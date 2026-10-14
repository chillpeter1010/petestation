from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.command_retention_service import command_game_path
from app.services.physical_stability_service import physical_game_path
from app.services.stamina_lab_service import stamina_dataset_path, stamina_game_state_path
from app.services.wpa_service import calibrate_pitcher_wpa, plate_appearance_wpa_ctes


CONTRACT_VERSION = "pitcher_performance_state_contract_v1"
WAREHOUSE_VERSION = "pitcher_appearance_state_warehouse_v1"
BASELINE_VERSION = "pitcher_performance_baselines_v1"
STATE_MODEL_VERSION = "hierarchical_diagonal_ar1_state_space_v1_1"
DEVELOPMENT_YEAR = 2025
TEST_YEAR = 2026
ROLES = ("SP", "RP")
STATE_SIGNALS = ("stuff_state", "command_state", "result_state")
GAP_POLICIES = ("fixed_appearance_with_60d_reset", "calendar_decay", "calendar_decay_with_60d_reset")
LONG_GAP_RESET_DAYS = 60.0
BASELINE_FEATURES = [
    "lag_process_score", "lag_result_score", "process_ma5", "process_ewm",
    "lag_process_volatility", "days_rest", "workload_pitches_7d",
    "workload_pitches_28d", "previous_appearance_pitches",
]


def contract_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_contract.json"


def appearance_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"performance_state_appearances_{int(year)}.parquet"


def filtered_state_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"performance_state_filtered_{int(year)}.parquet"


def audit_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_slice0_3.json"


def _write_parquet_atomic(frame: pd.DataFrame, path: Path, relation_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.parquet")
    with duckdb.connect() as connection:
        connection.register(relation_name, frame)
        target = str(temporary).replace("'", "''")
        connection.execute(f"COPY {relation_name} TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        connection.unregister(relation_name)
    temporary.replace(path)


def _write_json_atomic(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def _number(value: Any, digits: int = 4) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    return round(float(numeric), digits) if pd.notna(numeric) and np.isfinite(float(numeric)) else None


def _load_pitch_appearances(year: int, root: Path) -> pd.DataFrame:
    path = stamina_dataset_path(year, root)
    if not path.exists():
        raise FileNotFoundError(f"Required Stamina pitch dataset not found: {path}")
    query = """
        SELECT
            CAST(pitcher AS BIGINT) AS pitcher_id,
            CAST(game_pk AS BIGINT) AS game_pk,
            min(CAST(game_date AS DATE)) AS game_date,
            any_value(player_name) AS pitcher_name,
            any_value(pitcher_team) AS team,
            any_value(appearance_role) AS role,
            max(appearance_number) AS role_appearance_number,
            max(all_role_appearance_number) AS appearance_number,
            max(days_rest) AS days_rest,
            max(previous_appearance_pitches) AS previous_appearance_pitches,
            max(workload_pitches_3d) AS workload_pitches_3d,
            max(workload_pitches_7d) AS workload_pitches_7d,
            max(workload_pitches_14d) AS workload_pitches_14d,
            max(workload_pitches_28d) AS workload_pitches_28d,
            max(all_role_season_pitches_before) AS season_pitches_before,
            count(*) AS pitches,
            count(pitch_stuff_plus) AS stuff_pitches,
            count(location_plus_pitch) AS location_pitches,
            avg(pitch_stuff_plus) AS mean_stuff_plus,
            avg(location_plus_pitch) AS mean_location_plus,
            avg(pitch_stuff_plus) FILTER (WHERE appearance_pitch_number <= 10) AS first10_stuff_plus,
            avg(location_plus_pitch) FILTER (WHERE appearance_pitch_number <= 10) AS first10_location_plus,
            avg(pitch_stuff_plus) FILTER (WHERE appearance_pitch_number <= 20) AS first20_stuff_plus,
            avg(location_plus_pitch) FILTER (WHERE appearance_pitch_number <= 20) AS first20_location_plus,
            avg(pitch_stuff_plus) FILTER (WHERE pitch_family = 'Fastball') AS fastball_stuff_plus,
            avg(pitch_stuff_plus) FILTER (WHERE pitch_family = 'Breaking') AS breaking_stuff_plus,
            avg(pitch_stuff_plus) FILTER (WHERE pitch_family = 'Offspeed') AS offspeed_stuff_plus,
            count(*) FILTER (WHERE pitch_family = 'Fastball') AS fastball_pitches,
            count(*) FILTER (WHERE pitch_family = 'Breaking') AS breaking_pitches,
            count(*) FILTER (WHERE pitch_family = 'Offspeed') AS offspeed_pitches
        FROM read_parquet(?)
        GROUP BY pitcher, game_pk
        ORDER BY game_date, game_pk, pitcher
    """
    with duckdb.connect() as connection:
        return connection.execute(query, [str(path)]).fetchdf()


def _load_pa_results(year: int, root: Path) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, root)
    if not db_path.exists():
        raise FileNotFoundError(f"Pitch database not found for {year}: {db_path}")
    with duckdb.connect(str(db_path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        source = resolve_pitch_table(tables)
        if not source:
            raise FileNotFoundError(f"Pitch table not found for {year}.")
        frame = connection.execute(
            f"""
            WITH {plate_appearance_wpa_ctes(source)},
            pa_pitcher AS (
                SELECT
                    game_pk,
                    at_bat_number,
                    arg_min(CAST(pitcher AS BIGINT), pitch_number) AS pitcher_id,
                    arg_min(pitcher_team, pitch_number) AS pitcher_team,
                    arg_min(home_team, pitch_number) AS home_team,
                    arg_min(CAST(inning AS BIGINT), pitch_number) AS inning,
                    arg_min(inning_topbot, pitch_number) AS inning_topbot,
                    arg_min(CAST(outs_when_up AS BIGINT), pitch_number) AS outs,
                    arg_min(
                        CASE WHEN on_1b IS NULL THEN 0 ELSE 1 END
                        + CASE WHEN on_2b IS NULL THEN 0 ELSE 2 END
                        + CASE WHEN on_3b IS NULL THEN 0 ELSE 4 END,
                        pitch_number
                    ) AS base_state,
                    arg_min(
                        CASE WHEN inning_topbot = 'Top' THEN home_score - away_score
                             ELSE away_score - home_score END,
                        pitch_number
                    ) AS score_diff,
                    sum(try_cast(delta_pitcher_run_exp AS DOUBLE)) AS pa_re24
                FROM {source}
                WHERE game_type = 'R' AND pitcher IS NOT NULL AND game_pk IS NOT NULL
                  AND at_bat_number IS NOT NULL
                GROUP BY game_pk, at_bat_number
            )
            SELECT p.*, w.pa_home_wpa
            FROM pa_pitcher p
            LEFT JOIN wpa_values w USING (game_pk, at_bat_number)
            """
        ).fetchdf()
    raw_pitcher_wpa = np.where(
        frame["pitcher_team"].eq(frame["home_team"]), frame["pa_home_wpa"], -frame["pa_home_wpa"]
    )
    frame["pitcher_wpa"] = calibrate_pitcher_wpa(raw_pitcher_wpa)
    return frame


def _leverage_reference(pa_2025: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    valid = pa_2025.dropna(subset=["pitcher_wpa"]).copy()
    global_abs = float(valid["pitcher_wpa"].abs().mean()) if len(valid) else 0.01
    global_abs = max(global_abs, 1e-6)
    keys = ["inning", "inning_topbot", "score_diff", "outs", "base_state"]
    states = valid.groupby(keys, dropna=False, as_index=False).agg(
        samples=("pitcher_wpa", "size"), mean_abs_wpa=("pitcher_wpa", lambda s: float(s.abs().mean()))
    )
    raw_li = states["mean_abs_wpa"] / global_abs
    states["event_li"] = ((states["samples"] * raw_li + 50.0) / (states["samples"] + 50.0)).clip(0.20, 5.0)
    return states[keys + ["event_li", "samples"]], global_abs


def _aggregate_results(pa: pd.DataFrame, li_reference: pd.DataFrame) -> pd.DataFrame:
    keys = ["inning", "inning_topbot", "score_diff", "outs", "base_state"]
    working = pa.merge(li_reference[keys + ["event_li"]], on=keys, how="left")
    working["event_li"] = working["event_li"].fillna(1.0).clip(0.20, 5.0)
    working["wpa_li_event"] = working["pitcher_wpa"] / working["event_li"]
    return working.groupby(["pitcher_id", "game_pk"], as_index=False).agg(
        re24=("pa_re24", "sum"),
        wpa=("pitcher_wpa", "sum"),
        wpa_li=("wpa_li_event", "sum"),
        plate_appearances=("at_bat_number", "nunique"),
        mean_li=("event_li", "mean"),
    )


def _load_game_score_proxy(year: int, root: Path) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, root)
    with duckdb.connect(str(db_path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        source = resolve_pitch_table(tables)
        return connection.execute(
            f"""
            WITH terminal AS (
                SELECT
                    CAST(pitcher AS BIGINT) AS pitcher_id,
                    CAST(game_pk AS BIGINT) AS game_pk,
                    events,
                    greatest(coalesce(post_bat_score, bat_score) - coalesce(bat_score, 0), 0) AS runs,
                    CASE
                        WHEN events IN ('grounded_into_double_play', 'strikeout_double_play', 'double_play') THEN 2
                        WHEN events = 'triple_play' THEN 3
                        WHEN events IN ('strikeout', 'field_out', 'force_out', 'sac_fly', 'sac_bunt',
                                        'fielders_choice_out') THEN 1
                        ELSE 0
                    END AS outs_on_play
                FROM {source}
                WHERE game_type = 'R' AND pitcher IS NOT NULL AND game_pk IS NOT NULL AND events IS NOT NULL
            ), lines AS (
                SELECT
                    pitcher_id, game_pk,
                    sum(outs_on_play) AS outs_recorded,
                    count(*) FILTER (WHERE events IN ('single', 'double', 'triple', 'home_run')) AS hits,
                    count(*) FILTER (WHERE events IN ('walk', 'intent_walk', 'hit_by_pitch')) AS walks,
                    count(*) FILTER (WHERE events IN ('strikeout', 'strikeout_double_play')) AS strikeouts,
                    sum(runs) AS runs_allowed
                FROM terminal GROUP BY pitcher_id, game_pk
            )
            SELECT *,
                50 + outs_recorded + 2 * greatest(outs_recorded - 12, 0) + strikeouts
                   - 2 * hits - 4 * runs_allowed - walks AS game_score_proxy
            FROM lines
            """
        ).fetchdf()


def _load_optional_game_signals(year: int, root: Path) -> pd.DataFrame:
    quality = stamina_game_state_path(year, root)
    physical = physical_game_path(year, root)
    command = command_game_path(year, root)
    base = pd.DataFrame(columns=["pitcher_id", "game_pk"])
    with duckdb.connect() as connection:
        if quality.exists():
            base = connection.execute(
                "SELECT CAST(pitcher AS BIGINT) pitcher_id, CAST(game_pk AS BIGINT) game_pk, "
                "stamina_plus AS quality_stamina_plus, reliability AS quality_reliability "
                "FROM read_parquet(?) WHERE scope = 'Overall' AND eligible",
                [str(quality)],
            ).fetchdf()
        if physical.exists():
            frame = connection.execute(
                "SELECT CAST(pitcher AS BIGINT) pitcher_id, CAST(game_pk AS BIGINT) game_pk, "
                "physical_stability_plus, reliability AS physical_reliability "
                "FROM read_parquet(?) WHERE eligible",
                [str(physical)],
            ).fetchdf()
            base = frame if base.empty else base.merge(frame, on=["pitcher_id", "game_pk"], how="outer")
        if command.exists():
            frame = connection.execute(
                "SELECT CAST(pitcher AS BIGINT) pitcher_id, CAST(game_pk AS BIGINT) game_pk, "
                "command_retention_plus, reliability AS command_reliability "
                "FROM read_parquet(?) WHERE scope = 'Overall' AND eligible",
                [str(command)],
            ).fetchdf()
            base = frame if base.empty else base.merge(frame, on=["pitcher_id", "game_pk"], how="outer")
    return base


def _build_raw_warehouse(year: int, root: Path, li_reference: pd.DataFrame) -> pd.DataFrame:
    appearances = _load_pitch_appearances(year, root)
    results = _aggregate_results(_load_pa_results(year, root), li_reference)
    game_score = _load_game_score_proxy(year, root)
    optional = _load_optional_game_signals(year, root)
    frame = appearances.merge(results, on=["pitcher_id", "game_pk"], how="left")
    frame = frame.merge(game_score, on=["pitcher_id", "game_pk"], how="left", suffixes=("", "_line"))
    if not optional.empty:
        frame = frame.merge(optional, on=["pitcher_id", "game_pk"], how="left")
    frame["year"] = int(year)
    frame["game_score_proxy"] = frame["game_score_proxy"].where(frame["role"].eq("SP"))
    frame["game_score_source"] = np.where(frame["role"].eq("SP"), "derived_runs_allowed_proxy", None)
    frame["re24_per_pa"] = frame["re24"] / frame["plate_appearances"].replace(0, np.nan)
    frame["wpa_li_per_pa"] = frame["wpa_li"] / frame["plate_appearances"].replace(0, np.nan)
    return frame.sort_values(["pitcher_id", "role", "game_date", "game_pk"], kind="stable").reset_index(drop=True)


def _reference_parameters(development: pd.DataFrame) -> dict[str, dict[str, float]]:
    columns = [
        "mean_stuff_plus", "mean_location_plus", "first10_stuff_plus", "first10_location_plus",
        "first20_stuff_plus", "first20_location_plus", "re24_per_pa", "wpa_li_per_pa",
        "game_score_proxy",
    ]
    reference: dict[str, dict[str, float]] = {}
    for role in ROLES:
        subset = development[development["role"].eq(role)]
        role_values: dict[str, float] = {}
        for column in columns:
            values = pd.to_numeric(subset[column], errors="coerce").dropna()
            role_values[f"{column}_mean"] = float(values.mean()) if len(values) else 0.0
            role_values[f"{column}_sd"] = max(float(values.std(ddof=1)), 1e-6) if len(values) > 1 else 1.0
        reference[role] = role_values
    return reference


def _causal_personal_residual(
    frame: pd.DataFrame,
    column: str,
    reference: dict[str, dict[str, float]],
    development_year: int,
    prior_appearances: float = 5.0,
) -> tuple[pd.Series, pd.Series, dict[str, float]]:
    expected = pd.Series(np.nan, index=frame.index, dtype=float)
    residual = pd.Series(np.nan, index=frame.index, dtype=float)
    ordered = frame.sort_values(["pitcher_id", "role", "game_date", "game_pk"], kind="stable")
    for (pitcher_id, role), group in ordered.groupby(["pitcher_id", "role"], sort=False):
        del pitcher_id
        role_mean = reference[str(role)][f"{column}_mean"]
        observed_sum = 0.0
        observed_count = 0
        for index, value in pd.to_numeric(group[column], errors="coerce").items():
            estimate = (prior_appearances * role_mean + observed_sum) / (prior_appearances + observed_count)
            expected.loc[index] = estimate
            if pd.notna(value):
                residual.loc[index] = float(value) - estimate
                observed_sum += float(value)
                observed_count += 1
    scales: dict[str, float] = {}
    standardized = pd.Series(np.nan, index=frame.index, dtype=float)
    for role in ROLES:
        mask = frame["role"].eq(role)
        development_values = residual[mask & frame["year"].eq(development_year)].dropna()
        scale = max(float(development_values.std(ddof=1)), 1e-6) if len(development_values) > 1 else 1.0
        scales[role] = scale
        standardized.loc[mask] = residual.loc[mask] / scale
    return expected, standardized, scales


def _mean_available(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    return frame[columns].mean(axis=1, skipna=True)


def _add_labels_and_history(
    all_rows: pd.DataFrame,
    development_year: int,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, dict[str, float]]]:
    frame = all_rows.copy()
    development = frame[frame["year"].eq(development_year)].copy()
    reference = _reference_parameters(development)
    residual_scales: dict[str, dict[str, float]] = {}
    for column in [
        "mean_stuff_plus", "mean_location_plus", "first10_stuff_plus", "first10_location_plus",
        "first20_stuff_plus", "first20_location_plus", "re24_per_pa", "wpa_li_per_pa",
        "game_score_proxy",
    ]:
        expected, standardized, scales = _causal_personal_residual(
            frame, column, reference, development_year
        )
        frame[f"{column}_expected"] = expected
        frame[f"{column}_z"] = standardized
        residual_scales[column] = scales
    frame["process_score"] = _mean_available(frame, ["mean_stuff_plus_z", "mean_location_plus_z"])
    frame["result_score"] = _mean_available(frame, ["re24_per_pa_z", "wpa_li_per_pa_z"])
    frame["first10_process_score"] = _mean_available(frame, ["first10_stuff_plus_z", "first10_location_plus_z"])
    frame["first20_process_score"] = _mean_available(frame, ["first20_stuff_plus_z", "first20_location_plus_z"])
    frame["adjusted_game_score"] = frame["game_score_proxy_z"].where(frame["role"].eq("SP"))

    thresholds: dict[str, dict[str, float]] = {}
    for role in ROLES:
        train = frame[frame["year"].eq(development_year) & frame["role"].eq(role)]
        thresholds[role] = {}
        for column in ["process_score", "result_score", "first10_process_score", "first20_process_score"]:
            values = train[column].dropna()
            thresholds[role][column] = float(values.quantile(0.05)) if len(values) else -1.645
            frame[f"{column}_collapse"] = frame.get(f"{column}_collapse", pd.Series(False, index=frame.index))
            mask = frame["role"].eq(role) & frame[column].notna()
            frame.loc[mask, f"{column}_collapse"] = frame.loc[mask, column].le(thresholds[role][column])
    frame["process_collapse"] = frame["process_score_collapse"].astype(bool)
    frame["result_collapse"] = frame["result_score_collapse"].astype(bool)
    frame["combined_collapse"] = frame["process_collapse"] & frame["result_collapse"]

    frame = frame.sort_values(["pitcher_id", "role", "game_date", "game_pk"], kind="stable")
    groups = frame.groupby(["pitcher_id", "role"], sort=False)
    frame["calendar_days_since_prior"] = groups["game_date"].diff().dt.days.astype(float)
    frame["lag_process_score"] = groups["process_score"].shift(1)
    frame["lag_result_score"] = groups["result_score"].shift(1)
    frame["lag_process_collapse"] = groups["process_collapse"].shift(1).fillna(False).astype(bool)
    frame["process_ma5"] = groups["process_score"].transform(lambda s: s.shift(1).rolling(5, min_periods=2).mean())
    frame["process_ewm"] = groups["process_score"].transform(lambda s: s.shift(1).ewm(span=5, adjust=False, min_periods=2).mean())
    frame["lag_process_volatility"] = groups["process_score"].transform(lambda s: s.shift(1).rolling(5, min_periods=3).std())
    frame["process_improvement"] = frame["process_score"] - frame["lag_process_score"]

    collapsed_train = frame[frame["year"].eq(development_year) & frame["lag_process_collapse"]].copy()
    expected_recovery = collapsed_train.groupby("role")["process_improvement"].mean().to_dict()
    frame["expected_mean_reversion"] = frame["role"].map(expected_recovery).where(frame["lag_process_collapse"])
    frame["excess_recovery"] = frame["process_improvement"] - frame["expected_mean_reversion"]
    frame["return_to_baseline"] = frame["lag_process_collapse"] & frame["process_score"].ge(-0.50)
    frame["strong_rebound"] = frame["lag_process_collapse"] & frame["process_score"].ge(0.50)

    prevalence: dict[str, Any] = {}
    for year in sorted(frame["year"].unique()):
        prevalence[str(int(year))] = {}
        for role in ROLES:
            subset = frame[frame["year"].eq(year) & frame["role"].eq(role)]
            prevalence[str(int(year))][role] = {
                "appearances": int(len(subset)),
                "pitchers": int(subset["pitcher_id"].nunique()),
                "process_collapse_rate": _number(subset["process_collapse"].mean()),
                "result_collapse_rate": _number(subset["result_collapse"].mean()),
                "combined_collapse_rate": _number(subset["combined_collapse"].mean()),
                "rebound_opportunities": int(subset["lag_process_collapse"].sum()),
                "return_to_baseline_rate": _number(
                    subset.loc[subset["lag_process_collapse"], "return_to_baseline"].mean()
                ),
            }
    transfer_drift: dict[str, Any] = {}
    development_key = str(int(development_year))
    test_years = [key for key in prevalence if key != development_key]
    for role in ROLES:
        role_drift: dict[str, Any] = {}
        for test_key in test_years:
            development_rate = prevalence[development_key][role]["process_collapse_rate"]
            test_rate = prevalence[test_key][role]["process_collapse_rate"]
            delta = float(test_rate) - float(development_rate)
            role_drift[test_key] = {
                "development_rate": development_rate,
                "test_rate": test_rate,
                "delta_pp": _number(delta * 100.0),
                "flagged": abs(delta) > 0.02,
                "interpretation": (
                    "Cross-season process-score distribution or model calibration shifted; do not interpret the rate change as physiology."
                    if abs(delta) > 0.02 else "Within the preregistered two-percentage-point transfer tolerance."
                ),
            }
        transfer_drift[role] = role_drift
    audit = {
        "thresholds": thresholds,
        "personal_baseline": {
            "method": "Causal empirical-Bayes pitcher-role mean using five role-average prior appearances and only earlier observations.",
            "residual_scales": residual_scales,
        },
        "expected_mean_reversion": {role: _number(value) for role, value in expected_recovery.items()},
        "prevalence": prevalence,
        "cross_season_transfer_drift": transfer_drift,
    }
    return frame.reset_index(drop=True), audit, reference


def _safe_probability_metrics(y_true: pd.Series, probabilities: np.ndarray) -> dict[str, Any]:
    truth = y_true.astype(int).to_numpy()
    clipped = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    if len(np.unique(truth)) < 2:
        return {"rows": int(len(truth)), "average_precision": None, "brier": None, "log_loss": None}
    return {
        "rows": int(len(truth)),
        "average_precision": _number(average_precision_score(truth, clipped)),
        "brier": _number(brier_score_loss(truth, clipped)),
        "log_loss": _number(log_loss(truth, clipped, labels=[0, 1])),
    }


def _build_baseline_audit(frame: pd.DataFrame, development_year: int, test_year: int) -> dict[str, Any]:
    train = frame[frame["year"].eq(development_year)].copy()
    test = frame[frame["year"].eq(test_year)].copy()
    continuous: dict[str, Any] = {}
    for model, column in {
        "personal_last": "lag_process_score",
        "ma5": "process_ma5",
        "ewma5": "process_ewm",
    }.items():
        valid = test.dropna(subset=["process_score", column])
        continuous[model] = {
            "rows": int(len(valid)),
            "rmse": _number(math.sqrt(mean_squared_error(valid["process_score"], valid[column]))) if len(valid) else None,
            "mae": _number(mean_absolute_error(valid["process_score"], valid[column])) if len(valid) else None,
        }

    train_valid = train.dropna(subset=["process_score", "lag_process_score"]).copy()
    test_valid = test.dropna(subset=["process_score", "lag_process_score"]).copy()
    train_valid = train_valid[train_valid[BASELINE_FEATURES].notna().sum(axis=1).ge(2)]
    test_valid = test_valid[test_valid[BASELINE_FEATURES].notna().sum(axis=1).ge(2)]
    event_models: dict[str, Any] = {}
    if len(train_valid) and len(test_valid) and train_valid["process_collapse"].nunique() == 2:
        model = make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=1000)
        )
        model.fit(train_valid[BASELINE_FEATURES], train_valid["process_collapse"].astype(int))
        probabilities = model.predict_proba(test_valid[BASELINE_FEATURES])[:, 1]
        event_models["lagged_logistic"] = _safe_probability_metrics(test_valid["process_collapse"], probabilities)
    prevalence = float(train_valid["process_collapse"].mean()) if len(train_valid) else 0.05
    event_models["development_prevalence"] = _safe_probability_metrics(
        test_valid["process_collapse"], np.full(len(test_valid), prevalence)
    ) if len(test_valid) else {"rows": 0, "average_precision": None, "brier": None, "log_loss": None}

    rebound_train = train[train["lag_process_collapse"] & train["return_to_baseline"].notna()]
    rebound_test = test[test["lag_process_collapse"] & test["return_to_baseline"].notna()]
    rebound_rate = float(rebound_train["return_to_baseline"].mean()) if len(rebound_train) else 0.5
    rebound = _safe_probability_metrics(
        rebound_test["return_to_baseline"], np.full(len(rebound_test), rebound_rate)
    ) if len(rebound_test) else {"rows": 0, "average_precision": None, "brier": None, "log_loss": None}
    return {
        "version": BASELINE_VERSION,
        "development_year": development_year,
        "external_diagnostic_year": test_year,
        "evaluation_status": "test_with_documented_slice3a_amendment",
        "feature_information_time": "All predictors are shifted to the prior same-role appearance.",
        "continuous_process_forecasts": continuous,
        "collapse_probability": event_models,
        "rebound_prevalence_baseline": rebound,
    }


def _filter_sequence(
    observations: np.ndarray,
    pitches: np.ndarray,
    elapsed_days: np.ndarray,
    phi: float,
    process_variance: float,
    observation_variance: float,
    median_pitches: float,
    gap_policy: str = "calendar_decay",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n = len(observations)
    forecasts = np.full(n, np.nan)
    forecast_sd = np.full(n, np.nan)
    states = np.full(n, np.nan)
    state_sd = np.full(n, np.nan)
    innovations = np.full(n, np.nan)
    mean = 0.0
    variance = 1.0
    for index in range(n):
        if index == 0:
            prior_mean, prior_variance = 0.0, 1.0
        else:
            days = float(elapsed_days[index]) if np.isfinite(elapsed_days[index]) else 5.0
            days = max(days, 1.0)
            if gap_policy != "calendar_decay" and days >= LONG_GAP_RESET_DAYS:
                prior_mean, prior_variance = 0.0, 1.0
                gap_scale = None
            elif gap_policy == "fixed_appearance_with_60d_reset":
                gap_scale = 1.0
            else:
                gap_scale = days / 5.0
            if gap_scale is not None:
                transition = float(phi ** gap_scale)
                if phi < 1.0:
                    accumulated_process_variance = process_variance * (
                        (1.0 - transition * transition) / max(1.0 - phi * phi, 1e-9)
                    )
                else:
                    accumulated_process_variance = process_variance * gap_scale
                prior_mean = transition * mean
                prior_variance = transition * transition * variance + accumulated_process_variance
        forecasts[index] = prior_mean
        forecast_sd[index] = math.sqrt(max(prior_variance, 1e-9))
        observation = observations[index]
        if np.isfinite(observation):
            pitch_scale = float(np.clip(median_pitches / max(pitches[index], 1.0), 0.5, 3.0))
            current_r = observation_variance * pitch_scale
            innovations[index] = observation - prior_mean
            gain = prior_variance / (prior_variance + current_r)
            mean = prior_mean + gain * innovations[index]
            variance = (1.0 - gain) * prior_variance
        else:
            mean, variance = prior_mean, prior_variance
        states[index] = mean
        state_sd[index] = math.sqrt(max(variance, 1e-9))
    return forecasts, forecast_sd, states, state_sd, innovations


def _state_space_loss(
    frame: pd.DataFrame,
    signal: str,
    role: str,
    phi: float,
    q: float,
    r: float,
    gap_policy: str = "calendar_decay",
) -> float:
    errors: list[float] = []
    subset = frame[frame["role"].eq(role)].sort_values(["pitcher_id", "game_date", "game_pk"])
    median_pitches = max(float(subset["pitches"].median()), 1.0)
    for _, group in subset.groupby("pitcher_id", sort=False):
        forecasts, _, _, _, _ = _filter_sequence(
            group[signal].to_numpy(dtype=float), group["pitches"].to_numpy(dtype=float),
            group["calendar_days_since_prior"].to_numpy(dtype=float), phi, q, r, median_pitches,
            gap_policy,
        )
        observed = group[signal].to_numpy(dtype=float)
        valid = np.isfinite(observed) & np.isfinite(forecasts)
        if valid.any():
            errors.extend((observed[valid] - forecasts[valid]).tolist())
    return float(np.sqrt(np.mean(np.square(errors)))) if errors else float("inf")


def _state_space_grid_search(
    development: pd.DataFrame,
    signal: str,
    role: str,
) -> tuple[tuple[float, float, float, float, str], dict[str, float]]:
    subset = development[development["role"].eq(role)].sort_values(
        ["pitcher_id", "game_date", "game_pk"]
    )
    median_pitches = max(float(subset["pitches"].median()), 1.0)
    candidates = [
        (phi, q, r, gap_policy)
        for gap_policy in GAP_POLICIES
        for phi in (0.0, 0.10, 0.25, 0.50, 0.70, 0.85, 0.95, 0.99)
        for q in (0.01, 0.03, 0.10, 0.30)
        for r in (0.25, 0.50, 1.00, 2.00)
    ]
    phis = np.asarray([item[0] for item in candidates], dtype=float)
    process_variances = np.asarray([item[1] for item in candidates], dtype=float)
    observation_variances = np.asarray([item[2] for item in candidates], dtype=float)
    policies = np.asarray([item[3] for item in candidates], dtype=object)
    squared_error = np.zeros(len(candidates), dtype=float)
    observations_count = 0
    for _, group in subset.groupby("pitcher_id", sort=False):
        observations = group[signal].to_numpy(dtype=float)
        pitches = group["pitches"].to_numpy(dtype=float)
        elapsed_days = group["calendar_days_since_prior"].to_numpy(dtype=float)
        means = np.zeros(len(candidates), dtype=float)
        variances = np.ones(len(candidates), dtype=float)
        for index, observation in enumerate(observations):
            if index == 0:
                prior_means = np.zeros(len(candidates), dtype=float)
                prior_variances = np.ones(len(candidates), dtype=float)
            else:
                days = float(elapsed_days[index]) if np.isfinite(elapsed_days[index]) else 5.0
                days = max(days, 1.0)
                gap_scales = np.full(len(candidates), days / 5.0, dtype=float)
                gap_scales[policies == "fixed_appearance_with_60d_reset"] = 1.0
                reset = (policies != "calendar_decay") & (days >= LONG_GAP_RESET_DAYS)
                transitions = np.power(phis, gap_scales)
                accumulated = process_variances * (
                    (1.0 - np.square(transitions)) / np.maximum(1.0 - np.square(phis), 1e-9)
                )
                prior_means = transitions * means
                prior_variances = np.square(transitions) * variances + accumulated
                prior_means[reset] = 0.0
                prior_variances[reset] = 1.0
            if np.isfinite(observation):
                innovations = observation - prior_means
                squared_error += np.square(innovations)
                observations_count += 1
                pitch_scale = float(np.clip(median_pitches / max(pitches[index], 1.0), 0.5, 3.0))
                current_r = observation_variances * pitch_scale
                gains = prior_variances / (prior_variances + current_r)
                means = prior_means + gains * innovations
                variances = (1.0 - gains) * prior_variances
            else:
                means, variances = prior_means, prior_variances
    losses = np.sqrt(squared_error / observations_count) if observations_count else np.full(len(candidates), np.inf)
    best_index = min(range(len(candidates)), key=lambda index: (losses[index], *candidates[index]))
    phi, q, r, gap_policy = candidates[best_index]
    policy_best = {
        policy: float(losses[policies == policy].min())
        for policy in GAP_POLICIES
    }
    return (float(losses[best_index]), phi, q, r, gap_policy), policy_best


def _fit_state_parameters(development: pd.DataFrame) -> dict[str, dict[str, dict[str, Any]]]:
    parameters: dict[str, dict[str, dict[str, Any]]] = {}
    for role in ROLES:
        parameters[role] = {}
        for signal in STATE_SIGNALS:
            best, policy_best = _state_space_grid_search(development, signal, role)
            positive_gaps = pd.to_numeric(
                development.loc[development["role"].eq(role), "calendar_days_since_prior"], errors="coerce"
            )
            median_gap_days = float(positive_gaps[positive_gaps.gt(0)].median())
            half_life_units = math.log(0.5) / math.log(best[1]) if 0.0 < best[1] < 1.0 else None
            half_life_days = half_life_units * 5.0 if half_life_units is not None else None
            parameters[role][signal] = {
                "development_rmse": best[0],
                "phi": best[1],
                "process_variance": best[2],
                "observation_variance": best[3],
                "gap_policy": best[4],
                "gap_policy_development_rmse": policy_best,
                "median_role_gap_days": median_gap_days,
                "half_life_5day_units": half_life_units,
                "half_life_calendar_days": half_life_days,
                "half_life_appearances_approx": (
                    half_life_days / median_gap_days if half_life_days is not None and median_gap_days > 0 else None
                ),
                "persistence_interpretation": (
                    "white_noise_or_shorter_than_grid" if best[1] == 0.0 else "persistent_state"
                ),
            }
    return parameters


def _apply_state_space(
    frame: pd.DataFrame,
    parameters: dict[str, dict[str, dict[str, Any]]],
) -> pd.DataFrame:
    output = frame.copy().sort_values(["pitcher_id", "role", "game_date", "game_pk"], kind="stable")
    for signal in STATE_SIGNALS:
        for suffix in ["forecast", "forecast_sd", "filtered", "filtered_sd", "innovation", "standardized_innovation"]:
            output[f"{signal}_{suffix}"] = np.nan
    for role in ROLES:
        role_mask = output["role"].eq(role)
        median_pitches = max(float(output.loc[role_mask, "pitches"].median()), 1.0)
        for _, group in output.loc[role_mask].groupby("pitcher_id", sort=False):
            indices = group.index
            for signal in STATE_SIGNALS:
                params = parameters[role][signal]
                forecasts, forecast_sd, states, state_sd, innovations = _filter_sequence(
                    group[signal].to_numpy(dtype=float), group["pitches"].to_numpy(dtype=float),
                    group["calendar_days_since_prior"].to_numpy(dtype=float), params["phi"],
                    params["process_variance"], params["observation_variance"], median_pitches,
                    params["gap_policy"],
                )
                output.loc[indices, f"{signal}_forecast"] = forecasts
                output.loc[indices, f"{signal}_forecast_sd"] = forecast_sd
                output.loc[indices, f"{signal}_filtered"] = states
                output.loc[indices, f"{signal}_filtered_sd"] = state_sd
                output.loc[indices, f"{signal}_innovation"] = innovations
                output.loc[indices, f"{signal}_standardized_innovation"] = innovations / np.sqrt(
                    np.square(forecast_sd) + params["observation_variance"]
                )
    return output.sort_index()


def _state_space_audit(
    filtered: pd.DataFrame,
    parameters: dict[str, dict[str, dict[str, Any]]],
    test_year: int,
) -> dict[str, Any]:
    evaluations: list[dict[str, Any]] = []
    test = filtered[filtered["year"].eq(test_year)]
    for role in ROLES:
        for signal in STATE_SIGNALS:
            valid = test[test["role"].eq(role)].dropna(subset=[signal, f"{signal}_forecast"])
            if valid.empty:
                continue
            rmse = math.sqrt(mean_squared_error(valid[signal], valid[f"{signal}_forecast"]))
            zero_rmse = math.sqrt(mean_squared_error(valid[signal], np.zeros(len(valid))))
            within = (
                (valid[signal] >= valid[f"{signal}_forecast"] - 1.2816 * np.sqrt(
                    np.square(valid[f"{signal}_forecast_sd"]) + parameters[role][signal]["observation_variance"]
                ))
                & (valid[signal] <= valid[f"{signal}_forecast"] + 1.2816 * np.sqrt(
                    np.square(valid[f"{signal}_forecast_sd"]) + parameters[role][signal]["observation_variance"]
                ))
            )
            evaluations.append({
                "role": role,
                "signal": signal,
                "rows": int(len(valid)),
                "pitchers": int(valid["pitcher_id"].nunique()),
                "forecast_rmse": _number(rmse),
                "zero_state_rmse": _number(zero_rmse),
                "rmse_improvement_pct": _number((zero_rmse - rmse) / zero_rmse * 100.0) if zero_rmse else None,
                "interval_80_coverage": _number(within.mean()),
                "phi": _number(parameters[role][signal]["phi"]),
                "gap_policy": parameters[role][signal]["gap_policy"],
                "half_life_5day_units": _number(parameters[role][signal]["half_life_5day_units"]),
                "half_life_calendar_days": _number(parameters[role][signal]["half_life_calendar_days"]),
                "half_life_appearances_approx": _number(parameters[role][signal]["half_life_appearances_approx"]),
                "forecast_value": (
                    "useful" if (zero_rmse - rmse) / zero_rmse >= 0.02
                    else "exploratory" if rmse < zero_rmse
                    else "no_incremental_gain"
                ) if zero_rmse else "unavailable",
            })
    correlations = (
        test[[*STATE_SIGNALS]].corr(method="spearman").replace({np.nan: None}).to_dict()
        if len(test) else {}
    )
    return {
        "version": STATE_MODEL_VERSION,
        "model_class": "Role-pooled diagonal multivariate AR(1) Kalman filter with pitcher-specific filtered states.",
        "parameters": parameters,
        "external_diagnostic_year": test_year,
        "evaluation_status": "test_with_documented_slice3a_amendment",
        "evaluations": evaluations,
        "observed_signal_spearman": correlations,
        "limitations": [
            "The three latent dimensions share timing and hierarchy but use diagonal observation and transition covariance in v1.",
            "Half-life is reported in five-day units and calendar days; appearance count is only a role-level approximation.",
            "Filtered states describe performance; they do not diagnose fatigue or injury.",
        ],
    }


def _slice3a_audit(
    filtered: pd.DataFrame,
    parameters: dict[str, dict[str, dict[str, Any]]],
    development_year: int,
    test_year: int,
) -> dict[str, Any]:
    ordered = filtered.sort_values(["pitcher_id", "role", "game_date", "game_pk"], kind="stable")
    development_keys = set(
        map(tuple, ordered.loc[ordered["year"].eq(development_year), ["pitcher_id", "role"]].drop_duplicates().to_numpy())
    )
    first_test = ordered.loc[ordered["year"].eq(test_year)].groupby(["pitcher_id", "role"], sort=False).head(1)
    first_test = first_test[
        first_test[["pitcher_id", "role"]].apply(tuple, axis=1).isin(development_keys)
    ]
    gap_audit: dict[str, Any] = {}
    for role in ROLES:
        rows = first_test[first_test["role"].eq(role)]
        gaps = pd.to_numeric(rows["calendar_days_since_prior"], errors="coerce")
        gap_audit[role] = {
            "returning_pitcher_roles": int(len(rows)),
            "actual_gap_coverage": _number(gaps.notna().mean()) if len(rows) else None,
            "median_calendar_gap_days": _number(gaps.median()),
            "minimum_calendar_gap_days": _number(gaps.min()),
            "maximum_calendar_gap_days": _number(gaps.max()),
            "legacy_missing_days_rest_rows": int(rows["days_rest"].isna().sum()),
            "legacy_four_day_fill_used": False,
        }
    return {
        "version": "performance_state_slice3a_protocol_repair_v1",
        "development_year": development_year,
        "external_diagnostic_year": test_year,
        "evaluation_status": "test_with_documented_slice3a_amendment",
        "prospective_untouched_year": 2027,
        "calendar_gap_audit": gap_audit,
        "selected_models": {
            role: {
                signal: {
                    "phi": _number(values["phi"]),
                    "gap_policy": values["gap_policy"],
                    "gap_policy_development_rmse": {
                        key: _number(value) for key, value in values["gap_policy_development_rmse"].items()
                    },
                    "persistence_interpretation": values["persistence_interpretation"],
                    "half_life_5day_units": _number(values["half_life_5day_units"]),
                    "half_life_calendar_days": _number(values["half_life_calendar_days"]),
                    "half_life_appearances_approx": _number(values["half_life_appearances_approx"]),
                }
                for signal, values in signals.items()
            }
            for role, signals in parameters.items()
        },
        "changes": [
            "State transitions use actual pitcher-role calendar gaps rather than filling missing rest with four days.",
            "Fixed-appearance and calendar-decay timing are compared only on 2025 causal walk-forward loss; fixed timing and the explicit reset policy always reset gaps of at least 60 days.",
            "The persistence grid includes phi 0.00, 0.10 and 0.25 so transient signals are not forced to phi 0.50.",
            "Half-life units are corrected to five-day units and calendar days; appearance counts are approximate only.",
        ],
    }


def _contract_payload() -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "research_only",
        "development_year": DEVELOPMENT_YEAR,
        "external_diagnostic_year": TEST_YEAR,
        "evaluation_status": "test_with_documented_slice3a_amendment; reserve 2027 for a prospective untouched test.",
        "roles": list(ROLES),
        "role_rule": "Each appearance keeps its SP/RP role; dual-role pitchers retain separate histories.",
        "forecast_horizons": {
            "pregame_first_10": "The next appearance's first 10 pitches.",
            "pregame_first_20": "The next appearance's first 20 pitches.",
            "next_appearance": "The complete next same-role appearance.",
            "in_game_arbitrary_anchor": "Deferred; v1 does not relabel arbitrary pitch anchors as pregame forecasts.",
        },
        "labels": {
            "process_collapse": "Role-specific bottom 5% of 2025 Stuff+ and Location+ residuals versus a causal empirical-Bayes pitcher-role baseline.",
            "result_collapse": "Role-specific bottom 5% of 2025 RE24/PA and WPA/LI/PA residuals versus a causal empirical-Bayes pitcher-role baseline.",
            "combined_collapse": "Process and result collapse in the same appearance.",
            "return_to_baseline": "After a process collapse, process score returns to at least -0.50 SD.",
            "strong_rebound": "After a process collapse, process score reaches at least +0.50 SD.",
            "excess_recovery": "Observed improvement minus role-level 2025 mean reversion after a collapse.",
        },
        "information_time": "Forecast features must exist before the target appearance; rolling features are shifted by one same-role appearance.",
        "result_semantics": {
            "re24": "Pitcher-positive delta_pitcher_run_exp aggregated at the plate-appearance level.",
            "wpa": "Shared calibrated PA-boundary pitcher WPA; no per-pitch duplicate summation.",
            "wpa_li": "PA-boundary WPA divided by a 2025 empirical, shrunk state leverage estimate.",
            "game_score": "Starter-only Bill James-style proxy using observed outs, hits, runs, walks and strikeouts; not an official earned-run Game Score.",
        },
        "release_rules": [
            "No official leaderboard, Stamina+ overwrite or player-page integration in Slices 0-3.",
            "Missing values remain null and are never filled with zero.",
            "No injury, health, fatigue-cause or medical prediction claim.",
            "2026 is an external diagnostic/test season with a documented Slice 3A protocol amendment; it is not pristine untouched validation.",
        ],
    }


def refresh_performance_state(
    data_dir: Path | None = None,
    development_year: int = DEVELOPMENT_YEAR,
    test_year: int = TEST_YEAR,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    pa_development = _load_pa_results(development_year, root)
    li_reference, global_abs_wpa = _leverage_reference(pa_development)
    yearly = {
        development_year: _build_raw_warehouse(development_year, root, li_reference),
        test_year: _build_raw_warehouse(test_year, root, li_reference),
    }
    combined, label_audit, reference = _add_labels_and_history(
        pd.concat(yearly.values(), ignore_index=True), development_year
    )
    combined["stuff_state"] = combined["mean_stuff_plus_z"]
    combined["command_state"] = combined["mean_location_plus_z"]
    combined["result_state"] = combined["result_score"]
    baseline_audit = _build_baseline_audit(combined, development_year, test_year)
    parameters = _fit_state_parameters(combined[combined["year"].eq(development_year)])
    filtered = _apply_state_space(combined, parameters)
    state_audit = _state_space_audit(filtered, parameters, test_year)
    slice3a_audit = _slice3a_audit(filtered, parameters, development_year, test_year)

    for year in (development_year, test_year):
        rows = combined[combined["year"].eq(year)].copy()
        states = filtered[filtered["year"].eq(year)].copy()
        _write_parquet_atomic(rows, appearance_path(year, root), f"performance_state_appearances_{year}")
        _write_parquet_atomic(states, filtered_state_path(year, root), f"performance_state_filtered_{year}")

    contract = _contract_payload()
    _write_json_atomic(contract, contract_path(root))
    source_modified_at = {
        str(year): int(stamina_dataset_path(year, root).stat().st_mtime_ns)
        for year in (development_year, test_year)
    }
    coverage: dict[str, Any] = {}
    for year in (development_year, test_year):
        rows = combined[combined["year"].eq(year)]
        coverage[str(year)] = {
            "appearances": int(len(rows)),
            "pitchers": int(rows["pitcher_id"].nunique()),
            "sp_appearances": int(rows["role"].eq("SP").sum()),
            "rp_appearances": int(rows["role"].eq("RP").sum()),
            "stuff_coverage": _number(rows["mean_stuff_plus"].notna().mean()),
            "location_coverage": _number(rows["mean_location_plus"].notna().mean()),
            "result_coverage": _number(rows["result_score"].notna().mean()),
            "quality_state_coverage": _number(rows.get("quality_stamina_plus", pd.Series(index=rows.index)).notna().mean()),
            "physical_state_coverage": _number(rows.get("physical_stability_plus", pd.Series(index=rows.index)).notna().mean()),
            "command_state_coverage": _number(rows.get("command_retention_plus", pd.Series(index=rows.index)).notna().mean()),
        }
    audit = {
        "contract_version": CONTRACT_VERSION,
        "warehouse_version": WAREHOUSE_VERSION,
        "baseline_version": BASELINE_VERSION,
        "state_model_version": STATE_MODEL_VERSION,
        "status": "research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "development_year": development_year,
        "test_year": test_year,
        "data_as_of": {
            str(year): str(combined.loc[combined["year"].eq(year), "game_date"].max())[:10]
            for year in (development_year, test_year)
        },
        "source_modified_at": source_modified_at,
        "slice0": {"contract": contract, "label_audit": label_audit},
        "slice1": {
            "coverage": coverage,
            "leverage_reference_global_abs_wpa": _number(global_abs_wpa, 6),
            "leverage_states": int(len(li_reference)),
            "reference_parameters": reference,
            "warnings": [
                "Quality, Physical and Command game signals are starter-oriented and remain null for unsupported appearances.",
                "Game Score is a starter-only derived proxy because a complete 2025 official game-line source is unavailable.",
            ],
        },
        "slice2": baseline_audit,
        "slice3": state_audit,
        "slice3a": slice3a_audit,
    }
    _write_json_atomic(audit, audit_path(root))
    _cached_overview.cache_clear()
    return audit


@lru_cache(maxsize=2)
def _cached_overview(path_value: str, modified_at: int) -> dict[str, Any]:
    del modified_at
    return json.loads(Path(path_value).read_text(encoding="utf-8"))


def get_performance_state_overview(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = audit_path(root)
    if not path.exists():
        raise FileNotFoundError("Performance State Slices 0-3 have not been built.")
    payload = _cached_overview(str(path.resolve()), path.stat().st_mtime_ns).copy()
    warnings = list(payload.get("slice1", {}).get("warnings", []))
    stale_years: list[int] = []
    for year_text, stamp in payload.get("source_modified_at", {}).items():
        source = stamina_dataset_path(int(year_text), root)
        if source.exists() and source.stat().st_mtime_ns > int(stamp):
            stale_years.append(int(year_text))
    payload["dataset_status"] = "stale" if stale_years else "current"
    if stale_years:
        warnings.append(f"Source pitch datasets changed after the build for: {', '.join(map(str, stale_years))}.")
    try:
        from app.services.performance_state_advanced_service import get_performance_state_advanced_audit

        advanced = get_performance_state_advanced_audit(root)
        payload["advanced_model_version"] = advanced.get("model_version")
        payload["advanced_dataset_status"] = advanced.get("dataset_status")
        for slice_name in ("slice4", "slice5", "slice6"):
            payload[slice_name] = advanced.get(slice_name, {})
        warnings.extend(advanced.get("warnings", []))
    except FileNotFoundError:
        payload["advanced_model_version"] = None
        payload["advanced_dataset_status"] = "unavailable"
        warnings.append("Performance State Slices 4-6 have not been built.")
    try:
        from app.services.performance_state_advanced_service import get_performance_state_tail_audit

        tail = get_performance_state_tail_audit(root)
        payload["tail_model_version"] = tail.get("version")
        payload["tail_dataset_status"] = tail.get("dataset_status")
        payload["slice7"] = tail
        warnings.extend(tail.get("warnings", []))
    except FileNotFoundError:
        payload["tail_model_version"] = None
        payload["tail_dataset_status"] = "unavailable"
        warnings.append("Performance State Slice 7 has not been built.")
    try:
        from app.services.performance_state_forecast_service import get_performance_state_forecast_audit

        forecast = get_performance_state_forecast_audit(root)
        payload["forecast_model_version"] = forecast.get("model_version")
        payload["forecast_dataset_status"] = forecast.get("dataset_status")
        payload["slice8"] = forecast.get("slice8", {})
        payload["slice9"] = forecast.get("slice9", {})
        warnings.extend(forecast.get("warnings", []))
    except FileNotFoundError:
        payload["forecast_model_version"] = None
        payload["forecast_dataset_status"] = "unavailable"
        warnings.append("Performance State Slices 8-9 have not been built.")
    try:
        from app.services.performance_state_forecast_service import get_performance_state_shadow_audit

        shadow = get_performance_state_shadow_audit(root)
        payload["shadow_model_version"] = shadow.get("version")
        payload["shadow_dataset_status"] = shadow.get("dataset_status")
        payload["slice11"] = shadow
        warnings.extend(shadow.get("warnings", []))
    except FileNotFoundError:
        payload["shadow_model_version"] = None
        payload["shadow_dataset_status"] = "unavailable"
        warnings.append("Performance State Slice 11 has not been built.")
    payload["warnings"] = warnings
    return payload


def get_pitcher_performance_states(
    year: int,
    pitcher_id: int,
    role: str | None = None,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = filtered_state_path(year, root)
    if not path.exists():
        raise FileNotFoundError(f"Performance State artifact not found for {year}.")
    role_value = str(role or "").upper()
    if role_value and role_value not in ROLES:
        raise ValueError("role must be SP or RP.")
    where = "pitcher_id = ?"
    params: list[Any] = [str(path), int(pitcher_id)]
    if role_value:
        where += " AND role = ?"
        params.append(role_value)
    columns = [
        "pitcher_id", "pitcher_name", "team", "role", "game_pk", "game_date", "pitches",
        "calendar_days_since_prior", "plate_appearances", "mean_stuff_plus", "mean_location_plus",
        "re24", "re24_per_pa", "wpa", "wpa_li", "wpa_li_per_pa",
        "process_score", "result_score", "process_collapse", "result_collapse", "combined_collapse",
        "return_to_baseline", "strong_rebound", "excess_recovery",
        *[f"{signal}_{suffix}" for signal in STATE_SIGNALS for suffix in (
            "forecast", "forecast_sd", "filtered", "filtered_sd", "innovation", "standardized_innovation"
        )],
    ]
    with duckdb.connect() as connection:
        frame = connection.execute(
            f"SELECT {', '.join(columns)} FROM read_parquet(?) WHERE {where} ORDER BY game_date, game_pk",
            params,
        ).fetchdf()
        try:
            from app.services.performance_state_advanced_service import advanced_state_path

            advanced_path = advanced_state_path(year, root)
            if advanced_path.exists():
                advanced_where = "pitcher_id = ?"
                advanced_params: list[Any] = [str(advanced_path), int(pitcher_id)]
                if role_value:
                    advanced_where += " AND role = ?"
                    advanced_params.append(role_value)
                advanced = connection.execute(
                    f"SELECT * EXCLUDE (year, game_date) FROM read_parquet(?) WHERE {advanced_where}",
                    advanced_params,
                ).fetchdf()
                if not advanced.empty:
                    frame = frame.merge(
                        advanced,
                        on=["pitcher_id", "role", "game_pk"],
                        how="left",
                        validate="one_to_one",
                    )
        except (FileNotFoundError, ImportError):
            pass
        try:
            from app.services.performance_state_forecast_service import forecast_state_path

            forecast_path = forecast_state_path(year, root)
            if forecast_path.exists():
                forecast_where = "pitcher_id = ?"
                forecast_params: list[Any] = [str(forecast_path), int(pitcher_id)]
                if role_value:
                    forecast_where += " AND role = ?"
                    forecast_params.append(role_value)
                forecast = connection.execute(
                    f"SELECT * EXCLUDE (year, game_date) FROM read_parquet(?) WHERE {forecast_where}",
                    forecast_params,
                ).fetchdf()
                if not forecast.empty:
                    frame = frame.merge(
                        forecast,
                        on=["pitcher_id", "role", "game_pk"],
                        how="left",
                        validate="one_to_one",
                    )
        except (FileNotFoundError, ImportError):
            pass
        try:
            from app.services.performance_state_advanced_service import tail_state_path

            tail_path = tail_state_path(year, root)
            if tail_path.exists():
                tail_where = "pitcher_id = ?"
                tail_params: list[Any] = [str(tail_path), int(pitcher_id)]
                if role_value:
                    tail_where += " AND role = ?"
                    tail_params.append(role_value)
                tail = connection.execute(
                    f"SELECT * EXCLUDE (year, game_date) FROM read_parquet(?) WHERE {tail_where}",
                    tail_params,
                ).fetchdf()
                if not tail.empty:
                    frame = frame.merge(
                        tail,
                        on=["pitcher_id", "role", "game_pk"],
                        how="left",
                        validate="one_to_one",
                    )
        except (FileNotFoundError, ImportError):
            pass
    if frame.empty:
        raise ValueError(f"No Performance State rows found for pitcher {pitcher_id} in {year}.")
    frame["game_date"] = pd.to_datetime(frame["game_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    clean = frame.astype(object).where(pd.notna(frame), None).to_dict("records")
    return {
        "year": int(year),
        "pitcher_id": int(pitcher_id),
        "pitcher_name": str(frame.iloc[-1]["pitcher_name"]),
        "roles": sorted(frame["role"].dropna().astype(str).unique().tolist()),
        "model_version": STATE_MODEL_VERSION,
        "status": "research_only",
        "rows": clean,
        "warnings": ["Filtered performance states are not fatigue, health or injury estimates."],
    }
