from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.core.config import settings


CONTRACT_VERSION = "stamina_physical_signal_contract_v1"
MODEL_VERSION = "physical_stability_challenger_v1"
DEVELOPMENT_YEAR = 2023
MINIMUM_EARLY_EXACT_PITCHES = 3
MINIMUM_LATE_PITCHES = 15
MINIMUM_COMPONENT_COVERAGE = 0.75
WINDOWS = [(21, 40, "21–40"), (41, 60, "41–60"), (61, 80, "61–80"), (81, 100, "81–100")]
SIGNALS = {
    "velocity": {
        "label": "Velocity",
        "column": "velocity_drift",
        "unit": "mph",
        "weight": 0.25,
        "definition": "Absolute release-speed change from the same appearance's first-20 exact-pitch-type mean.",
    },
    "spin": {
        "label": "Spin vector",
        "column": "spin_drift",
        "unit": "rpm-vector",
        "weight": 0.15,
        "definition": "Distance from the early spin vector built from spin rate and circular spin axis.",
    },
    "movement": {
        "label": "Movement",
        "column": "movement_drift",
        "unit": "inches",
        "weight": 0.20,
        "definition": "Horizontal/vertical movement-vector distance from the early exact-type centroid.",
    },
    "release_point": {
        "label": "Release point",
        "column": "release_point_drift",
        "unit": "inches",
        "weight": 0.20,
        "definition": "Horizontal/vertical release-point distance from the early exact-type centroid.",
    },
    "extension": {
        "label": "Extension",
        "column": "extension_drift",
        "unit": "inches",
        "weight": 0.10,
        "definition": "Absolute extension change from the early exact-type mean.",
    },
    "arm_angle": {
        "label": "Arm angle",
        "column": "arm_angle_drift",
        "unit": "degrees",
        "weight": 0.10,
        "definition": "Absolute arm-angle change from the early exact-type mean; date-batch missingness remains null.",
    },
}
SOURCE_COLUMNS = [
    "pitcher", "player_name", "pitcher_team", "game_pk", "game_date", "appearance_role",
    "appearance_pitch_number", "pitch_type", "pitch_family", "release_speed", "pfx_x", "pfx_z",
    "release_spin_rate", "spin_axis", "release_extension", "release_pos_x", "release_pos_z", "arm_angle",
]


def physical_contract_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_physical_contract_{int(year)}.json"


def physical_window_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_physical_windows_{int(year)}.parquet"


def physical_game_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"stamina_physical_games_{int(year)}.parquet"


def _stamina_dataset_path(year: int, root: Path) -> Path:
    return root / "derived" / f"stamina_lab_{int(year)}.parquet"


def _write_parquet_atomic(frame: pd.DataFrame, path: Path, relation_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.parquet")
    with duckdb.connect() as connection:
        connection.register(relation_name, frame)
        target = str(temporary).replace("'", "''")
        connection.execute(f"COPY {relation_name} TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        connection.unregister(relation_name)
    temporary.replace(path)


def _load_source(year: int, root: Path) -> pd.DataFrame:
    path = _stamina_dataset_path(year, root)
    if not path.exists():
        raise FileNotFoundError(f"Required Stamina dataset not found: {path}")
    with duckdb.connect() as connection:
        return connection.execute(
            f"SELECT {', '.join(SOURCE_COLUMNS)} FROM read_parquet(?) "
            "WHERE appearance_role = 'SP' AND appearance_pitch_number BETWEEN 1 AND 100 "
            "AND pitch_family IS NOT NULL",
            [str(path)],
        ).fetchdf()


def _window_label(values: pd.Series) -> pd.Series:
    result = pd.Series(pd.NA, index=values.index, dtype="string")
    for low, high, label in WINDOWS:
        result = result.mask(values.between(low, high), label)
    return result


def _display_name(value: object) -> str:
    text = str(value or "").strip()
    if "," not in text:
        return text
    last, first = [part.strip() for part in text.split(",", 1)]
    return f"{first} {last}".strip()


def _build_raw_windows(frame: pd.DataFrame, year: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    working = frame.copy()
    working["player_name"] = working["player_name"].map(_display_name)
    numeric_columns = [
        "appearance_pitch_number", "release_speed", "pfx_x", "pfx_z", "release_spin_rate", "spin_axis",
        "release_extension", "release_pos_x", "release_pos_z", "arm_angle",
    ]
    for column in numeric_columns:
        working[column] = pd.to_numeric(working[column], errors="coerce")
    angle = np.deg2rad(working["spin_axis"])
    working["spin_x"] = working["release_spin_rate"] * np.cos(angle)
    working["spin_y"] = working["release_spin_rate"] * np.sin(angle)

    baseline_columns = [
        "release_speed", "pfx_x", "pfx_z", "spin_x", "spin_y", "release_extension",
        "release_pos_x", "release_pos_z", "arm_angle",
    ]
    early = working[working["appearance_pitch_number"].le(20)]
    baseline = early.groupby(["pitcher", "game_pk", "pitch_type"], as_index=False).agg(
        reference_pitches=("pitch_type", "size"),
        **{f"early_{column}": (column, "mean") for column in baseline_columns},
    )
    working = working.merge(baseline, on=["pitcher", "game_pk", "pitch_type"], how="left", validate="many_to_one")
    supported = working["reference_pitches"].fillna(0).ge(MINIMUM_EARLY_EXACT_PITCHES)
    working["velocity_drift"] = (working["release_speed"] - working["early_release_speed"]).abs().where(supported)
    working["spin_drift"] = np.hypot(
        working["spin_x"] - working["early_spin_x"], working["spin_y"] - working["early_spin_y"]
    ).where(supported)
    working["movement_drift"] = (
        np.hypot(working["pfx_x"] - working["early_pfx_x"], working["pfx_z"] - working["early_pfx_z"]) * 12.0
    ).where(supported)
    working["release_point_drift"] = (
        np.hypot(
            working["release_pos_x"] - working["early_release_pos_x"],
            working["release_pos_z"] - working["early_release_pos_z"],
        ) * 12.0
    ).where(supported)
    working["extension_drift"] = (
        (working["release_extension"] - working["early_release_extension"]).abs() * 12.0
    ).where(supported)
    working["arm_angle_drift"] = (working["arm_angle"] - working["early_arm_angle"]).abs().where(supported)
    working["analysis_bucket"] = _window_label(working["appearance_pitch_number"])
    late = working[working["analysis_bucket"].notna()].copy()
    late["supported_pitch"] = supported.loc[late.index].astype(int)

    aggregations: dict[str, tuple[str, str]] = {
        "pitcher_name": ("player_name", "first"), "team": ("pitcher_team", "first"),
        "total_pitches": ("pitcher", "size"), "supported_pitches": ("supported_pitch", "sum"),
        "exact_pitch_types": ("pitch_type", "nunique"),
    }
    for signal in SIGNALS.values():
        column = str(signal["column"])
        aggregations[column] = (column, "mean")
        aggregations[f"{column}_pitches"] = (column, "count")
    windows = late.groupby(
        ["pitcher", "game_pk", "game_date", "analysis_bucket"], as_index=False
    ).agg(**aggregations)
    order = {label: index for index, (_, _, label) in enumerate(WINDOWS, start=1)}
    windows["order"] = windows["analysis_bucket"].map(order).astype(int)
    windows["year"] = int(year)
    windows["support_pct"] = windows["supported_pitches"] / windows["total_pitches"].clip(lower=1) * 100.0
    coverage = {
        key: round(float(windows[f"{spec['column']}_pitches"].sum() / windows["total_pitches"].sum() * 100.0), 1)
        for key, spec in SIGNALS.items()
    }
    audit = {
        "year": int(year), "pitches": int(len(working)),
        "appearances": int(working[["pitcher", "game_pk"]].drop_duplicates().shape[0]),
        "pitchers": int(working["pitcher"].nunique()), "window_rows": int(len(windows)),
        "supported_late_pitches": int(windows["supported_pitches"].sum()),
        "late_pitches": int(windows["total_pitches"].sum()),
        "supported_late_pct": round(float(windows["supported_pitches"].sum() / max(windows["total_pitches"].sum(), 1) * 100.0), 1),
        "signal_coverage_pct": coverage,
    }
    return windows, audit


def _robust_center_scale(values: pd.Series) -> tuple[float, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return 0.0, 1.0
    center = float(clean.median())
    scale = float((clean - center).abs().median() * 1.4826)
    if not np.isfinite(scale) or scale < 1e-6:
        scale = max(float(clean.std(ddof=1)), 1.0)
    return center, scale


def _fit_reference(development: pd.DataFrame) -> dict[str, Any]:
    signal_parameters: dict[str, dict[str, dict[str, float]]] = {}
    for key, spec in SIGNALS.items():
        column = str(spec["column"])
        signal_parameters[key] = {}
        for _, _, bucket in WINDOWS:
            center, scale = _robust_center_scale(
                development.loc[development["analysis_bucket"].eq(bucket), column]
            )
            signal_parameters[key][bucket] = {"center": center, "scale": scale}
    scored = _apply_signal_reference(development.copy(), {"signals": signal_parameters})
    center, scale = _robust_center_scale(scored["composite_instability"])
    scored["raw_physical_stability_plus"] = 100.0 - 10.0 * (scored["composite_instability"] - center) / scale
    game_raw = _aggregate_raw_games(scored)
    game_center, game_scale = _robust_center_scale(game_raw["raw_game_score"])
    within = scored.groupby(["pitcher", "game_pk"])["raw_physical_stability_plus"].var(ddof=1).dropna()
    within_variance = max(float(within.median()) if len(within) else 25.0, 9.0)
    game_scores = 100.0 - 10.0 * (game_raw["raw_game_score"] - game_center) / game_scale
    between_variance = max(float(game_scores.var(ddof=1)) - within_variance / 2.0, 9.0)
    median_window_pitches = max(float(scored["supported_pitches"].median()), 5.0)
    return {
        "development_year": DEVELOPMENT_YEAR, "signals": signal_parameters,
        "window_composite_center": center, "window_composite_scale": scale,
        "game_score_center": game_center, "game_score_scale": game_scale,
        "within_variance": within_variance, "between_variance": between_variance,
        "median_window_pitches": median_window_pitches,
    }


def _apply_signal_reference(frame: pd.DataFrame, reference: dict[str, Any]) -> pd.DataFrame:
    result = frame.copy()
    weighted = np.zeros(len(result), dtype="float64")
    coverage = np.zeros(len(result), dtype="float64")
    for key, spec in SIGNALS.items():
        column = str(spec["column"])
        weight = float(spec["weight"])
        z = pd.Series(np.nan, index=result.index, dtype="float64")
        for _, _, bucket in WINDOWS:
            parameters = reference["signals"][key][bucket]
            mask = result["analysis_bucket"].eq(bucket) & result[column].notna()
            z.loc[mask] = ((result.loc[mask, column] - parameters["center"]) / parameters["scale"]).clip(-4.0, 4.0)
        result[f"{key}_z"] = z
        result[f"{key}_plus"] = 100.0 - 10.0 * z
        valid = z.notna().to_numpy()
        weighted += np.where(valid, weight * z.fillna(0.0).to_numpy(), 0.0)
        coverage += np.where(valid, weight, 0.0)
    result["component_coverage"] = coverage
    result["composite_instability"] = weighted
    return result


def _aggregate_raw_games(windows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (pitcher, game_pk), group in windows.groupby(["pitcher", "game_pk"], sort=False):
        weights = group["supported_pitches"].clip(lower=1).to_numpy(dtype="float64")
        row: dict[str, Any] = {
            "pitcher": int(pitcher), "game_pk": int(game_pk), "game_date": group["game_date"].iloc[0],
            "pitcher_name": str(group["pitcher_name"].iloc[0]), "team": str(group["team"].iloc[0]),
            "year": int(group["year"].iloc[0]), "windows": int(len(group)),
            "late_pitches": int(group["total_pitches"].sum()),
            "supported_pitches": int(group["supported_pitches"].sum()),
            "component_coverage": float(np.average(group["component_coverage"], weights=weights)),
            "raw_game_score": float(np.average(group["composite_instability"], weights=weights)),
        }
        for key in SIGNALS:
            valid = group[f"{key}_z"].notna()
            row[f"{key}_plus"] = (
                float(100.0 - 10.0 * np.average(group.loc[valid, f"{key}_z"], weights=weights[valid.to_numpy()]))
                if valid.any() else np.nan
            )
        rows.append(row)
    return pd.DataFrame(rows)


def _score_year(raw_windows: pd.DataFrame, reference: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    windows = _apply_signal_reference(raw_windows, reference)
    windows["raw_physical_stability_plus"] = 100.0 - 10.0 * (
        windows["composite_instability"] - reference["window_composite_center"]
    ) / reference["window_composite_scale"]
    window_sampling = (
        reference["within_variance"] * reference["median_window_pitches"]
        / windows["supported_pitches"].clip(lower=1)
        / windows["component_coverage"].clip(lower=0.25).pow(2)
    )
    windows["reliability"] = reference["between_variance"] / (reference["between_variance"] + window_sampling)
    windows["physical_stability_plus"] = 100.0 + windows["reliability"] * (windows["raw_physical_stability_plus"] - 100.0)
    posterior_variance = reference["between_variance"] * window_sampling / (reference["between_variance"] + window_sampling)
    halfwidth = 1.281552 * np.sqrt(posterior_variance)
    windows["ci_low"] = windows["physical_stability_plus"] - halfwidth
    windows["ci_high"] = windows["physical_stability_plus"] + halfwidth
    windows["eligible"] = (
        windows["supported_pitches"].ge(5) & windows["component_coverage"].ge(MINIMUM_COMPONENT_COVERAGE)
    )

    games = _aggregate_raw_games(windows)
    games["raw_physical_stability_plus"] = 100.0 - 10.0 * (
        games["raw_game_score"] - reference["game_score_center"]
    ) / reference["game_score_scale"]
    effective_windows = games["windows"].clip(lower=1)
    game_sampling = (
        reference["within_variance"] / effective_windows
        * reference["median_window_pitches"] * effective_windows / games["supported_pitches"].clip(lower=1)
        / games["component_coverage"].clip(lower=0.25).pow(2)
    )
    games["reliability"] = reference["between_variance"] / (reference["between_variance"] + game_sampling)
    games["physical_stability_plus"] = 100.0 + games["reliability"] * (games["raw_physical_stability_plus"] - 100.0)
    game_posterior_variance = reference["between_variance"] * game_sampling / (reference["between_variance"] + game_sampling)
    game_halfwidth = 1.281552 * np.sqrt(game_posterior_variance)
    games["ci_low"] = games["physical_stability_plus"] - game_halfwidth
    games["ci_high"] = games["physical_stability_plus"] + game_halfwidth
    games["eligible"] = (
        games["supported_pitches"].ge(MINIMUM_LATE_PITCHES)
        & games["component_coverage"].ge(MINIMUM_COMPONENT_COVERAGE)
    )
    games["confidence"] = np.select(
        [games["reliability"].ge(0.75), games["reliability"].ge(0.50)], ["high", "medium"], default="low"
    )
    games = games.sort_values(["pitcher", "game_date", "game_pk"], kind="stable")
    games["season_start_number"] = games.groupby("pitcher").cumcount() + 1
    for column in ["physical_stability_plus", "raw_physical_stability_plus", "ci_low", "ci_high", "reliability"]:
        windows[column] = pd.to_numeric(windows[column], errors="coerce").round(4)
        games[column] = pd.to_numeric(games[column], errors="coerce").round(4)
    return windows, games


def _spearman(left: pd.Series, right: pd.Series) -> float | None:
    sample = pd.concat([left, right], axis=1).dropna()
    if len(sample) < 3 or sample.iloc[:, 0].nunique() < 2 or sample.iloc[:, 1].nunique() < 2:
        return None
    return float(sample.iloc[:, 0].corr(sample.iloc[:, 1], method="spearman"))


def refresh_physical_stability(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    years = [candidate for candidate in range(DEVELOPMENT_YEAR, int(year) + 1) if _stamina_dataset_path(candidate, root).exists()]
    if DEVELOPMENT_YEAR not in years:
        raise FileNotFoundError(f"Physical Stability+ requires the {DEVELOPMENT_YEAR} Stamina dataset.")

    raw_by_year: dict[int, pd.DataFrame] = {}
    coverage = []
    for candidate in years:
        raw_by_year[candidate], audit = _build_raw_windows(_load_source(candidate, root), candidate)
        coverage.append(audit)
    reference = _fit_reference(raw_by_year[DEVELOPMENT_YEAR])

    year_audits = []
    target_games = pd.DataFrame()
    for candidate in years:
        windows, games = _score_year(raw_by_year[candidate], reference)
        _write_parquet_atomic(windows, physical_window_path(candidate, root), "physical_windows")
        _write_parquet_atomic(games, physical_game_path(candidate, root), "physical_games")
        eligible = games[games["eligible"]].copy()
        pivot = windows[windows["eligible"]].pivot_table(
            index=["pitcher", "game_pk"], columns="analysis_bucket", values="physical_stability_plus", aggfunc="first"
        )
        split = _spearman(pivot.get("21–40", pd.Series(dtype="float64")), pivot.get("61–80", pd.Series(dtype="float64")))
        velocity_relation = _spearman(eligible["physical_stability_plus"], eligible["velocity_plus"])
        year_audits.append({
            "year": int(candidate), "window_rows": int(len(windows)), "game_rows": int(len(games)),
            "eligible_games": int(len(eligible)), "pitchers": int(eligible["pitcher"].nunique()),
            "median_reliability": round(float(eligible["reliability"].median()), 3) if len(eligible) else 0.0,
            "median_interval_width": round(float((eligible["ci_high"] - eligible["ci_low"]).median()), 3) if len(eligible) else 0.0,
            "split_window_spearman": round(split, 3) if split is not None else None,
            "velocity_vs_physical_spearman": round(velocity_relation, 3) if velocity_relation is not None else None,
            "score_p05": round(float(eligible["physical_stability_plus"].quantile(0.05)), 1) if len(eligible) else None,
            "score_p50": round(float(eligible["physical_stability_plus"].median()), 1) if len(eligible) else None,
            "score_p95": round(float(eligible["physical_stability_plus"].quantile(0.95)), 1) if len(eligible) else None,
        })
        if candidate == int(year):
            target_games = games

    signal_contract = [
        {
            "key": key, "label": spec["label"], "unit": spec["unit"], "weight": spec["weight"],
            "direction": "Smaller drift is more stable", "definition": spec["definition"],
        }
        for key, spec in SIGNALS.items()
    ]
    players = []
    if len(target_games):
        player_rows = target_games.groupby("pitcher", as_index=False).agg(
            name=("pitcher_name", "first"), team=("team", "last"), appearances=("game_pk", "nunique")
        ).sort_values("name", kind="stable")
        players = [
            {"pitcher_id": int(row.pitcher), "name": str(row.name), "team": str(row.team), "appearances": int(row.appearances)}
            for row in player_rows.itertuples(index=False)
        ]
    payload = {
        "slice15": {
            "status": "ready", "publication_status": "research_only", "contract_version": CONTRACT_VERSION,
            "development_year": DEVELOPMENT_YEAR, "covered_years": years,
            "minimum_early_exact_pitches": MINIMUM_EARLY_EXACT_PITCHES,
            "minimum_late_pitches": MINIMUM_LATE_PITCHES,
            "minimum_component_coverage_pct": MINIMUM_COMPONENT_COVERAGE * 100.0,
            "method": "Every later pitch is compared with the same appearance's first-20 exact-pitch-type baseline. Absolute or vector drift is retained; missing signals remain null and never become zero.",
            "signals": signal_contract, "coverage": coverage,
            "warnings": [
                "Drift measures change magnitude, not injury, fatigue, pain or mechanical failure.",
                "Arm-angle date-batch missingness remains null; missing fixed weight receives a neutral league contribution and lowers reliability.",
                "Later pitch selection remains observable-only: a pitch type abandoned mid-game cannot reveal its unobserved physical path.",
            ],
        },
        "slice16": {
            "status": "ready", "publication_status": "research_only", "model_version": MODEL_VERSION,
            "contract_version": "stamina_physical_stability_v1", "development_year": DEVELOPMENT_YEAR,
            "scoring_year": int(year), "players": players, "year_audits": year_audits,
            "method": "Six transparent drift components are robustly standardized on 2023, combined with fixed weights, centered to 100 with 10 points per development-game SD, and empirical-Bayes shrunk with an 80% interval.",
            "warnings": [
                "Physical Stability+ is independent of Stuff+ during score construction and is not a replacement for observed Quality Stamina+.",
                "A higher score means less measured delivery/shape drift than the development reference, not lower injury risk.",
                "The 2026 season has already been inspected in prior diagnostics, so it is a robustness audit rather than a pristine untouched test.",
            ],
        },
        "reference": reference,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path = physical_contract_path(year, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return payload


def get_physical_stability_overview(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    path = physical_contract_path(year, data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Physical Stability+ artifacts have not been built for {year}.")
    return json.loads(path.read_text(encoding="utf-8"))


def get_physical_stability(year: int, pitcher_id: int, data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    window_path = physical_window_path(year, root)
    game_path = physical_game_path(year, root)
    if not window_path.exists() or not game_path.exists():
        raise FileNotFoundError(f"Physical Stability+ artifacts have not been built for {year}.")
    with duckdb.connect() as connection:
        games = connection.execute(
            "SELECT * FROM read_parquet(?) WHERE pitcher = ? ORDER BY game_date, game_pk",
            [str(game_path), int(pitcher_id)],
        ).fetchdf()
        windows = connection.execute(
            "SELECT * FROM read_parquet(?) WHERE pitcher = ? ORDER BY game_date, game_pk, \"order\"",
            [str(window_path), int(pitcher_id)],
        ).fetchdf()
    if games.empty:
        raise ValueError(f"Pitcher {pitcher_id} has no Physical Stability+ data for {year}.")
    game_columns = [
        "pitcher", "game_pk", "game_date", "pitcher_name", "team", "season_start_number", "windows",
        "late_pitches", "supported_pitches", "component_coverage", "velocity_plus", "spin_plus",
        "movement_plus", "release_point_plus", "extension_plus", "arm_angle_plus",
        "raw_physical_stability_plus", "physical_stability_plus", "ci_low", "ci_high", "reliability",
        "eligible", "confidence",
    ]
    window_columns = [
        "pitcher", "game_pk", "game_date", "pitcher_name", "team", "analysis_bucket", "order",
        "total_pitches", "supported_pitches", "support_pct", "component_coverage", "velocity_plus", "spin_plus",
        "movement_plus", "release_point_plus", "extension_plus", "arm_angle_plus",
        "raw_physical_stability_plus", "physical_stability_plus", "ci_low", "ci_high", "reliability", "eligible",
    ]
    clean_games = games[game_columns].replace({np.nan: None}).to_dict("records")
    clean_windows = windows[window_columns].replace({np.nan: None}).to_dict("records")
    for rows in [clean_games, clean_windows]:
        for row in rows:
            row["game_date"] = str(pd.Timestamp(row["game_date"]).date())
    return {
        "year": int(year), "publication_status": "research_only", "pitcher_id": int(pitcher_id),
        "pitcher_name": str(games["pitcher_name"].iloc[0]), "team": str(games["team"].iloc[-1]),
        "games": clean_games, "windows": clean_windows,
        "warnings": [
            "Physical Stability+ measures public tracking stability, not health, effort, intent or injury risk.",
            "Use the component columns to distinguish velocity, shape and release-geometry changes.",
        ],
    }
