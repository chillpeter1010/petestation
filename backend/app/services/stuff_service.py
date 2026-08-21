"""Reusable Stuff+ feature and scoring calculations.

This module intentionally separates feature extraction from model scoring.  The
first migration slice exposes a stable feature table and a transparent
prototype score so the frontend/API contract can settle before trained model
artifacts are wired in.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.api.schemas.common import AnalysisResponse, MetricItem, ResponseMeta
from app.api.schemas.stuff import StuffCalculatorRequest, StuffCalculatorResponse
from app.core.config import settings
from app.ml.stuff_plus import load_artifact, score_pitch_types
from app.repositories.pitch_repository import load_pitcher_cached_season
from app.services.personal_service import (
    dataframe_to_table_payload,
    display_pitch_name,
    filter_display_pitch_rows,
    normalize_pitch_names,
)


STUFF_FEATURE_COLUMNS = [
    "release_speed",
    "ivb",
    "adj_hb",
    "release_spin_rate",
    "release_extension",
    "release_pos_z",
    "adj_release_pos_x",
    "velo_diff_from_fastball",
    "ivb_diff_from_fastball",
    "hb_diff_from_fastball",
    "spin_axis_x",
    "spin_axis_y",
    "arm_angle",
    "release_extension_diff_from_fastball",
    "release_pos_z_diff_from_fastball",
]

FASTBALL_FAMILY = {"Four-Seam", "Sinker", "Cutter"}

PITCH_FAMILIES = {
    "4-Seam": "Fastball",
    "Four-Seam": "Fastball",
    "Sinker": "Fastball",
    "Cutter": "Fastball",
    "Slider": "Breaking",
    "Sweeper": "Breaking",
    "Curveball": "Breaking",
    "Knuckle Curve": "Breaking",
    "Changeup": "Offspeed",
    "Splitter": "Offspeed",
}

PITCH_TYPE_CODES = {
    "4-Seam": "FF",
    "Four-Seam": "FF",
    "Sinker": "SI",
    "Cutter": "FC",
    "Slider": "SL",
    "Sweeper": "ST",
    "Curveball": "CU",
    "Knuckle Curve": "KC",
    "Changeup": "CH",
    "Splitter": "FS",
    "Forkball": "FO",
}

PITCH_CODE_FAMILIES = {
    code: PITCH_FAMILIES.get(label, "Other")
    for label, code in PITCH_TYPE_CODES.items()
}


def _stuff_grade(value: float) -> str:
    thresholds = [
        (125, "A+"), (115, "A"), (110, "A-"), (105, "B+"),
        (100, "B"), (95, "B-"), (90, "C+"), (85, "C"), (80, "C-"),
    ]
    return next((grade for minimum, grade in thresholds if value >= minimum), "D")


def _pitch_key(value: Any) -> str:
    key = str(value or "").strip().lower().replace("-", " ")
    aliases = {
        "four seam": "four seam",
        "four seam fastball": "four seam",
        "4 seam": "four seam",
        "4 seam fastball": "four seam",
        "split finger": "splitter",
        "split finger fastball": "splitter",
    }
    return aliases.get(key, key)


def _numeric_series(data: pd.DataFrame, column: str) -> pd.Series:
    if column not in data.columns:
        return pd.Series(np.nan, index=data.index, dtype="float64")
    return pd.to_numeric(data[column], errors="coerce")


def _mean_or_nan(values: pd.Series) -> float:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return float("nan")
    return float(clean.mean())


def _pitcher_hand(data: pd.DataFrame) -> str:
    if "p_throws" not in data.columns:
        return "Unknown"
    values = data["p_throws"].dropna().astype(str).str.upper()
    if values.empty:
        return "Unknown"
    value = values.mode().iloc[0]
    return value if value in {"L", "R"} else "Unknown"


def _fastball_reference(feature_df: pd.DataFrame) -> pd.Series:
    if feature_df.empty:
        return pd.Series(dtype="float64")
    fastballs = feature_df[feature_df["pitch_name"].isin(FASTBALL_FAMILY)].copy()
    source = fastballs if not fastballs.empty else feature_df
    if "usage_pct" in source.columns:
        return source.sort_values("usage_pct", ascending=False).iloc[0]
    return source.iloc[0]


def build_stuff_feature_table(data: pd.DataFrame) -> pd.DataFrame:
    """Build pitch-type Stuff feature rows from Statcast pitch-level data."""

    if data.empty or "pitch_name" not in data.columns:
        return pd.DataFrame()

    working = filter_display_pitch_rows(normalize_pitch_names(data))
    if working.empty:
        return pd.DataFrame()

    working["pitch_name"] = working["pitch_name"].astype(str)
    working["pitches"] = 1
    working["release_speed"] = _numeric_series(working, "release_speed")
    working["ivb"] = _numeric_series(working, "pfx_z") * 12.0
    working["hb"] = _numeric_series(working, "pfx_x") * -12.0
    hand = _pitcher_hand(working)
    hand_multiplier = -1.0 if hand == "L" else 1.0
    working["adj_hb"] = working["hb"] * hand_multiplier
    working["release_spin_rate"] = _numeric_series(working, "release_spin_rate")
    working["release_extension"] = _numeric_series(working, "release_extension")
    working["release_pos_z"] = _numeric_series(working, "release_pos_z")
    working["release_pos_x"] = _numeric_series(working, "release_pos_x")
    working["adj_release_pos_x"] = working["release_pos_x"] * hand_multiplier
    working["arm_angle"] = _numeric_series(working, "arm_angle")

    spin_axis = _numeric_series(working, "spin_axis")
    spin_radians = np.deg2rad(spin_axis)
    working["spin_axis_x"] = np.cos(spin_radians)
    working["spin_axis_y"] = np.sin(spin_radians) * hand_multiplier

    grouped = (
        working.groupby("pitch_name", dropna=False)
        .agg(
            pitches=("pitches", "sum"),
            release_speed=("release_speed", "mean"),
            ivb=("ivb", "mean"),
            hb=("hb", "mean"),
            adj_hb=("adj_hb", "mean"),
            release_spin_rate=("release_spin_rate", "mean"),
            release_extension=("release_extension", "mean"),
            release_pos_z=("release_pos_z", "mean"),
            adj_release_pos_x=("adj_release_pos_x", "mean"),
            spin_axis_x=("spin_axis_x", "mean"),
            spin_axis_y=("spin_axis_y", "mean"),
            arm_angle=("arm_angle", "mean"),
        )
        .reset_index()
    )
    total = float(grouped["pitches"].sum())
    grouped["usage_pct"] = np.where(total > 0, grouped["pitches"] / total * 100.0, 0.0)

    reference = _fastball_reference(grouped)
    for source_col, output_col in [
        ("release_speed", "velo_diff_from_fastball"),
        ("ivb", "ivb_diff_from_fastball"),
        ("adj_hb", "hb_diff_from_fastball"),
        ("release_extension", "release_extension_diff_from_fastball"),
        ("release_pos_z", "release_pos_z_diff_from_fastball"),
    ]:
        base_value = reference.get(source_col, np.nan)
        grouped[output_col] = grouped[source_col] - base_value if pd.notna(base_value) else np.nan

    grouped["Pitch"] = grouped["pitch_name"].map(display_pitch_name)
    ordered = [
        "Pitch",
        "pitch_name",
        "pitches",
        "usage_pct",
        *STUFF_FEATURE_COLUMNS,
        "hb",
    ]
    available = [column for column in ordered if column in grouped.columns]
    result = grouped[available].sort_values(["pitches", "Pitch"], ascending=[False, True]).reset_index(drop=True)
    return result


def build_stuff_feature_diagnostics(feature_df: pd.DataFrame, source_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total_pitches = int(len(source_df))
    feature_pitches = int(feature_df["pitches"].sum()) if not feature_df.empty and "pitches" in feature_df.columns else 0
    rows.append({"check": "source_pitches", "value": total_pitches, "status": "ok" if total_pitches else "empty"})
    rows.append({"check": "feature_pitches", "value": feature_pitches, "status": "ok" if feature_pitches else "empty"})
    for column in STUFF_FEATURE_COLUMNS:
        if column not in feature_df.columns or feature_df.empty:
            coverage = 0.0
        else:
            coverage = float(pd.to_numeric(feature_df[column], errors="coerce").notna().mean() * 100.0)
        rows.append({
            "check": column,
            "value": round(coverage, 1),
            "status": "ok" if coverage >= 80 else ("partial" if coverage > 0 else "missing"),
        })
    return pd.DataFrame(rows)


def build_prototype_stuff_scores(feature_df: pd.DataFrame) -> pd.DataFrame:
    """Transparent placeholder until trained Stuff+ artifacts are connected."""

    if feature_df.empty:
        return pd.DataFrame()

    scored = feature_df.copy()
    velo_component = pd.to_numeric(scored.get("release_speed"), errors="coerce").fillna(0) - 90.0
    ivb_component = pd.to_numeric(scored.get("ivb"), errors="coerce").fillna(0).abs() / 2.5
    hb_component = pd.to_numeric(scored.get("adj_hb"), errors="coerce").fillna(0).abs() / 3.0
    spin_component = (pd.to_numeric(scored.get("release_spin_rate"), errors="coerce").fillna(2200) - 2200.0) / 180.0
    ext_component = (pd.to_numeric(scored.get("release_extension"), errors="coerce").fillna(6.0) - 6.0) * 2.0

    scored["prototype_stuff_plus"] = (100 + velo_component + ivb_component + hb_component + spin_component + ext_component).round(1)
    scored["model_status"] = "prototype_proxy"
    columns = [
        "Pitch",
        "pitches",
        "usage_pct",
        "prototype_stuff_plus",
        "release_speed",
        "ivb",
        "hb",
        "release_spin_rate",
        "release_extension",
        "model_status",
    ]
    return scored[[column for column in columns if column in scored.columns]].copy()


@lru_cache(maxsize=2)
def _load_pete_artifact(model_mtime: int, metadata_mtime: int):
    del model_mtime, metadata_mtime
    return load_artifact(settings.data_dir / "models" / "stuff_plus")


def _pete_pitch_type_scores(
    feature_df: pd.DataFrame,
    pitcher_hand: str,
    outing: bool,
) -> tuple[pd.DataFrame, str | None, str | None]:
    artifact_dir = settings.data_dir / "models" / "stuff_plus"
    model_path = artifact_dir / "pete_stuff_pipeline.joblib"
    metadata_path = artifact_dir / "pete_stuff_metadata.json"
    if feature_df.empty or not model_path.exists() or not metadata_path.exists():
        return pd.DataFrame(), None, None
    try:
        model, metadata = _load_pete_artifact(model_path.stat().st_mtime_ns, metadata_path.stat().st_mtime_ns)
        shape_rows = feature_df.copy()
        shape_rows["pitch_type"] = shape_rows["Pitch"].map(PITCH_TYPE_CODES).fillna("UN")
        shape_rows["p_throws"] = pitcher_hand
        scored = score_pitch_types(model, metadata, shape_rows, outing=outing)
    except (OSError, ValueError, KeyError):
        return pd.DataFrame(), None, None
    return (
        scored[["Pitch", "stuff_plus", "raw_stuff_plus", "reliability"]],
        str(metadata.get("model_version") or "pete_stuff_supervised"),
        str(metadata.get("generated_at")) if metadata.get("generated_at") else None,
    )


def calculate_stuff_pitch(request: StuffCalculatorRequest) -> StuffCalculatorResponse:
    """Score one hypothetical pitch shape with the active Peter Stuff+ artifact."""

    pitch_code = request.pitch_type.strip().upper()
    if pitch_code not in PITCH_CODE_FAMILIES:
        supported = ", ".join(sorted(PITCH_CODE_FAMILIES))
        raise ValueError(f"Unsupported pitch type {pitch_code!r}. Supported codes: {supported}")

    artifact_dir = settings.data_dir / "models" / "stuff_plus"
    model_path = artifact_dir / "pete_stuff_pipeline.joblib"
    metadata_path = artifact_dir / "pete_stuff_metadata.json"
    if not model_path.exists() or not metadata_path.exists():
        raise FileNotFoundError("Pete Stuff+ model artifact is unavailable")

    hand_sign = 1.0 if request.pitcher_hand == "R" else -1.0
    adjusted_hb = request.hb * hand_sign
    adjusted_fastball_hb = request.primary_fastball_hb * hand_sign
    spin_radians = np.deg2rad(request.spin_axis)
    derived = {
        "adj_hb": adjusted_hb,
        "adj_release_pos_x": request.release_pos_x * hand_sign,
        "velo_diff_from_fastball": request.release_speed - request.primary_fastball_speed,
        "ivb_diff_from_fastball": request.ivb - request.primary_fastball_ivb,
        "hb_diff_from_fastball": adjusted_hb - adjusted_fastball_hb,
        "spin_axis_x": float(np.cos(spin_radians)),
        "spin_axis_y": float(np.sin(spin_radians) * hand_sign),
    }
    shape = pd.DataFrame([{
        "pitch_type": pitch_code,
        "p_throws": request.pitcher_hand,
        "pitches": request.pitches,
        "release_speed": request.release_speed,
        "ivb": request.ivb,
        "release_spin_rate": request.spin_rate,
        "release_extension": request.extension,
        "release_pos_z": request.release_pos_z,
        "arm_angle": request.arm_angle,
        **derived,
    }])
    model, metadata = _load_pete_artifact(model_path.stat().st_mtime_ns, metadata_path.stat().st_mtime_ns)
    scored = score_pitch_types(model, metadata, shape, outing=False).iloc[0]
    stuff_plus = float(scored["stuff_plus"])
    raw_stuff_plus = float(scored["raw_stuff_plus"])
    return StuffCalculatorResponse(
        stuff_plus=round(stuff_plus, 1),
        raw_stuff_plus=round(raw_stuff_plus, 1),
        reliability=round(float(scored["reliability"]), 4),
        grade=_stuff_grade(stuff_plus),
        pitch_type=pitch_code,
        pitch_family=PITCH_CODE_FAMILIES[pitch_code],
        scale_source=str(scored["scale_source"]),
        model_version=str(metadata.get("model_version") or "pete_stuff_supervised"),
        contexts_evaluated=len(metadata.get("standard_contexts", [])),
        derived_features={key: round(float(value), 3) for key, value in derived.items()},
    )


def _derived_pitch_type_scores(year: int, pitcher_id: int) -> tuple[pd.DataFrame, str | None]:
    """Read versioned supervised scores without coupling the Lab to the export job."""

    db_path = settings.data_dir / "derived" / "derived_exports.duckdb"
    table = f"model_scores_pitch_type_{int(year)}"
    if not db_path.exists():
        return pd.DataFrame(), None
    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            if table not in tables:
                return pd.DataFrame(), None
            frame = conn.execute(
                f"""
                SELECT pitch_name, stuff_plus, model_version, generated_at
                FROM {table}
                WHERE pitcher_id = ?
                """,
                [int(pitcher_id)],
            ).fetchdf()
    except duckdb.Error:
        return pd.DataFrame(), None
    if frame.empty:
        return frame, None
    generated_at = str(frame["generated_at"].dropna().iloc[0]) if frame["generated_at"].notna().any() else None
    return frame, generated_at


def _derived_outing_scores(year: int, pitcher_id: int, game_pk: int) -> tuple[pd.DataFrame, str | None]:
    db_path = settings.data_dir / "derived" / "derived_exports.duckdb"
    table = f"outing_pitch_type_metrics_{int(year)}"
    if not db_path.exists():
        return pd.DataFrame(), None
    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            if table not in tables:
                return pd.DataFrame(), None
            frame = conn.execute(
                f"""
                SELECT pitch_name, stuff_plus, 'outing_supervised_v1' AS model_version, generated_at
                FROM {table}
                WHERE pitcher_id = ? AND game_pk = ?
                """,
                [int(pitcher_id), int(game_pk)],
            ).fetchdf()
    except duckdb.Error:
        return pd.DataFrame(), None
    if frame.empty:
        return frame, None
    generated_at = str(frame["generated_at"].dropna().iloc[0]) if frame["generated_at"].notna().any() else None
    return frame, generated_at


def _split_shape_scores(pitch_df: pd.DataFrame) -> pd.DataFrame:
    """Return transparent shape proxies for the shapes observed vs each batter side."""

    if pitch_df.empty or "stand" not in pitch_df.columns:
        return pd.DataFrame(columns=["pitch_name", "shape_vs_r", "shape_vs_l"])
    pieces: list[pd.DataFrame] = []
    for stand, output in [("R", "shape_vs_r"), ("L", "shape_vs_l")]:
        side_features = build_stuff_feature_table(pitch_df.loc[pitch_df["stand"].astype(str).str.upper().eq(stand)])
        side_scores = build_prototype_stuff_scores(side_features)
        if side_scores.empty:
            continue
        piece = side_scores[["Pitch", "prototype_stuff_plus"]].rename(
            columns={"Pitch": "pitch_name", "prototype_stuff_plus": output}
        )
        pieces.append(piece)
    if not pieces:
        return pd.DataFrame(columns=["pitch_name", "shape_vs_r", "shape_vs_l"])
    result = pieces[0]
    for piece in pieces[1:]:
        result = result.merge(piece, on="pitch_name", how="outer")
    return result


def build_stuff_lab_scores(
    pitch_df: pd.DataFrame,
    year: int,
    pitcher_id: int,
    game_pk: int | None = None,
    scoring_mode: str = "pete",
) -> tuple[pd.DataFrame, str, str | None]:
    """Score pitch shapes with the requested model, retaining a visible fallback."""

    features = build_stuff_feature_table(pitch_df)
    proxy = build_prototype_stuff_scores(features)
    if proxy.empty:
        return proxy, "unavailable", None

    scores = proxy.rename(columns={"prototype_stuff_plus": "shape_proxy"})
    scores["pitch_key"] = scores["Pitch"].map(_pitch_key)
    if scoring_mode == "pete":
        derived, supervised_version, generated_at = _pete_pitch_type_scores(
            features,
            pitcher_hand=_pitcher_hand(pitch_df),
            outing=game_pk is not None,
        )
        if supervised_version and "v3_312_contexts" in supervised_version:
            supervised_source = "Pete Stuff+ v3 · 312 fixed contexts"
        elif supervised_version and "outcome_probability_v2" in supervised_version:
            supervised_source = "Pete Stuff+ outcome probability v2 · pitch scaled"
        else:
            supervised_source = "Pete Stuff+ supervised"
    else:
        snapshot, generated_at = (
            _derived_outing_scores(year, pitcher_id, game_pk)
            if game_pk is not None
            else _derived_pitch_type_scores(year, pitcher_id)
        )
        supervised_version = None
        if not snapshot.empty:
            supervised_version = str(snapshot["model_version"].dropna().iloc[0]) if snapshot["model_version"].notna().any() else "supervised"
            derived = snapshot.rename(columns={"pitch_name": "Pitch"})[["Pitch", "stuff_plus"]].copy()
            derived["raw_stuff_plus"] = np.nan
            derived["reliability"] = np.nan
        else:
            derived = pd.DataFrame()
        supervised_source = "Supervised model snapshot"
    model_status = "shape_proxy"
    has_supervised_score = pd.Series(False, index=scores.index)
    if not derived.empty:
        derived["pitch_key"] = derived["Pitch"].map(_pitch_key)
        derived = derived.drop(columns=["Pitch"])
        scores = scores.merge(derived, on="pitch_key", how="left")
        has_supervised_score = pd.to_numeric(scores["stuff_plus"], errors="coerce").notna()
        if scores["stuff_plus"].notna().any():
            model_status = supervised_version or "supervised"
    if "stuff_plus" not in scores.columns:
        scores["stuff_plus"] = scores["shape_proxy"]
    else:
        scores["stuff_plus"] = pd.to_numeric(scores["stuff_plus"], errors="coerce").fillna(scores["shape_proxy"])

    splits = _split_shape_scores(pitch_df)
    scores = scores.merge(splits, left_on="Pitch", right_on="pitch_name", how="left")
    scores["pitch_family"] = scores["Pitch"].map(PITCH_FAMILIES).fillna("Other")
    scores["score_source"] = np.where(
        has_supervised_score,
        supervised_source,
        "Shape proxy fallback",
    )
    scores = scores.drop(columns=[column for column in ["pitch_key", "pitch_name", "model_status", "generated_at"] if column in scores.columns])
    ordered = [
        "Pitch", "pitch_family", "pitches", "usage_pct", "stuff_plus", "shape_proxy",
        "raw_stuff_plus", "reliability",
        "shape_vs_r", "shape_vs_l", "release_speed", "ivb", "hb",
        "release_spin_rate", "release_extension", "score_source",
    ]
    return scores[[column for column in ordered if column in scores.columns]], model_status, generated_at


def get_stuff_features(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> AnalysisResponse:
    pitch_df = load_pitcher_cached_season(year=year, pitcher_id=pitcher_id, data_dir=settings.data_dir, start_date=start_date, end_date=end_date)
    feature_df = build_stuff_feature_table(pitch_df)
    diagnostics = build_stuff_feature_diagnostics(feature_df, pitch_df)
    warnings = []
    if pitch_df.empty:
        warnings.append("No pitch-level rows found for this pitcher/date range.")
    if not feature_df.empty:
        missing = diagnostics.loc[diagnostics["status"].eq("missing"), "check"].tolist()
        if missing:
            warnings.append(f"Missing feature coverage: {', '.join(missing)}")

    return AnalysisResponse(
        meta=ResponseMeta(year=year, warnings=warnings),
        summary=[
            MetricItem(key="source_pitches", label="Source Pitches", value=int(len(pitch_df))),
            MetricItem(key="pitch_types", label="Pitch Types", value=int(feature_df["Pitch"].nunique()) if not feature_df.empty else 0),
            MetricItem(key="feature_columns", label="Feature Columns", value=len(STUFF_FEATURE_COLUMNS)),
        ],
        tables={
            "stuff_features": dataframe_to_table_payload(feature_df),
            "feature_diagnostics": dataframe_to_table_payload(diagnostics),
        },
    )


def get_stuff_score(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    game_pk: int | None = None,
    scoring_mode: str = "pete",
) -> AnalysisResponse:
    pitch_df = load_pitcher_cached_season(year=year, pitcher_id=pitcher_id, data_dir=settings.data_dir, start_date=start_date, end_date=end_date)
    if game_pk is not None and not pitch_df.empty and "game_pk" in pitch_df.columns:
        pitch_df = pitch_df.loc[pd.to_numeric(pitch_df["game_pk"], errors="coerce").eq(int(game_pk))].copy()
    feature_df = build_stuff_feature_table(pitch_df)
    score_df, model_status, generated_at = build_stuff_lab_scores(
        pitch_df, year, pitcher_id, game_pk=game_pk, scoring_mode=scoring_mode
    )
    diagnostics = build_stuff_feature_diagnostics(feature_df, pitch_df)
    warnings = []
    if model_status in {"shape_proxy", "unavailable"}:
        missing_source = "Pete Stuff+ model artifact" if scoring_mode == "pete" else "supervised score snapshot"
        warnings.append(f"No {missing_source} was available; this response is using the transparent shape proxy fallback.")
    elif scoring_mode == "pete":
        warnings.append(
            "Stuff+ uses Pete Stuff+ v3 with pitch-type-specific scales: calibrated pitch-result probabilities "
            "are converted to expected run value over one fixed 2-side x 12-count x 13-zone test."
        )
    else:
        warnings.append("Stuff+ uses the latest supervised export snapshot; current shape metrics use the selected live date range.")
    warnings.append("Vs R/L values are observed-shape proxies, not separate supervised platoon Stuff+ models.")
    if pitch_df.empty:
        warnings.append("No pitch-level rows found for this pitcher/date range.")

    weighted_stuff = None
    if not score_df.empty:
        weights = pd.to_numeric(score_df["pitches"], errors="coerce").fillna(0)
        values = pd.to_numeric(score_df["stuff_plus"], errors="coerce")
        valid = values.notna() & weights.gt(0)
        if valid.any():
            weighted_stuff = round(float(np.average(values.loc[valid], weights=weights.loc[valid])), 1)
    best_pitch = None
    if not score_df.empty and score_df["stuff_plus"].notna().any():
        best_pitch = str(score_df.sort_values(["stuff_plus", "pitches"], ascending=[False, False]).iloc[0]["Pitch"])

    pitch_stuff = pd.Series(np.nan, index=pitch_df.index, dtype="float64")
    if not pitch_df.empty:
        from app.services.pitch_stuff_cache_service import load_pitch_stuff_scores

        pitch_stuff = load_pitch_stuff_scores(pitch_df, settings.data_dir)
    variability = build_stuff_variability_table(pitch_df, pitch_stuff)
    covered = int(pitch_stuff.notna().sum())
    overall_mean = round(float(pitch_stuff.mean()), 1) if covered else None
    overall_sd = round(float(pitch_stuff.std(ddof=1)), 1) if covered > 1 else None
    overall_se = round(float(pitch_stuff.sem()), 1) if covered > 1 else None
    if len(pitch_df) and covered == 0:
        warnings.append("Per-pitch Stuff+ cache is not available for this selection; consistency metrics are hidden.")

    return AnalysisResponse(
        meta=ResponseMeta(year=year, data_updated_at=pd.to_datetime(generated_at, errors="coerce") if generated_at else None, warnings=warnings),
        summary=[
            MetricItem(key="stuff_plus", label="Stuff+", value=weighted_stuff),
            MetricItem(key="best_pitch", label="Best Pitch", value=best_pitch),
            MetricItem(key="source_pitches", label="Source Pitches", value=int(len(pitch_df))),
            MetricItem(key="pitch_types", label="Pitch Types", value=int(score_df["Pitch"].nunique()) if not score_df.empty else 0),
            MetricItem(key="model_status", label="Model", value=model_status),
            MetricItem(key="pitch_stuff_mean", label="Pitch Stuff+ Mean", value=overall_mean),
            MetricItem(key="pitch_stuff_sd", label="Stuff+ SD", value=overall_sd),
            MetricItem(key="pitch_stuff_se", label="Stuff+ SE", value=overall_se),
            MetricItem(key="pitch_stuff_coverage", label="Stuff+ Coverage", value=f"{covered}/{len(pitch_df)}"),
        ],
        charts={"pitch_profiles": score_df.to_dict(orient="records")},
        tables={
            "stuff_scores": dataframe_to_table_payload(score_df),
            "stuff_features": dataframe_to_table_payload(feature_df),
            "feature_diagnostics": dataframe_to_table_payload(diagnostics),
            "stuff_variability": dataframe_to_table_payload(variability),
        },
    )


def build_stuff_variability_table(pitch_df: pd.DataFrame, pitch_stuff: pd.Series) -> pd.DataFrame:
    columns = ["Pitch", "Pitches", "Avg Stuff+", "SD", "SE", "P10", "P90"]
    if pitch_df.empty or pitch_stuff.notna().sum() == 0:
        return pd.DataFrame(columns=columns)

    working = normalize_pitch_names(pitch_df.copy())
    raw_names = working.get("pitch_name", pd.Series("Unknown", index=working.index))
    working["Pitch"] = raw_names.map(display_pitch_name)
    working["pitch_stuff_plus"] = pd.to_numeric(pitch_stuff, errors="coerce")
    rows: list[dict[str, Any]] = []
    for pitch, group in working.groupby("Pitch", dropna=False, sort=False):
        values = group["pitch_stuff_plus"].dropna()
        if values.empty:
            continue
        rows.append({
            "Pitch": str(pitch),
            "Pitches": int(len(values)),
            "Avg Stuff+": round(float(values.mean()), 1),
            "SD": round(float(values.std(ddof=1)), 1) if len(values) > 1 else None,
            "SE": round(float(values.sem()), 1) if len(values) > 1 else None,
            "P10": round(float(values.quantile(0.10)), 1),
            "P90": round(float(values.quantile(0.90)), 1),
        })
    return pd.DataFrame(rows, columns=columns).sort_values("Pitches", ascending=False).reset_index(drop=True)
