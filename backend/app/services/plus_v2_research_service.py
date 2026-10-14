"""Research-only audit and challenger summaries for the Plus v2 roadmap.

This module deliberately does not replace the production Stuff+/Location+
contracts.  Slice 7 freezes the cleaning/taxonomy audit first; Slices 8 and 9
then use the already materialised pitch scores to measure the effect of the
cleaning and taxonomy rules without paying the cost of refitting the XGBoost
models.  A later release gate can promote a refit challenger only after these
diagnostics are reviewed.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import duckdb
import joblib
import numpy as np
import pandas as pd

from app.ml.location_plus import (
    MODEL_FEATURES as LOCATION_MODEL_FEATURES,
    OUTCOMES as LOCATION_OUTCOMES,
    apply_temperature as apply_location_temperature,
    build_training_frame as build_location_training_frame,
    choose_temperature as choose_location_temperature,
    evaluate as evaluate_location,
    expected_run_value as location_expected_run_value,
    location_scale,
    make_pipeline as make_location_pipeline,
    outcome_run_values as location_outcome_run_values,
    SOURCE_COLUMNS as LOCATION_SOURCE_COLUMNS,
    calibration_error as location_calibration_error,
)
from app.ml.stuff_plus import (
    CONTEXT_FEATURES as STUFF_CONTEXT_FEATURES,
    MODEL_FEATURES as STUFF_MODEL_FEATURES,
    PHYSICAL_FEATURES as STUFF_PHYSICAL_FEATURES,
    PITCH_TYPE_FAMILIES,
    SOURCE_COLUMNS as STUFF_SOURCE_COLUMNS,
    build_training_frame as build_stuff_training_frame,
    choose_temperature as choose_stuff_temperature,
    evaluate as evaluate_stuff,
    expected_run_value as stuff_expected_run_value,
    make_pipeline as make_stuff_pipeline,
    outcome_run_values as stuff_outcome_run_values,
    score_standard_contexts,
    standard_context_grid,
    calibration_error as stuff_calibration_error,
)

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.performance_state_v2_service import _position_player_ids


PLUS_V2_VERSION = "plus_v2_research_slices_7_9_v1"
YEARS = (2021, 2022, 2023, 2024, 2025, 2026)
RAW_AUDIT_FIELDS = (
    "pitch_name",
    "pitch_type",
    "release_speed",
    "pfx_x",
    "pfx_z",
    "release_spin_rate",
    "release_extension",
    "release_pos_z",
    "release_pos_x",
    "spin_axis",
    "arm_angle",
    "plate_x",
    "plate_z",
)

PITCH_CODE_BY_NAME = {
    "4-Seam Fastball": "FA",
    "Four-Seam Fastball": "FA",
    "Fastball": "FA",
    "Sinker": "SI",
    "Cutter": "FC",
    "Split-Finger": "FS",
    "Splitter": "FS",
    "Slider": "SL",
    "Sweeper": "SL",
    "Curveball": "CU",
    "Knuckle Curve": "KC",
    "Changeup": "CH",
    "Forkball": "FO",
}
KNOWN_CODES = {"FA", "SI", "FC", "FS", "SL", "CU", "CH", "KC", "FO"}


def artifact_path(slice_id: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"plus_v2_slice{int(slice_id)}.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def _sql_in(column: str, values: Iterable[int]) -> tuple[str, list[int]]:
    clean = sorted({int(value) for value in values})
    if not clean:
        return "1 = 1", []
    return f"{column} NOT IN ({','.join('?' for _ in clean)})", clean


def canonical_pitch_code(pitch_code: Any, pitch_name: Any) -> str | None:
    """Map names/codes to the reporting taxonomy used by the Plus boards."""

    code = str(pitch_code).strip().upper() if pitch_code is not None else ""
    name = str(pitch_name).strip() if pitch_name is not None else ""
    if code in KNOWN_CODES:
        return code
    return PITCH_CODE_BY_NAME.get(name)


def _raw_audit(year: int, root: Path) -> dict[str, Any]:
    path = get_season_duckdb_path(year, root)
    if not path.exists():
        return {"year": year, "status": "missing_source"}
    with duckdb.connect(str(path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        source = resolve_pitch_table(tables)
        if not source:
            return {"year": year, "status": "missing_pitch_table"}
        columns = {row[0] for row in connection.execute(f"DESCRIBE {source}").fetchall()}
        available_audit = [field for field in RAW_AUDIT_FIELDS if field in columns]
        expressions = [
            "COUNT(*) AS pitch_rows",
            "COUNT(DISTINCT game_pk) AS games",
            "COUNT(DISTINCT pitcher) AS pitchers",
            "MIN(game_date) AS first_date",
            "MAX(game_date) AS last_date",
        ]
        for field in available_audit:
            expressions.append(f"AVG(CASE WHEN {field} IS NOT NULL THEN 1.0 ELSE 0.0 END) AS {field}_coverage")
        summary = connection.execute(
            f"SELECT {', '.join(expressions)} FROM {source} WHERE game_type = 'R' AND pitcher IS NOT NULL"
        ).fetchone()
        position_ids, defensive_games = _position_player_ids(year, root)
        actual_pitchers = {
            int(row[0])
            for row in connection.execute(
                f"SELECT DISTINCT pitcher FROM {source} WHERE game_type = 'R' AND pitcher IS NOT NULL"
            ).fetchall()
        }
        position_pitchers = position_ids & actual_pitchers
        clean_where, clean_params = _sql_in("pitcher", position_ids)
        clean_count = connection.execute(
            f"SELECT COUNT(*) FROM {source} WHERE game_type = 'R' AND pitcher IS NOT NULL AND {clean_where}",
            clean_params,
        ).fetchone()[0]
        position_pitch_rows = int(summary[0] or 0) - int(clean_count or 0)
        season_stats = connection.execute(
            f"""
            SELECT pitcher, SUM(game_pitches) AS season_pitches,
                   COUNT(*) AS appearances, MAX(game_pitches) AS max_appearance_pitches
            FROM (
                SELECT pitcher, game_pk, COUNT(*) AS game_pitches
                FROM {source}
                WHERE game_type = 'R' AND pitcher IS NOT NULL
                GROUP BY pitcher, game_pk
            )
            GROUP BY pitcher
            """
        ).fetchall()
        low_volume = [
            row for row in season_stats
            if int(row[1] or 0) < 60 and int(row[2] or 0) <= 4 and int(row[3] or 0) <= 40
        ]
        groups = connection.execute(
            f"SELECT pitch_name, pitch_type, COUNT(*) AS pitches FROM {source} "
            "WHERE game_type = 'R' AND pitcher IS NOT NULL GROUP BY 1, 2 ORDER BY pitches DESC"
        ).fetchall()
    raw_groups = [
        {
            "pitch_name": row[0],
            "pitch_type": row[1],
            "pitches": int(row[2]),
            "canonical_code": canonical_pitch_code(row[1], row[0]),
        }
        for row in groups
    ]
    canonical_counts: Counter[str] = Counter()
    unmapped = 0
    for row in raw_groups:
        code = row["canonical_code"]
        if code:
            canonical_counts[code] += row["pitches"]
        else:
            unmapped += row["pitches"]
    values = dict(zip(["pitch_rows", "games", "pitchers", "first_date", "last_date", *[f"{f}_coverage" for f in available_audit]], summary))
    total_rows = int(values.pop("pitch_rows") or 0)
    values.update(
        {
            "year": year,
            "status": "ok",
            "source_table": source,
            "pitch_rows": total_rows,
            "position_player_pitch_rows": position_pitch_rows,
            "position_player_pitch_pct": _number(position_pitch_rows / total_rows * 100.0) if total_rows else None,
            "position_player_pitchers": len(position_pitchers),
            "position_player_defensive_game_slots": int(sum(defensive_games.values())),
            "low_volume_emergency_rule": "season pitches <60, appearances <=4, max appearance <=40 (hindsight audit only)",
            "low_volume_emergency_pitchers": len(low_volume),
            "low_volume_emergency_pitch_rows": int(sum(int(row[1] or 0) for row in low_volume)),
            "raw_pitch_groups": raw_groups,
            "canonical_pitch_counts": dict(sorted(canonical_counts.items())),
            "unmapped_pitch_rows": unmapped,
            "available_audit_fields": available_audit,
        }
    )
    return values


def build_slice7(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    yearly = [_raw_audit(year, root) for year in YEARS]
    result = {
        "artifact": "plus_v2_slice7_cleaning_audit",
        "version": PLUS_V2_VERSION,
        "generated_at": _now(),
        "scope": "MLB regular-season Statcast pitch rows 2021-2026",
        "production_impact": "none; formal Stuff+/Location+ contracts remain unchanged",
        "rules": {
            "exclude_position_player_pitching": True,
            "position_player_definition": "pitcher ID appears in a fielder_2..fielder_9 slot during that season",
            "low_volume_emergency": "cohort audit only; never a pregame feature",
            "opener_bulk": "retain and label; do not silently drop",
            "canonical_pitch_taxonomy": "FA, SI, FC, FS, SL (Slider+Sweeper), CU, CH, KC, FO",
            "tracking_era": "report field coverage by year; do not pool a missing field as zero",
        },
        "yearly": yearly,
    }
    _write_json(artifact_path(7, root), result)
    return result


def _score_cache_summary(year: int, root: Path, position_ids: set[int]) -> dict[str, Any]:
    path = root / "derived" / "pitch_stuff_scores.sqlite3"
    if not path.exists():
        return {"year": year, "status": "missing_score_cache"}
    with sqlite3.connect(path, timeout=60) as connection:
        total = connection.execute("SELECT COUNT(*), AVG(pitch_stuff_plus), AVG(pitch_stuff_plus * pitch_stuff_plus) FROM pitch_stuff_scores WHERE year = ?", (year,)).fetchone()
        where, params = _sql_in("pitcher", position_ids)
        clean = connection.execute(
            f"SELECT COUNT(*), AVG(pitch_stuff_plus), AVG(pitch_stuff_plus * pitch_stuff_plus) FROM pitch_stuff_scores WHERE year = ? AND {where}",
            [year, *params],
        ).fetchone()
        pitcher_rows = connection.execute(
            f"SELECT pitcher, COUNT(*) AS pitches, AVG(pitch_stuff_plus) AS stuff_plus FROM pitch_stuff_scores WHERE year = ? AND {where} GROUP BY pitcher",
            [year, *params],
        ).fetchall()
        versions = connection.execute("SELECT model_version, COUNT(*) FROM pitch_stuff_scores WHERE year = ? GROUP BY model_version", (year,)).fetchall()
    def population_sd(row: tuple[Any, ...]) -> float | None:
        if row[1] is None or row[2] is None:
            return None
        return _number(max(0.0, float(row[2]) - float(row[1]) ** 2) ** 0.5)

    shift = None
    if clean[1] is not None:
        shift = 100.0 - float(clean[1])
    return {
        "year": year,
        "status": "ok",
        "score_rows": int(total[0] or 0),
        "clean_score_rows": int(clean[0] or 0),
        "excluded_position_player_score_rows": int((total[0] or 0) - (clean[0] or 0)),
        "official_mean": _number(total[1]),
        "clean_mean": _number(clean[1]),
        "official_sd": population_sd(total),
        "clean_sd": population_sd(clean),
        "clean_recenter_delta_to_100": _number(shift),
        "clean_pitchers": int(len(pitcher_rows)),
        "official_model_versions": {str(row[0]): int(row[1]) for row in versions},
        "pitcher_season_rows": [
            {"pitcher_id": int(row[0]), "pitches": int(row[1]), "stuff_plus": _number(row[2]), "recentered_stuff_plus": _number(float(row[2]) + shift) if row[2] is not None and shift is not None else None}
            for row in pitcher_rows
        ],
    }


def _load_challenger_raw(year: int, root: Path) -> pd.DataFrame:
    """Load one season with stable pitch keys needed for point-in-time joins."""

    path = get_season_duckdb_path(year, root)
    if not path.exists():
        return pd.DataFrame()
    columns = sorted(set([*STUFF_SOURCE_COLUMNS, *LOCATION_SOURCE_COLUMNS, "game_pk", "at_bat_number", "pitch_number"]))
    with duckdb.connect(str(path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        source = resolve_pitch_table(tables)
        if not source:
            return pd.DataFrame()
        available = {row[0] for row in connection.execute(f"DESCRIBE {source}").fetchall()}
        missing = [column for column in columns if column not in available]
        if missing:
            raise RuntimeError(f"Slice 8/9 source is missing columns for {year}: {', '.join(missing)}")
        frame = connection.execute(
            f"SELECT {', '.join(columns)} FROM {source} WHERE game_type = 'R' AND pitcher IS NOT NULL"
        ).fetchdf()
    frame["season"] = int(year)
    position_ids, _ = _position_player_ids(year, root)
    if position_ids:
        frame = frame[~pd.to_numeric(frame["pitcher"], errors="coerce").isin(position_ids)].copy()
    return frame.reset_index(drop=True)


def _point_in_time_fastball_frame(raw: pd.DataFrame, fallback_refs: dict[int, dict[str, float]] | None = None) -> pd.DataFrame:
    """Replace season-wide fastball references with strictly prior pitch values."""

    frame = build_stuff_training_frame(raw)
    order = [column for column in ["season", "pitcher", "game_date", "game_pk", "at_bat_number", "pitch_number"] if column in frame]
    if order:
        frame = frame.sort_values(order, kind="mergesort").reset_index(drop=True)
    fastball = frame["pitch_type"].astype(str).str.upper().isin({"FF", "SI", "FC"})
    frame["_fb_count"] = fastball.astype("int8")
    group_keys = ["season", "pitcher"]
    prior_count = frame.groupby(group_keys, sort=False)['_fb_count'].cumsum() - frame["_fb_count"]
    fallback_refs = fallback_refs or {}
    global_fallback = fallback_refs.get(-1, {})
    for source, diff in (("release_speed", "velo_diff_from_fastball"), ("ivb", "ivb_diff_from_fastball"), ("adj_hb", "hb_diff_from_fastball")):
        values = pd.to_numeric(frame[source], errors="coerce")
        contribution = values.where(fastball, 0.0).fillna(0.0)
        frame["_fb_sum"] = contribution
        prior_sum = frame.groupby(group_keys, sort=False)["_fb_sum"].cumsum() - contribution
        reference = prior_sum / prior_count.replace(0, np.nan)
        pitcher_fallback = frame["pitcher"].map(lambda pitcher: fallback_refs.get(int(pitcher), {}).get(source) if pd.notna(pitcher) else None)
        reference = reference.fillna(pitcher_fallback).fillna(global_fallback.get(source, 0.0))
        frame[diff] = values - reference
    frame = frame.drop(columns=["_fb_count", "_fb_sum"], errors="ignore")
    return frame


def _sample_with_source_support(frame: pd.DataFrame, sample_fraction: float, seed: int) -> pd.DataFrame:
    keys = ["season", "pitcher", "pitch_type", "p_throws"]
    frame = frame.copy()
    frame["source_pitch_count"] = frame.groupby(keys, dropna=False)["pitcher"].transform("size")
    if sample_fraction < 1.0:
        frame = frame.sample(frac=sample_fraction, random_state=seed)
    return frame.reset_index(drop=True)


def _stuff_scale_with_source_support(
    model: Any,
    frame: pd.DataFrame,
    contexts: list[dict[str, object]],
    temperature: float,
    run_values: dict[str, float],
    pitch_type_zone_weights: dict[str, dict[str, float]],
    global_zone_weights: dict[str, float],
    minimum_pitches: int = 50,
) -> dict[str, Any]:
    grouped = frame.groupby(["season", "pitcher", "pitch_type", "p_throws"], as_index=False).agg(
        pitches=("pitcher", "size"),
        source_pitches=("source_pitch_count", "max"),
        **{column: (column, "mean") for column in STUFF_PHYSICAL_FEATURES},
    )
    qualified = grouped[grouped["source_pitches"].ge(minimum_pitches)].copy()
    values = score_standard_contexts(
        model,
        qualified,
        contexts,
        temperature,
        run_values,
        pitch_type_zone_weights,
        global_zone_weights,
    )
    if len(values) < 2 or np.std(values) == 0:
        raise ValueError("Not enough supported pitch groups to define the Stuff+ v2 scale")
    qualified["prediction"] = values
    qualified["pitch_family"] = qualified["pitch_type"].map(PITCH_TYPE_FAMILIES).fillna("other")

    def grouped_scales(column: str, minimum_groups: int) -> dict[str, dict[str, float | int]]:
        result: dict[str, dict[str, float | int]] = {}
        for label, group in qualified.groupby(column):
            if len(group) < minimum_groups or group["prediction"].std(ddof=0) == 0:
                continue
            result[str(label)] = {
                "mean_pitcher_value": float(group["prediction"].mean()),
                "sd_pitcher_value": float(group["prediction"].std(ddof=0)),
                "qualified_pitch_groups": int(len(group)),
            }
        return result

    return {
        "mean_pitcher_value": float(np.mean(values)),
        "sd_pitcher_value": float(np.std(values)),
        "points_per_sd": 10.0,
        "minimum_pitch_type_pitches": int(minimum_pitches),
        "qualified_pitch_groups": int(len(values)),
        "pitch_type_scales": grouped_scales("pitch_type", 30),
        "pitch_family_scales": grouped_scales("pitch_family", 60),
    }


def _train_stuff_v2(
    root: Path,
    sample_fraction: float = 0.20,
    n_estimators: int = 160,
    *,
    historical_fallback: bool = False,
    model_dir_name: str = "stuff_plus_v2_research",
    model_version: str = "pete_stuff_outcome_probability_v4_point_in_time_cleaned",
) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    frames: list[pd.DataFrame] = []
    source_rows: dict[int, int] = {}
    fallback_refs: dict[int, dict[str, float]] = {}
    for year in YEARS:
        raw = _load_challenger_raw(year, root)
        source_rows[year] = int(len(raw))
        if raw.empty:
            continue
        prepared = _point_in_time_fastball_frame(raw, fallback_refs if historical_fallback else None)
        if historical_fallback:
            fastball = prepared[prepared["pitch_type"].astype(str).str.upper().isin({"FF", "SI", "FC"})]
            if not fastball.empty:
                means = fastball.groupby("pitcher")[["release_speed", "ivb", "adj_hb"]].mean()
                for pitcher, row in means.iterrows():
                    fallback_refs[int(pitcher)] = {column: float(row[column]) for column in ["release_speed", "ivb", "adj_hb"] if pd.notna(row[column])}
                global_values = fastball[["release_speed", "ivb", "adj_hb"]].mean()
                fallback_refs[-1] = {column: float(global_values[column]) for column in ["release_speed", "ivb", "adj_hb"] if pd.notna(global_values[column])}
        frames.append(_sample_with_source_support(prepared, sample_fraction, 7000 + year))
    frame = pd.concat(frames, ignore_index=True)
    retained = [*STUFF_MODEL_FEATURES, "outcome", "outcome_code", "delta_run_exp", "pitcher_value", "pitcher", "season", "source_pitch_count", "zone"]
    frame = frame[[column for column in retained if column in frame.columns]].dropna(subset=["outcome_code", "pitcher_value", *STUFF_MODEL_FEATURES]).reset_index(drop=True)
    train = frame[frame["season"].between(2021, 2024)].copy()
    validation = frame[frame["season"].eq(2025)].copy()
    test = frame[frame["season"].eq(2026)].copy()
    run_values = stuff_outcome_run_values(train)
    development_model = make_stuff_pipeline(n_estimators=n_estimators)
    development_model.fit(train[STUFF_MODEL_FEATURES], train["outcome_code"])
    classes = development_model.named_steps["model"].classes_
    validation_raw = development_model.predict_proba(validation[STUFF_MODEL_FEATURES])
    temperature = choose_stuff_temperature(validation["outcome_code"].to_numpy(dtype="int64"), validation_raw, classes)
    validation_probabilities = __import__("app.ml.stuff_plus", fromlist=["apply_temperature"]).apply_temperature(validation_raw, temperature)
    test_probabilities = __import__("app.ml.stuff_plus", fromlist=["apply_temperature"]).apply_temperature(development_model.predict_proba(test[STUFF_MODEL_FEATURES]), temperature)
    production_train = frame[frame["season"].between(2021, 2025)].copy()
    production_model = make_stuff_pipeline(n_estimators=n_estimators)
    production_model.fit(production_train[STUFF_MODEL_FEATURES], production_train["outcome_code"])
    production_run_values = stuff_outcome_run_values(production_train)
    contexts, pitch_type_zone_weights, global_zone_weights = standard_context_grid(train)
    scale = _stuff_scale_with_source_support(
        production_model,
        production_train,
        contexts,
        temperature,
        production_run_values,
        pitch_type_zone_weights,
        global_zone_weights,
    )
    model_dir = root / "models" / model_dir_name
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / ("pete_stuff_v5_prior_carryover_pipeline.joblib" if historical_fallback else "pete_stuff_v2_point_in_time_pipeline.joblib")
    metadata_path = model_dir / ("pete_stuff_v5_prior_carryover_metadata.json" if historical_fallback else "pete_stuff_v2_point_in_time_metadata.json")
    joblib.dump(production_model, model_path, compress=3)
    from app.ml.stuff_plus import apply_temperature as apply_stuff_temperature
    metadata = {
        "model_version": model_version,
        "generated_at": _now(),
        "definition": "Stuff+ challenger with position-player pitching excluded, strictly prior all-primary-fastball references, and support-qualified scale groups.",
        "cleaning_artifact": str(artifact_path(7, root)),
        "development_train_years": [2021, 2022, 2023, 2024],
        "validation_year": 2025,
        "test_year": 2026,
        "production_train_years": [2021, 2022, 2023, 2024, 2025],
        "features": STUFF_MODEL_FEATURES,
        "temperature": float(temperature),
        "run_values": production_run_values,
        "standard_contexts": contexts,
        "pitch_type_zone_weights": pitch_type_zone_weights,
        "global_zone_weights": global_zone_weights,
        "stuff_plus_scale": scale,
        "point_in_time_reference": "expanding prior FF/SI/FC mean within pitcher-season; first pitch falls back to prior-season pitcher mean when available" if historical_fallback else "expanding prior FF/SI/FC mean within pitcher-season; first pitch uses zero differential",
        "validation_metrics": evaluate_stuff(validation, apply_stuff_temperature(validation_raw, temperature), classes, run_values).__dict__,
        "test_metrics": evaluate_stuff(test, apply_stuff_temperature(development_model.predict_proba(test[STUFF_MODEL_FEATURES]), temperature), classes, run_values).__dict__,
        "rows": {"development_train": len(train), "validation": len(validation), "test": len(test), "production_train": len(production_train), "source_rows_after_cleaning": source_rows},
        "sample_fraction": sample_fraction,
        "n_estimators": n_estimators,
        "training_started_at": started.isoformat(),
        "model_path": str(model_path),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return metadata


def _location_challenger_pitch_type(pitch_code: Any, pitch_name: Any) -> str:
    canonical = canonical_pitch_code(pitch_code, pitch_name)
    if canonical:
        return canonical
    code = str(pitch_code or "").strip().upper()
    if code in {"SV", "CS"} or "slurve" in str(pitch_name or "").lower():
        return "BR"
    if code in {"KN", "EP"}:
        return "OS"
    return "OT"


def _location_scale_with_source_support(frame: pd.DataFrame, xrv: np.ndarray, minimum_pitches: int = 100) -> dict[str, Any]:
    scores = frame[["season", "pitcher", "source_pitch_count"]].copy()
    scores["xrv"] = xrv
    grouped = scores.groupby(["season", "pitcher"], as_index=False).agg(
        pitches=("xrv", "size"), source_pitches=("source_pitch_count", "max"), xrv=("xrv", "mean")
    )
    qualified = grouped.loc[grouped["source_pitches"].ge(minimum_pitches), "xrv"] * 100.0
    if len(qualified) < 2:
        raise ValueError("Not enough supported pitcher-seasons to define the Location+ v2 scale")
    return {
        "mean_xrv_per_100": float(qualified.mean()),
        "sd_xrv_per_100": float(qualified.std(ddof=0)),
        "points_per_sd": 10.0,
        "minimum_pitches": minimum_pitches,
        "qualified_pitcher_seasons": int(len(qualified)),
    }


def _train_location_v2(root: Path, sample_fraction: float = 0.20, n_estimators: int = 160) -> dict[str, Any]:
    frames: list[pd.DataFrame] = []
    source_rows: dict[int, int] = {}
    for year in YEARS:
        raw = _load_challenger_raw(year, root)
        source_rows[year] = int(len(raw))
        if raw.empty:
            continue
        raw["_challenger_pitch_code"] = [
            _location_challenger_pitch_type(code, name)
            for code, name in zip(raw["pitch_type"], raw["pitch_name"])
        ]
        prepared = build_location_training_frame(raw)
        prepared["pitch_type"] = prepared["_challenger_pitch_code"].astype(str)
        prepared = prepared.drop(columns=["_challenger_pitch_code"], errors="ignore")
        frames.append(_sample_with_source_support(prepared, sample_fraction, 9000 + year))
    frame = pd.concat(frames, ignore_index=True)
    retained = [*LOCATION_MODEL_FEATURES, "outcome", "outcome_code", "delta_run_exp", "pitcher", "season", "source_pitch_count"]
    frame = frame[retained].dropna(subset=["outcome_code", "delta_run_exp", *LOCATION_MODEL_FEATURES]).reset_index(drop=True)
    train = frame[frame["season"].between(2021, 2024)].copy()
    validation = frame[frame["season"].eq(2025)].copy()
    test = frame[frame["season"].eq(2026)].copy()
    run_values = location_outcome_run_values(train)
    development_model = make_location_pipeline(n_estimators=n_estimators)
    development_model.fit(train[LOCATION_MODEL_FEATURES], train["outcome_code"])
    classes = development_model.named_steps["model"].classes_
    validation_raw = development_model.predict_proba(validation[LOCATION_MODEL_FEATURES])
    temperature = choose_location_temperature(validation["outcome_code"].to_numpy(dtype="int64"), validation_raw, classes)
    production_train = frame[frame["season"].between(2021, 2025)].copy()
    production_model = make_location_pipeline(n_estimators=n_estimators)
    production_model.fit(production_train[LOCATION_MODEL_FEATURES], production_train["outcome_code"])
    production_run_values = location_outcome_run_values(production_train)
    production_probabilities = apply_location_temperature(production_model.predict_proba(production_train[LOCATION_MODEL_FEATURES]), temperature)
    production_xrv = np.asarray(
        __import__("app.ml.location_plus", fromlist=["expected_run_value"]).expected_run_value(
            production_probabilities,
            production_model.named_steps["model"].classes_,
            production_run_values,
        )
    )
    scale = _location_scale_with_source_support(production_train, production_xrv)
    model_dir = root / "models" / "location_plus_v2_research"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "location_plus_v2_canonical_pipeline.joblib"
    metadata_path = model_dir / "location_plus_v2_canonical_metadata.json"
    joblib.dump(production_model, model_path, compress=3)
    test_raw = development_model.predict_proba(test[LOCATION_MODEL_FEATURES])
    metadata = {
        "model_version": "location_plus_independent_v2_canonical_cleaned",
        "generated_at": _now(),
        "definition": "Location+ challenger with position-player pitching excluded and canonical pitch-code/family categories; no pitcher identity or stuff inputs.",
        "cleaning_artifact": str(artifact_path(7, root)),
        "development_train_years": [2021, 2022, 2023, 2024],
        "validation_year": 2025,
        "test_year": 2026,
        "production_train_years": [2021, 2022, 2023, 2024, 2025],
        "features": LOCATION_MODEL_FEATURES,
        "canonical_pitch_taxonomy": "FA, SI, FC, FS, SL, CU, CH, KC, FO; SV/CS/Slurve=BR; KN/EP=OS; remaining=OT",
        "temperature": float(temperature),
        "run_values": production_run_values,
        "location_plus_scale": scale,
        "validation_metrics": evaluate_location(validation, apply_location_temperature(validation_raw, temperature), classes, run_values).__dict__,
        "test_metrics": evaluate_location(test, apply_location_temperature(test_raw, temperature), classes, run_values).__dict__,
        "rows": {"development_train": len(train), "validation": len(validation), "test": len(test), "production_train": len(production_train), "source_rows_after_cleaning": source_rows},
        "sample_fraction": sample_fraction,
        "n_estimators": n_estimators,
        "model_path": str(model_path),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return metadata


def _prediction_summary(
    frame: pd.DataFrame,
    probabilities: np.ndarray,
    classes: np.ndarray,
    run_values: dict[str, float],
    target_column: str,
    lower_is_better: bool,
    calibration_fn: Any,
) -> dict[str, Any]:
    y_true = frame["outcome_code"].to_numpy(dtype="int64")
    class_index = {int(label): index for index, label in enumerate(classes)}
    one_hot = np.zeros_like(probabilities)
    for row, label in enumerate(y_true):
        if int(label) in class_index:
            one_hot[row, class_index[int(label)]] = 1.0
    actual = pd.to_numeric(frame[target_column], errors="coerce").to_numpy(dtype="float64")
    if lower_is_better:
        predicted = -stuff_expected_run_value(probabilities, classes, run_values)
    else:
        predicted = location_expected_run_value(probabilities, classes, run_values)
    valid = np.isfinite(actual) & np.isfinite(predicted)
    correlation = None
    if valid.sum() > 1 and np.std(actual[valid]) > 0 and np.std(predicted[valid]) > 0:
        correlation = float(np.corrcoef(actual[valid], predicted[valid])[0, 1])
    return {
        "rows": int(len(frame)),
        "log_loss": float(-np.mean(np.log(np.clip(probabilities[np.arange(len(y_true)), [class_index.get(int(label), 0) for label in y_true]], 1e-12, 1.0)))),
        "brier_score": float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1))),
        "calibration_error": float(calibration_fn(y_true, probabilities, classes)),
        "run_value_mae": float(np.mean(np.abs(actual[valid] - predicted[valid]))) if valid.any() else None,
        "run_value_correlation": correlation,
    }


def _subgroup_diagnostics(
    frame: pd.DataFrame,
    baseline_probabilities: np.ndarray,
    challenger_probabilities: np.ndarray,
    classes: np.ndarray,
    dimensions: tuple[str, ...],
    calibration_fn: Any,
    minimum_rows: int = 1000,
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    y_true = frame["outcome_code"].to_numpy(dtype="int64")
    class_index = {int(label): index for index, label in enumerate(classes)}
    one_hot = np.zeros_like(baseline_probabilities)
    for row, label in enumerate(y_true):
        if int(label) in class_index:
            one_hot[row, class_index[int(label)]] = 1.0
    for dimension in dimensions:
        if dimension not in frame.columns:
            continue
        entries: list[dict[str, Any]] = []
        for label, indexes in frame.groupby(dimension, dropna=False).groups.items():
            indexes = np.asarray(list(indexes), dtype=int)
            if len(indexes) < minimum_rows:
                continue
            baseline = baseline_probabilities[indexes]
            challenger = challenger_probabilities[indexes]
            actual = y_true[indexes]
            base_one_hot = one_hot[indexes]
            entries.append(
                {
                    "group": str(label),
                    "rows": int(len(indexes)),
                    "baseline_calibration_error": float(calibration_fn(actual, baseline, classes)),
                    "challenger_calibration_error": float(calibration_fn(actual, challenger, classes)),
                    "calibration_delta": float(calibration_fn(actual, challenger, classes) - calibration_fn(actual, baseline, classes)),
                    "baseline_brier": float(np.mean(np.sum((baseline - base_one_hot) ** 2, axis=1))),
                    "challenger_brier": float(np.mean(np.sum((challenger - base_one_hot) ** 2, axis=1))),
                    "brier_delta": float(np.mean(np.sum((challenger - base_one_hot) ** 2, axis=1)) - np.mean(np.sum((baseline - base_one_hot) ** 2, axis=1))),
                }
            )
        output[dimension] = entries
    all_entries = [entry for entries in output.values() for entry in entries]
    return {
        "minimum_rows": minimum_rows,
        "dimensions": output,
        "supported_groups": len(all_entries),
        "worst_calibration_delta": max((float(entry["calibration_delta"]) for entry in all_entries), default=None),
        "worst_brier_delta": max((float(entry["brier_delta"]) for entry in all_entries), default=None),
        "material_calibration_regressions": int(sum(float(entry["calibration_delta"]) > 0.02 for entry in all_entries)),
    }


def _prepare_test_frames(root: Path, sample_fraction: float = 0.20) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw = _load_challenger_raw(2026, root)
    if 0 < sample_fraction < 1:
        raw = raw.sample(frac=sample_fraction, random_state=202610).reset_index(drop=True)
    challenger_stuff = _point_in_time_fastball_frame(raw)
    baseline_stuff = build_stuff_training_frame(raw)
    raw["_challenger_pitch_code"] = [
        _location_challenger_pitch_type(code, name)
        for code, name in zip(raw["pitch_type"], raw["pitch_name"])
    ]
    challenger_location = build_location_training_frame(raw)
    challenger_location["pitch_type"] = challenger_location["_challenger_pitch_code"].astype(str)
    challenger_location = challenger_location.drop(columns=["_challenger_pitch_code"], errors="ignore")
    baseline_location = build_location_training_frame(raw.drop(columns=["_challenger_pitch_code"], errors="ignore"))
    return baseline_stuff, challenger_stuff, baseline_location, challenger_location


def _prediction_frame(
    model_path: Path,
    frame: pd.DataFrame,
    feature_columns: list[str],
    temperature: float,
    apply_temperature_fn: Any,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    model = joblib.load(model_path)
    usable = frame.dropna(subset=[*feature_columns, "outcome_code"]).copy()
    probabilities = apply_temperature_fn(model.predict_proba(usable[feature_columns]), temperature)
    classes = model.named_steps["model"].classes_
    keys = [column for column in ["game_pk", "at_bat_number", "pitch_number", "pitcher"] if column in usable.columns]
    if keys:
        usable["_pitch_key"] = usable[keys].astype(str).agg("|".join, axis=1)
    else:
        usable["_pitch_key"] = usable.index.astype(str)
    return usable.reset_index(drop=True), probabilities, classes


def build_slice8(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    audit = build_slice7(root)
    yearly = []
    for year in YEARS:
        position_ids, _ = _position_player_ids(year, root)
        row = _score_cache_summary(year, root, position_ids)
        raw = next((item for item in audit["yearly"] if int(item.get("year", -1)) == year), {})
        raw_rows = int(raw.get("pitch_rows") or 0)
        row["source_pitch_rows"] = raw_rows
        row["score_coverage_pct_of_source"] = _number(float(row.get("clean_score_rows") or 0) / raw_rows * 100.0) if raw_rows else None
        yearly.append(row)
    metadata_path = root / "models" / "stuff_plus" / "pete_stuff_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    result = {
        "artifact": "plus_v2_slice8_stuff_scale_challenger",
        "version": PLUS_V2_VERSION,
        "generated_at": _now(),
        "scope": "cleaned point-in-time Stuff+ refit challenger, 2021-2026",
        "challenger_type": "refit challenger; no production promotion",
        "baseline_model_version": metadata.get("model_version"),
        "baseline_metadata_path": str(metadata_path),
        "method": "exclude position-player pitching, use strictly prior FF/SI/FC references within pitcher-season, train a separate outcome model, and qualify scale groups using unsampled source support",
        "yearly": yearly,
    }
    refit = _train_stuff_v2(root)
    result["refit"] = {
        "status": "complete",
        "model_version": refit.get("model_version"),
        "model_path": refit.get("model_path"),
        "validation_metrics": refit.get("validation_metrics"),
        "test_metrics": refit.get("test_metrics"),
        "rows": refit.get("rows"),
        "point_in_time_reference": refit.get("point_in_time_reference"),
        "scale": refit.get("stuff_plus_scale"),
    }
    _write_json(artifact_path(8, root), result)
    return result


def build_slice8b(data_dir: Path | None = None) -> dict[str, Any]:
    """Train the Stuff+ prior-carryover revision without touching Slice 8 v2."""

    root = Path(data_dir or settings.data_dir)
    baseline_path = root / "models" / "stuff_plus" / "pete_stuff_metadata.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.exists() else {}
    refit = _train_stuff_v2(
        root,
        sample_fraction=0.35,
        n_estimators=180,
        historical_fallback=True,
        model_dir_name="stuff_plus_v2_research_v5",
        model_version="pete_stuff_outcome_probability_v5_prior_carryover_cleaned",
    )
    result = {
        "artifact": "plus_v2_slice8b_stuff_prior_carryover_challenger",
        "version": PLUS_V2_VERSION,
        "generated_at": _now(),
        "scope": "2021-2026 cleaned point-in-time Stuff+ revision",
        "challenger_type": "prior-carryover refit challenger; no production promotion",
        "baseline_model_version": baseline.get("model_version"),
        "baseline_test_metrics": baseline.get("test_metrics"),
        "method": "position-player exclusion, strictly prior within-season FF/SI/FC reference, previous-season pitcher fastball carry-over fallback, 35% deterministic training sample, and raw source-support scale qualification",
        "refit": {
            "status": "complete",
            "model_version": refit.get("model_version"),
            "model_path": refit.get("model_path"),
            "validation_metrics": refit.get("validation_metrics"),
            "test_metrics": refit.get("test_metrics"),
            "rows": refit.get("rows"),
            "point_in_time_reference": refit.get("point_in_time_reference"),
            "scale": refit.get("stuff_plus_scale"),
        },
    }
    _write_json(root / "derived" / "plus_v2_slice8b.json", result)
    return result


def _location_summary(year: int, root: Path, position_ids: set[int]) -> dict[str, Any]:
    path = root / "derived" / "location_plus_scores.duckdb"
    if not path.exists():
        return {"year": year, "status": "missing_location_cache"}
    with duckdb.connect(str(path), read_only=True) as connection:
        table = f"location_pitch_scores_{year}"
        if table not in {row[0] for row in connection.execute("SHOW TABLES").fetchall()}:
            return {"year": year, "status": "missing_location_table"}
        where, params = _sql_in("pitcher_id", position_ids)
        rows = connection.execute(
            f"SELECT pitch_name, pitch_code, pitcher_id, 1 AS pitches, location_plus_pitch FROM {table} WHERE {where} AND location_plus_pitch IS NOT NULL",
            params,
        ).fetchall()
        current = connection.execute(
            f"SELECT pitcher_id, pitches, location_plus FROM location_pitcher_scores_{year} WHERE pitcher_id IS NOT NULL"
        ).fetchall()
    canonical_counts: Counter[str] = Counter()
    raw_names: Counter[str] = Counter()
    weighted_by_pitcher: dict[int, list[float]] = {}
    for name, code, pitcher_id, pitches, score in rows:
        canonical = canonical_pitch_code(code, name)
        raw_names[str(name)] += int(pitches or 0)
        if canonical:
            canonical_counts[canonical] += int(pitches or 0)
            weighted_by_pitcher.setdefault(int(pitcher_id), []).append((float(score), int(pitches or 0)))
    cleaned_pitcher = {
        pitcher: sum(score * pitches for score, pitches in values) / sum(pitches for _, pitches in values)
        for pitcher, values in weighted_by_pitcher.items()
        if sum(pitches for _, pitches in values) > 0
    }
    current_map = {int(row[0]): (int(row[1] or 0), _number(row[2])) for row in current}
    deltas = [cleaned_pitcher[p] - current_map[p][1] for p in cleaned_pitcher if p in current_map and current_map[p][1] is not None]
    merged = canonical_counts.get("SL", 0)
    return {
        "year": year,
        "status": "ok",
        "location_pitch_rows": int(sum(canonical_counts.values())),
        "raw_pitch_name_groups": len(raw_names),
        "canonical_groups": len(canonical_counts),
        "canonical_pitch_counts": dict(sorted(canonical_counts.items())),
        "slider_sweeper_canonical_rows": int(merged),
        "unmapped_location_rows": int(sum(raw_names.values()) - sum(canonical_counts.values())),
        "clean_pitchers": len(cleaned_pitcher),
        "current_pitcher_rows": len(current_map),
        "clean_vs_current_pitcher_delta": {
            "mean": _number(np.mean(deltas)) if deltas else None,
            "mean_abs": _number(np.mean(np.abs(deltas))) if deltas else None,
            "p95_abs": _number(np.quantile(np.abs(deltas), 0.95)) if deltas else None,
            "matched_pitchers": len(deltas),
        },
    }


def build_slice9(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    yearly = []
    for year in YEARS:
        position_ids, _ = _position_player_ids(year, root)
        yearly.append(_location_summary(year, root, position_ids))
    metadata_path = root / "models" / "location_plus" / "location_plus_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    result = {
        "artifact": "plus_v2_slice9_location_taxonomy_challenger",
        "version": PLUS_V2_VERSION,
        "generated_at": _now(),
        "scope": "cleaned canonical Location+ refit challenger, 2021-2026",
        "challenger_type": "refit challenger; no production promotion",
        "baseline_model_version": metadata.get("model_version"),
        "baseline_metadata_path": str(metadata_path),
        "method": "exclude position-player pitching, use canonical pitch-code/family categories as model features, retain count/handedness/base-out context, and compare fixed 2026 test metrics to the v1 contract",
        "yearly": yearly,
    }
    refit = _train_location_v2(root)
    result["refit"] = {
        "status": "complete",
        "model_version": refit.get("model_version"),
        "model_path": refit.get("model_path"),
        "validation_metrics": refit.get("validation_metrics"),
        "test_metrics": refit.get("test_metrics"),
        "rows": refit.get("rows"),
        "canonical_pitch_taxonomy": refit.get("canonical_pitch_taxonomy"),
        "scale": refit.get("location_plus_scale"),
    }
    _write_json(artifact_path(9, root), result)
    return result


def build_slice10(data_dir: Path | None = None) -> dict[str, Any]:
    """Run the fixed 2026 calibration/subgroup release gate for both challengers."""

    root = Path(data_dir or settings.data_dir)
    stuff_baseline_metadata_path = root / "models" / "stuff_plus" / "pete_stuff_metadata.json"
    stuff_challenger_metadata_path = root / "models" / "stuff_plus_v2_research" / "pete_stuff_v2_point_in_time_metadata.json"
    location_baseline_metadata_path = root / "models" / "location_plus" / "location_plus_metadata.json"
    location_challenger_metadata_path = root / "models" / "location_plus_v2_research" / "location_plus_v2_canonical_metadata.json"
    paths = [stuff_baseline_metadata_path, stuff_challenger_metadata_path, location_baseline_metadata_path, location_challenger_metadata_path]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Slice 10 requires completed Slice 8/9 metadata: {', '.join(missing)}")
    stuff_baseline_metadata = json.loads(stuff_baseline_metadata_path.read_text(encoding="utf-8"))
    stuff_challenger_metadata = json.loads(stuff_challenger_metadata_path.read_text(encoding="utf-8"))
    location_baseline_metadata = json.loads(location_baseline_metadata_path.read_text(encoding="utf-8"))
    location_challenger_metadata = json.loads(location_challenger_metadata_path.read_text(encoding="utf-8"))
    test_sample_fraction = 0.02
    baseline_stuff_frame, challenger_stuff_frame, baseline_location_frame, challenger_location_frame = _prepare_test_frames(root, test_sample_fraction)

    def compare(
        baseline_frame: pd.DataFrame,
        challenger_frame: pd.DataFrame,
        baseline_model_path: Path,
        challenger_model_path: Path,
        baseline_metadata: dict[str, Any],
        challenger_metadata: dict[str, Any],
        feature_columns: list[str],
        target_column: str,
        lower_is_better: bool,
        calibration_fn: Any,
        group_dimensions: tuple[str, ...],
    ) -> dict[str, Any]:
        base, base_probabilities, base_classes = _prediction_frame(
            baseline_model_path,
            baseline_frame,
            feature_columns,
            float(baseline_metadata["temperature"]),
            apply_location_temperature if not lower_is_better else __import__("app.ml.stuff_plus", fromlist=["apply_temperature"]).apply_temperature,
        )
        challenger, challenger_probabilities, challenger_classes = _prediction_frame(
            challenger_model_path,
            challenger_frame,
            feature_columns,
            float(challenger_metadata["temperature"]),
            apply_location_temperature if not lower_is_better else __import__("app.ml.stuff_plus", fromlist=["apply_temperature"]).apply_temperature,
        )
        base_order = base["_pitch_key"].sort_values().to_numpy()
        challenger_order = challenger["_pitch_key"].sort_values().to_numpy()
        common_keys = np.intersect1d(base_order, challenger_order)
        aligned = base.loc[base["_pitch_key"].isin(common_keys)].copy().sort_values("_pitch_key").reset_index(drop=True)
        challenger_aligned = challenger.loc[challenger["_pitch_key"].isin(common_keys)].copy().sort_values("_pitch_key").reset_index(drop=True)
        base_pos = np.array([int(base["_pitch_key"].eq(key).to_numpy().nonzero()[0][0]) for key in aligned["_pitch_key"]])
        challenger_pos = np.array([int(challenger["_pitch_key"].eq(key).to_numpy().nonzero()[0][0]) for key in aligned["_pitch_key"]])
        base_prob = base_probabilities[base_pos]
        challenger_prob = challenger_probabilities[challenger_pos]
        if target_column == "delta_run_exp":
            aligned["pitch_family"] = aligned["pitch_name"].map(lambda value: PITCH_TYPE_FAMILIES.get(canonical_pitch_code(None, value), "other"))
        else:
            aligned["pitch_family"] = aligned["pitch_type"].map(PITCH_TYPE_FAMILIES).fillna("other")
        aligned["count"] = aligned["balls"].astype(str) + "-" + aligned["strikes"].astype(str)
        baseline_metrics = _prediction_summary(aligned, base_prob, base_classes, {str(k): float(v) for k, v in baseline_metadata["run_values"].items()}, target_column, lower_is_better, calibration_fn)
        challenger_metrics = _prediction_summary(aligned, challenger_prob, challenger_classes, {str(k): float(v) for k, v in challenger_metadata["run_values"].items()}, target_column, lower_is_better, calibration_fn)
        subgroup = _subgroup_diagnostics(aligned, base_prob, challenger_prob, base_classes, group_dimensions, calibration_fn, minimum_rows=1000)
        deltas = {
            key: float(challenger_metrics[key] - baseline_metrics[key])
            for key in ["log_loss", "brier_score", "calibration_error"]
        }
        criteria = {
            "log_loss_delta_max": 0.01,
            "brier_delta_max": 0.005,
            "calibration_error_delta_max": 0.005,
            "subgroup_calibration_delta_max": 0.02,
            "material_subgroup_regressions_max": 0,
        }
        checks = {
            "log_loss_non_inferiority": deltas["log_loss"] <= criteria["log_loss_delta_max"],
            "brier_non_inferiority": deltas["brier_score"] <= criteria["brier_delta_max"],
            "calibration_non_inferiority": deltas["calibration_error"] <= criteria["calibration_error_delta_max"],
            "subgroup_calibration_non_inferiority": (subgroup["worst_calibration_delta"] is None or subgroup["worst_calibration_delta"] <= criteria["subgroup_calibration_delta_max"]),
            "no_material_subgroup_regressions": subgroup["material_calibration_regressions"] <= criteria["material_subgroup_regressions_max"],
        }
        return {
            "matched_test_rows": int(len(aligned)),
            "baseline": baseline_metrics,
            "challenger": challenger_metrics,
            "deltas_challenger_minus_baseline": deltas,
            "subgroups": subgroup,
            "release_gate": {"criteria": criteria, "checks": checks, "passed": bool(all(checks.values())), "decision": "eligible_for_shadow" if all(checks.values()) else "research_only"},
        }

    stuff_result = compare(
        baseline_stuff_frame,
        challenger_stuff_frame,
        root / "models" / "stuff_plus" / "pete_stuff_pipeline.joblib",
        root / "models" / "stuff_plus_v2_research" / "pete_stuff_v2_point_in_time_pipeline.joblib",
        stuff_baseline_metadata,
        stuff_challenger_metadata,
        STUFF_MODEL_FEATURES,
        "pitcher_value",
        True,
        stuff_calibration_error,
        ("pitch_family", "stand", "count"),
    )
    location_result = compare(
        baseline_location_frame,
        challenger_location_frame,
        root / "models" / "location_plus" / "location_plus_pipeline.joblib",
        root / "models" / "location_plus_v2_research" / "location_plus_v2_canonical_pipeline.joblib",
        location_baseline_metadata,
        location_challenger_metadata,
        LOCATION_MODEL_FEATURES,
        "delta_run_exp",
        False,
        location_calibration_error,
        ("pitch_family", "stand", "count"),
    )
    result = {
        "artifact": "plus_v2_slice10_calibration_subgroup_release_gate",
        "version": PLUS_V2_VERSION,
        "generated_at": _now(),
        "scope": "fixed 2026 test; baseline versus Slice 8/9 challengers",
        "test_sampling": {"fraction": test_sample_fraction, "random_state": 202610, "reason": "deterministic paired release-gate audit sample; full model fitting and Slice 8/9 fixed metrics remain unchanged"},
        "production_impact": "none; gate result controls shadow eligibility only",
        "criteria_note": "A challenger may enter shadow monitoring only if it is non-inferior within the fixed tolerances and has no material supported subgroup calibration regression.",
        "stuff_plus": stuff_result,
        "location_plus": location_result,
        "overall_decision": "eligible_for_shadow" if stuff_result["release_gate"]["passed"] and location_result["release_gate"]["passed"] else "research_only",
    }
    _write_json(artifact_path(10, root), result)
    return result


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def build_slices_7_9(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    return {"slice7": build_slice7(root), "slice8": build_slice8(root), "slice9": build_slice9(root)}
