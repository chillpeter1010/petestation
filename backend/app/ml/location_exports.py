"""Batch inference and aggregate exports for Location+."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd

from app.ml.location_plus import MODEL_FEATURES, OUTCOMES, SOURCE_COLUMNS, apply_temperature, build_training_frame, expected_run_value
from app.ml.plus_scoring import lower_is_better_plus, shrink_plus


IDENTITY_COLUMNS = ["pitch_uid", "game_pk", "player_name", "pitcher_team"]

PITCH_CODES = {
    "4-Seam Fastball": "FA",
    "Sinker": "SI",
    "Cutter": "FC",
    "Split-Finger": "FS",
    "Slider": "SL",
    "Sweeper": "SL",
    "Curveball": "CU",
    "Changeup": "CH",
    "Knuckle Curve": "KC",
    "Forkball": "FO",
}

SCORING_VERSION = "location_plus_aggregate_v2"


def _display_name(value: object) -> str:
    text = str(value or "Unknown").strip()
    if "," in text:
        last, first = (piece.strip() for piece in text.split(",", 1))
        return f"{first} {last}".strip()
    return text


def _location_plus(xrv_per_100: pd.Series, scale: dict[str, float]) -> pd.Series:
    return pd.Series(
        lower_is_better_plus(
            xrv_per_100,
            mean=float(scale["mean_xrv_per_100"]),
            standard_deviation=float(scale["sd_xrv_per_100"]),
            points_per_sd=float(scale["points_per_sd"]),
        ),
        index=xrv_per_100.index,
    )


def _aggregate_predictions(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    grouped = frame.groupby(keys, dropna=False).agg(
        pitches=("xrv", "size"),
        xrv_per_pitch=("xrv", "mean"),
        xrv_sd=("xrv", "std"),
        called_strike_pct=("called_strike_probability", "mean"),
        whiff_pct=("whiff_probability", "mean"),
        barrel_pct=("barrel_probability", "mean"),
        ball_pct=("ball_probability", "mean"),
    ).reset_index()
    grouped["xrv_per_100"] = grouped["xrv_per_pitch"] * 100.0
    for column in ["called_strike_pct", "whiff_pct", "barrel_pct", "ball_pct"]:
        grouped[column] *= 100.0
    return grouped


def _score_aggregates(
    grouped: pd.DataFrame,
    scale: dict[str, float],
    *,
    prior_pitches: float,
) -> pd.DataFrame:
    scored = grouped.copy()
    scored["raw_location_plus"] = _location_plus(scored["xrv_per_100"], scale)
    adjusted, reliability = shrink_plus(
        scored["raw_location_plus"],
        scored["pitches"],
        prior_pitches=prior_pitches,
    )
    scored["location_plus"] = adjusted
    scored["reliability"] = reliability
    raw_se = (
        float(scale["points_per_sd"])
        * scored["xrv_sd"].fillna(0.0)
        * 100.0
        / np.sqrt(scored["pitches"].clip(lower=1))
        / float(scale["sd_xrv_per_100"])
    )
    scored["location_plus_se"] = raw_se * reliability
    return scored.drop(columns=["xrv_sd"])


def _aggregate(
    frame: pd.DataFrame,
    keys: list[str],
    scale: dict[str, float],
    *,
    prior_pitches: float,
) -> pd.DataFrame:
    return _score_aggregates(
        _aggregate_predictions(frame, keys),
        scale,
        prior_pitches=prior_pitches,
    )


def _pitch_type_scales(
    pitch_type_rows: pd.DataFrame,
    fallback: dict[str, float],
) -> dict[str, dict[str, float]]:
    """Build one stable display scale per canonical pitch group.

    This is a reporting calibration, not another predictive model.  The xRV for
    every pitch has already been produced by the same Location+ model.
    """

    scales: dict[str, dict[str, float]] = {}
    qualified = pitch_type_rows.loc[pitch_type_rows["pitches"] >= 50]
    for pitch_code, rows in qualified.groupby("pitch_code"):
        values = rows["xrv_per_100"].to_numpy(dtype="float64")
        weights = rows["pitches"].to_numpy(dtype="float64")
        if len(values) < 2:
            continue
        mean = float(np.average(values, weights=weights))
        sd = float(np.std(values, ddof=1))
        if not np.isfinite(sd) or sd <= 1e-9:
            continue
        scales[str(pitch_code)] = {
            "mean_xrv_per_100": mean,
            "sd_xrv_per_100": sd,
            "points_per_sd": float(fallback["points_per_sd"]),
        }
    return scales


def _score_pitch_type_rows(
    rows: pd.DataFrame,
    scales: dict[str, dict[str, float]],
    fallback: dict[str, float],
    *,
    prior_pitches: float,
) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    for pitch_code, group in rows.groupby("pitch_code", dropna=False):
        scale = scales.get(str(pitch_code), fallback)
        piece = _score_aggregates(group, scale, prior_pitches=prior_pitches)
        piece["scale_source"] = f"pitch_type:{pitch_code}" if str(pitch_code) in scales else "global"
        pieces.append(piece)
    return pd.concat(pieces, ignore_index=True) if pieces else rows.iloc[0:0].copy()


def export_location_scores(data_dir: Path, year: int) -> dict[str, object]:
    model_dir = data_dir / "models" / "location_plus"
    metadata = json.loads((model_dir / "location_plus_metadata.json").read_text(encoding="utf-8"))
    model = joblib.load(model_dir / "location_plus_pipeline.joblib")
    source_path = data_dir / f"MLB{year}" / f"mlb_{year}.duckdb"
    columns = ", ".join(dict.fromkeys([*SOURCE_COLUMNS, *IDENTITY_COLUMNS]))
    with duckdb.connect(str(source_path), read_only=True) as conn:
        raw = conn.execute(
            f"""
            SELECT {columns}
            FROM pitches
            WHERE game_type = 'R'
              AND plate_x IS NOT NULL
              AND plate_z IS NOT NULL
              AND sz_top > sz_bot
            """
        ).fetchdf()
    raw["season"] = int(year)
    frame = build_training_frame(raw)
    probabilities = apply_temperature(model.predict_proba(frame[MODEL_FEATURES]), float(metadata["temperature"]))
    classes = model.named_steps["model"].classes_
    class_index = {OUTCOMES[int(value)]: index for index, value in enumerate(classes)}
    frame["xrv"] = expected_run_value(probabilities, classes, metadata["run_values"])
    frame["called_strike_probability"] = probabilities[:, class_index["called_strike"]]
    frame["whiff_probability"] = probabilities[:, class_index["swinging_strike"]]
    frame["barrel_probability"] = probabilities[:, class_index["barrel"]]
    frame["ball_probability"] = probabilities[:, class_index["ball"]]
    frame["pitcher_name"] = frame["player_name"].map(_display_name)
    frame["team"] = frame["pitcher_team"].fillna("-").astype(str)
    frame["game_date"] = pd.to_datetime(frame["game_date"], errors="coerce").dt.date
    frame["pitch_code"] = frame["pitch_name"].map(PITCH_CODES)
    latest_identity = (
        frame.sort_values("game_date")
        .groupby(["season", "pitcher"], as_index=False)
        .tail(1)[["season", "pitcher", "pitcher_name", "team"]]
        .rename(columns={"pitcher_name": "latest_pitcher_name", "team": "latest_team"})
    )
    heatmap_scale = metadata["location_heatmap_scale"]
    frame["location_plus_pitch"] = _location_plus(frame["xrv"] * 100.0, heatmap_scale)

    pitch_columns = [
        "pitch_uid", "season", "game_pk", "game_date", "pitcher", "pitcher_name", "team",
        "pitch_name", "pitch_code", "stand", "p_throws", "balls", "strikes", "plate_x", "plate_z_norm",
        "xrv", "location_plus_pitch", "called_strike_probability", "whiff_probability",
        "barrel_probability", "ball_probability",
    ]
    pitch_scores = frame[pitch_columns].rename(columns={"pitcher": "pitcher_id"})
    scale = metadata["location_plus_scale"]
    pitcher_scores = _aggregate(frame, ["season", "pitcher"], scale, prior_pitches=50.0)
    pitcher_scores = pitcher_scores.merge(latest_identity, on=["season", "pitcher"], how="left").rename(columns={"pitcher": "pitcher_id", "latest_pitcher_name": "pitcher_name", "latest_team": "team"})
    pitcher_scores["sample_status"] = np.where(pitcher_scores["pitches"] >= 300, "qualified", np.where(pitcher_scores["pitches"] >= 100, "limited", "provisional"))
    side_scores = _aggregate(frame, ["season", "pitcher", "stand"], scale, prior_pitches=25.0)
    side_pivot = side_scores.pivot(index=["season", "pitcher"], columns="stand", values="location_plus").reset_index().rename(columns={"L": "location_plus_vs_l", "R": "location_plus_vs_r"})
    pitcher_scores = pitcher_scores.merge(side_pivot, left_on=["season", "pitcher_id"], right_on=["season", "pitcher"], how="left").drop(columns=["pitcher"])
    pitch_type_predictions = _aggregate_predictions(frame.loc[frame["pitch_code"].notna()], ["season", "pitcher", "pitch_name", "pitch_code"])
    pitch_scales = _pitch_type_scales(pitch_type_predictions, scale)
    pitch_type_scores = _score_pitch_type_rows(
        pitch_type_predictions,
        pitch_scales,
        scale,
        prior_pitches=50.0,
    )
    pitch_type_scores = pitch_type_scores.merge(latest_identity, on=["season", "pitcher"], how="left").rename(columns={"pitcher": "pitcher_id", "latest_pitcher_name": "pitcher_name", "latest_team": "team"})
    pitch_type_scores["sample_status"] = np.where(pitch_type_scores["pitches"] >= 50, "qualified", "provisional")
    outing_scores = _aggregate(frame, ["season", "pitcher", "team", "game_pk", "game_date"], scale, prior_pitches=15.0)
    outing_scores = outing_scores.merge(latest_identity[["season", "pitcher", "latest_pitcher_name"]], on=["season", "pitcher"], how="left").rename(columns={"pitcher": "pitcher_id", "latest_pitcher_name": "pitcher_name"})
    outing_pitch_type_predictions = _aggregate_predictions(
        frame.loc[frame["pitch_code"].notna()],
        ["season", "pitcher", "team", "game_pk", "game_date", "pitch_name", "pitch_code"],
    )
    outing_pitch_type_scores = _score_pitch_type_rows(
        outing_pitch_type_predictions,
        pitch_scales,
        scale,
        prior_pitches=15.0,
    ).rename(columns={"pitcher": "pitcher_id"})
    outing_pitch_type_scores["sample_status"] = np.where(
        outing_pitch_type_scores["pitches"] >= 15,
        "limited",
        "provisional",
    )

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for table in [pitch_scores, pitcher_scores, pitch_type_scores, outing_scores, outing_pitch_type_scores]:
        table["model_version"] = metadata["model_version"]
        table["scoring_version"] = SCORING_VERSION
        table["generated_at"] = generated_at

    output_path = data_dir / "derived" / "location_plus_scores.duckdb"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tables = {
        f"location_pitch_scores_{year}": pitch_scores,
        f"location_pitcher_scores_{year}": pitcher_scores,
        f"location_pitch_type_scores_{year}": pitch_type_scores,
        f"location_outing_scores_{year}": outing_scores,
        f"location_outing_pitch_type_scores_{year}": outing_pitch_type_scores,
    }
    with duckdb.connect(str(output_path)) as conn:
        for table_name, table in tables.items():
            conn.register("export_frame", table)
            conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM export_frame")
            conn.unregister("export_frame")
        manifest = pd.DataFrame([{
            "year": int(year),
            "model_version": metadata["model_version"],
            "scoring_version": SCORING_VERSION,
            "generated_at": generated_at,
            "pitch_rows": len(pitch_scores),
            "pitcher_rows": len(pitcher_scores),
            "pitch_type_rows": len(pitch_type_scores),
            "outing_rows": len(outing_scores),
        }])
        conn.register("manifest_frame", manifest)
        conn.execute("CREATE TABLE IF NOT EXISTS location_manifest AS SELECT * FROM manifest_frame WHERE FALSE")
        conn.execute("ALTER TABLE location_manifest ADD COLUMN IF NOT EXISTS scoring_version VARCHAR")
        conn.execute("DELETE FROM location_manifest WHERE year = ?", [int(year)])
        conn.execute(
            """
            INSERT INTO location_manifest
                (year, model_version, generated_at, pitch_rows, pitcher_rows,
                 pitch_type_rows, outing_rows, scoring_version)
            SELECT year, model_version, generated_at, pitch_rows, pitcher_rows,
                   pitch_type_rows, outing_rows, scoring_version
            FROM manifest_frame
            """
        )
        conn.unregister("manifest_frame")
    return manifest.iloc[0].to_dict()
