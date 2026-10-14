from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.performance_state_service import (
    ROLES,
    _build_raw_warehouse,
    _leverage_reference,
    _load_pa_results,
    _number,
    _reference_parameters,
    _write_json_atomic,
    _write_parquet_atomic,
)
from app.services.stamina_lab_service import stamina_dataset_path


V2_VERSION = "performance_state_multiseason_v2"
ELIGIBILITY_VERSION = "performance_state_slice11a_eligibility_v1"
WAREHOUSE_VERSION = "performance_state_multiseason_warehouse_v1"
VALIDATION_VERSION = "performance_state_expanding_window_v1"
YEARS = (2023, 2024, 2025, 2026)
FEATURES = [
    "lag_process_score",
    "lag_result_score",
    "process_ma5",
    "process_ewm",
    "lag_process_volatility",
    "calendar_days_since_prior",
    "workload_pitches_7d",
    "workload_pitches_28d",
    "previous_appearance_pitches",
]
TARGETS = (
    "process_collapse",
    "result_collapse",
    "onset_process_collapse",
    "persistent_process_collapse",
    "return_to_baseline",
    "strong_rebound",
)
MEASURES = (
    "mean_stuff_plus",
    "mean_location_plus",
    "first10_stuff_plus",
    "first10_location_plus",
    "first20_stuff_plus",
    "first20_location_plus",
    "re24_per_pa",
    "wpa_li_per_pa",
    "game_score_proxy",
)


def v2_audit_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_slice11a_13.json"


def v2_contract_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "performance_state_v2_contract.json"


def v2_warehouse_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"performance_state_v2_warehouse_{int(year)}.parquet"


def v2_fold_predictions_path(test_year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"performance_state_v2_predictions_{int(test_year)}.parquet"


def _position_player_ids(year: int, root: Path) -> tuple[set[int], dict[int, int]]:
    db_path = get_season_duckdb_path(year, root)
    with duckdb.connect(str(db_path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        source = resolve_pitch_table(tables)
        if not source:
            return set(), {}
        columns = {row[0] for row in connection.execute(f"DESCRIBE {source}").fetchall()}
        fielder_columns = [column for column in (f"fielder_{number}" for number in range(2, 10)) if column in columns]
        if not fielder_columns:
            return set(), {}
        unions = " UNION ALL ".join(
            f"SELECT game_pk, try_cast({column} AS BIGINT) player_id FROM {source} "
            f"WHERE game_type = 'R' AND {column} IS NOT NULL"
            for column in fielder_columns
        )
        rows = connection.execute(
            f"SELECT player_id, count(DISTINCT game_pk) defensive_games FROM ({unions}) "
            "WHERE player_id IS NOT NULL GROUP BY player_id"
        ).fetchall()
    games = {int(player_id): int(count) for player_id, count in rows}
    return set(games), games


def _add_eligibility(frame: pd.DataFrame, position_players: set[int], defensive_games: dict[int, int]) -> pd.DataFrame:
    output = frame.copy()
    season = output.groupby(["year", "pitcher_id"], as_index=False).agg(
        season_pitching_appearances=("game_pk", "nunique"),
        season_pitch_count=("pitches", "sum"),
        season_max_appearance_pitches=("pitches", "max"),
    )
    output = output.merge(season, on=["year", "pitcher_id"], how="left", validate="many_to_one")
    output["defensive_position_games"] = output["pitcher_id"].map(defensive_games).fillna(0).astype(int)
    output["position_player_pitching"] = output["pitcher_id"].isin(position_players)
    output["low_volume_emergency"] = (
        output["season_pitch_count"].lt(60)
        & output["season_pitching_appearances"].le(4)
        & output["season_max_appearance_pitches"].le(40)
    )
    pitch_denominator = output["pitches"].replace(0, np.nan)
    output["stuff_coverage"] = output["stuff_pitches"] / pitch_denominator
    output["location_coverage"] = output["location_pitches"] / pitch_denominator
    output["plus_coverage"] = output[["stuff_coverage", "location_coverage"]].min(axis=1)
    output["appearance_type"] = "reliever"
    output.loc[
        output["role"].eq("RP") & (output["pitches"].ge(40) | output["plate_appearances"].ge(12)),
        "appearance_type",
    ] = "bulk_reliever"
    opener = output["role"].eq("SP") & output["pitches"].lt(45) & output["plate_appearances"].le(12)
    traditional = output["role"].eq("SP") & (output["pitches"].ge(70) | output["plate_appearances"].ge(18))
    output.loc[output["role"].eq("SP"), "appearance_type"] = "short_starter"
    output.loc[opener, "appearance_type"] = "opener_like"
    output.loc[traditional, "appearance_type"] = "traditional_starter"
    output["model_eligible"] = (
        ~output["position_player_pitching"]
        & ~output["low_volume_emergency"]
        & output["plus_coverage"].ge(0.80)
        & (
            (output["role"].eq("SP") & ~output["appearance_type"].eq("opener_like") & output["pitches"].ge(45))
            | (output["role"].eq("RP") & output["pitches"].ge(5))
        )
    )
    output["eligibility_exclusion"] = np.select(
        [
            output["position_player_pitching"],
            output["low_volume_emergency"],
            output["plus_coverage"].lt(0.80),
            output["appearance_type"].eq("opener_like"),
            output["role"].eq("SP") & output["pitches"].lt(45),
            output["role"].eq("RP") & output["pitches"].lt(5),
        ],
        ["position_player_pitching", "low_volume_emergency", "plus_coverage_below_80pct", "opener_like", "short_sp_under_45", "rp_under_5"],
        default="eligible",
    )
    return output


def _eligibility_audit(frame: pd.DataFrame) -> dict[str, Any]:
    yearly: dict[str, Any] = {}
    for year in YEARS:
        rows = frame[frame["year"].eq(year)]
        yearly[str(year)] = {
            "appearances": int(len(rows)),
            "pitchers": int(rows["pitcher_id"].nunique()),
            "eligible_appearances": int(rows["model_eligible"].sum()),
            "eligible_pct": _number(rows["model_eligible"].mean()),
            "position_player_pitching_appearances": int(rows["position_player_pitching"].sum()),
            "position_player_pitchers": int(rows.loc[rows["position_player_pitching"], "pitcher_id"].nunique()),
            "low_volume_emergency_appearances": int(rows["low_volume_emergency"].sum()),
            "appearance_types": {str(key): int(value) for key, value in rows["appearance_type"].value_counts().items()},
            "exclusions": {str(key): int(value) for key, value in rows["eligibility_exclusion"].value_counts().items()},
        }
    return {
        "version": ELIGIBILITY_VERSION,
        "rules": {
            "position_player_pitching": "Pitcher MLBAM ID appears in Statcast catcher/infield/outfield fielder slots during the same season.",
            "low_volume_emergency": "Season hindsight audit flag: fewer than 60 pitches, at most four pitching appearances and no appearance above 40 pitches.",
            "opener_like": "Started, fewer than 45 pitches and at most 12 batters faced; this is a workload heuristic, not an official opener designation.",
            "traditional_starter": "Started with at least 70 pitches or 18 batters faced.",
            "bulk_reliever": "Relief appearance with at least 40 pitches or 12 batters faced.",
            "model_eligible": "Not position-player pitching or low-volume emergency, at least 80% Stuff+/Location+ coverage, RP at least five pitches, and SP at least 45 pitches excluding opener-like starts.",
        },
        "hindsight_warning": "The low-volume emergency flag uses completed-season totals and is cohort cleaning only, never a pregame model feature. Official historical roster position remains the preferred production source.",
        "yearly": yearly,
    }


def _causal_residuals(
    frame: pd.DataFrame,
    column: str,
    reference: dict[str, dict[str, float]],
    train_years: tuple[int, ...],
    prior_appearances: float = 5.0,
) -> tuple[pd.Series, pd.Series]:
    expected = pd.Series(np.nan, index=frame.index, dtype=float)
    residual = pd.Series(np.nan, index=frame.index, dtype=float)
    ordered = frame.sort_values(["pitcher_id", "role", "game_date", "game_pk"], kind="stable")
    for (_, role), group in ordered.groupby(["pitcher_id", "role"], sort=False):
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
    standardized = pd.Series(np.nan, index=frame.index, dtype=float)
    for role in ROLES:
        role_mask = frame["role"].eq(role)
        train_values = residual[role_mask & frame["year"].isin(train_years)].dropna()
        scale = max(float(train_values.std(ddof=1)), 1e-6) if len(train_values) > 1 else 1.0
        standardized.loc[role_mask] = residual.loc[role_mask] / scale
    return expected, standardized


def _prepare_fold(frame: pd.DataFrame, train_years: tuple[int, ...], test_year: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    working = frame[frame["year"].isin((*train_years, test_year))].copy()
    reference = _reference_parameters(working[working["year"].isin(train_years)])
    for column in MEASURES:
        expected, standardized = _causal_residuals(working, column, reference, train_years)
        working[f"{column}_expected"] = expected
        working[f"{column}_z"] = standardized
    working["process_score"] = working[["mean_stuff_plus_z", "mean_location_plus_z"]].mean(axis=1, skipna=True)
    working["result_score"] = working[["re24_per_pa_z", "wpa_li_per_pa_z"]].mean(axis=1, skipna=True)
    thresholds: dict[str, dict[str, float]] = {}
    for role in ROLES:
        train = working[working["year"].isin(train_years) & working["role"].eq(role)]
        thresholds[role] = {}
        for score in ("process_score", "result_score"):
            values = train[score].dropna()
            threshold = float(values.quantile(0.05)) if len(values) else -1.645
            thresholds[role][score] = threshold
            working.loc[working["role"].eq(role), f"{score}_collapse"] = working.loc[working["role"].eq(role), score].le(threshold)
    working["process_collapse"] = working["process_score_collapse"].fillna(False).astype(bool)
    working["result_collapse"] = working["result_score_collapse"].fillna(False).astype(bool)
    working = working.sort_values(["pitcher_id", "role", "game_date", "game_pk"], kind="stable")
    groups = working.groupby(["pitcher_id", "role"], sort=False)
    working["calendar_days_since_prior"] = groups["game_date"].diff().dt.days.astype(float)
    working["lag_process_score"] = groups["process_score"].shift(1)
    working["lag_result_score"] = groups["result_score"].shift(1)
    working["lag_process_collapse"] = groups["process_collapse"].shift(1).fillna(False).astype(bool)
    working["process_ma5"] = groups["process_score"].transform(lambda values: values.shift(1).rolling(5, min_periods=2).mean())
    working["process_ewm"] = groups["process_score"].transform(lambda values: values.shift(1).ewm(span=5, adjust=False, min_periods=2).mean())
    working["lag_process_volatility"] = groups["process_score"].transform(lambda values: values.shift(1).rolling(5, min_periods=3).std())
    working["process_improvement"] = working["process_score"] - working["lag_process_score"]
    working["onset_process_collapse"] = working["process_collapse"] & ~working["lag_process_collapse"]
    working["persistent_process_collapse"] = working["process_collapse"] & working["lag_process_collapse"]
    working["return_to_baseline"] = working["lag_process_collapse"] & working["process_score"].ge(-0.50)
    working["strong_rebound"] = working["lag_process_collapse"] & working["process_score"].ge(0.50)
    return working.reset_index(drop=True), thresholds


def _metric_summary(truth: pd.Series, probabilities: np.ndarray) -> dict[str, Any]:
    actual = truth.astype(int).to_numpy()
    predicted = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    if len(actual) == 0 or len(np.unique(actual)) < 2:
        return {"rows": int(len(actual)), "events": int(actual.sum()), "prevalence": _number(actual.mean()) if len(actual) else None, "average_precision": None, "brier": None, "log_loss": None}
    return {
        "rows": int(len(actual)),
        "events": int(actual.sum()),
        "prevalence": _number(actual.mean()),
        "average_precision": _number(average_precision_score(actual, predicted)),
        "brier": _number(brier_score_loss(actual, predicted)),
        "log_loss": _number(log_loss(actual, predicted, labels=[0, 1])),
    }


def _target_rows(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    rows = frame.copy()
    if target in {"persistent_process_collapse", "return_to_baseline", "strong_rebound"}:
        rows = rows[rows["lag_process_collapse"]]
    elif target == "onset_process_collapse":
        rows = rows[~rows["lag_process_collapse"]]
    return rows


def _evaluate_fold(frame: pd.DataFrame, train_years: tuple[int, ...], test_year: int) -> tuple[dict[str, Any], pd.DataFrame]:
    prepared, thresholds = _prepare_fold(frame, train_years, test_year)
    fold: dict[str, Any] = {
        "train_years": list(train_years),
        "test_year": test_year,
        "thresholds": thresholds,
        "selection_allowed": test_year < 2026,
        "cohorts": {},
    }
    predictions: list[pd.DataFrame] = []
    for cohort, clean_only in (("raw", False), ("clean", True)):
        cohort_payload: dict[str, Any] = {}
        population = prepared[prepared["model_eligible"]] if clean_only else prepared
        for role in ROLES:
            role_payload: dict[str, Any] = {"targets": {}}
            role_rows = population[population["role"].eq(role)]
            test_role = role_rows[role_rows["year"].eq(test_year)]
            continuous: dict[str, Any] = {}
            for name, column in (("last", "lag_process_score"), ("ma5", "process_ma5"), ("ewma5", "process_ewm")):
                valid = test_role.dropna(subset=["process_score", column])
                continuous[name] = {
                    "rows": int(len(valid)),
                    "rmse": _number(math.sqrt(mean_squared_error(valid["process_score"], valid[column]))) if len(valid) else None,
                    "mae": _number(mean_absolute_error(valid["process_score"], valid[column])) if len(valid) else None,
                }
            role_payload["continuous_process"] = continuous
            for target in TARGETS:
                eligible = _target_rows(role_rows, target)
                train = eligible[eligible["year"].isin(train_years)].copy()
                test = eligible[eligible["year"].eq(test_year)].copy()
                train = train[train[FEATURES].notna().sum(axis=1).ge(2)]
                test = test[test[FEATURES].notna().sum(axis=1).ge(2)]
                prevalence = float(train[target].mean()) if len(train) else 0.5
                baseline = np.full(len(test), prevalence)
                model_metrics = {"rows": int(len(test)), "events": int(test[target].sum()) if len(test) else 0, "prevalence": _number(test[target].mean()) if len(test) else None, "average_precision": None, "brier": None, "log_loss": None}
                probabilities = baseline
                coefficients: list[dict[str, Any]] = []
                if len(train) and len(test) and train[target].nunique() == 2:
                    model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(max_iter=2000, C=0.5))
                    model.fit(train[FEATURES], train[target].astype(int))
                    probabilities = model.predict_proba(test[FEATURES])[:, 1]
                    model_metrics = _metric_summary(test[target], probabilities)
                    logistic = model.named_steps["logisticregression"]
                    coefficients = sorted(
                        ({"feature": feature, "coefficient": _number(value), "absolute": _number(abs(value))} for feature, value in zip(FEATURES, logistic.coef_[0], strict=True)),
                        key=lambda row: float(row["absolute"] or 0),
                        reverse=True,
                    )
                role_payload["targets"][target] = {
                    "train_rows": int(len(train)),
                    "test_rows": int(len(test)),
                    "logistic": model_metrics,
                    "train_prevalence_baseline": _metric_summary(test[target], baseline) if len(test) else model_metrics,
                    "standardized_coefficients": coefficients,
                }
                if len(test):
                    result = test[["year", "pitcher_id", "pitcher_name", "team", "role", "game_pk", "game_date", "appearance_type", "model_eligible"]].copy()
                    result["cohort"] = cohort
                    result["target"] = target
                    result["probability"] = probabilities
                    result["actual"] = test[target].astype(bool).to_numpy()
                    predictions.append(result)
            cohort_payload[role] = role_payload
        fold["cohorts"][cohort] = cohort_payload
    output = pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()
    return fold, output


def refresh_performance_state_v2(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    leverage_reference, global_abs_wpa = _leverage_reference(_load_pa_results(2023, root))
    yearly: dict[int, pd.DataFrame] = {}
    for year in YEARS:
        raw = _build_raw_warehouse(year, root, leverage_reference)
        position_players, defensive_games = _position_player_ids(year, root)
        enriched = _add_eligibility(raw, position_players, defensive_games)
        yearly[year] = enriched
        _write_parquet_atomic(enriched, v2_warehouse_path(year, root), f"performance_state_v2_warehouse_{year}")
    combined = pd.concat(yearly.values(), ignore_index=True)
    folds: list[dict[str, Any]] = []
    for train_years, test_year in (((2023,), 2024), ((2023, 2024), 2025), ((2023, 2024, 2025), 2026)):
        fold, predictions = _evaluate_fold(combined, train_years, test_year)
        folds.append(fold)
        _write_parquet_atomic(predictions, v2_fold_predictions_path(test_year, root), f"performance_state_v2_predictions_{test_year}")
    contract = {
        "version": V2_VERSION,
        "status": "research_only",
        "years": list(YEARS),
        "roles": list(ROLES),
        "features": FEATURES,
        "targets": list(TARGETS),
        "time_contract": "Expanding-window folds only: 2023→2024, 2023-24→2025, 2023-25→2026. Test years never fit coefficients, thresholds, scales or imputation.",
        "plus_model_warning": "Historical Plus scores were retrospectively generated with the same current frozen models. Folds test the Performance State layer, not pristine historical out-of-sample Stuff+/Location+ model training.",
        "release_rule": "No v1 artifact, leaderboard, shadow ledger or product integration is overwritten by Slices 11A-13.",
    }
    _write_json_atomic(contract, v2_contract_path(root))
    coverage = {}
    for year, rows in yearly.items():
        coverage[str(year)] = {
            "rows": int(len(rows)),
            "unique_keys": int(rows[["pitcher_id", "role", "game_pk"]].drop_duplicates().shape[0]),
            "pitchers": int(rows["pitcher_id"].nunique()),
            "data_as_of": str(pd.to_datetime(rows["game_date"]).max())[:10],
            "stuff_coverage": _number(rows["mean_stuff_plus"].notna().mean()),
            "location_coverage": _number(rows["mean_location_plus"].notna().mean()),
            "result_coverage": _number((rows["re24_per_pa"].notna() & rows["wpa_li_per_pa"].notna()).mean()),
        }
    audit = {
        "version": V2_VERSION,
        "status": "research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_modified_at": {str(year): int(stamina_dataset_path(year, root).stat().st_mtime_ns) for year in YEARS},
        "slice11a": _eligibility_audit(combined),
        "slice12": {
            "version": WAREHOUSE_VERSION,
            "years": list(YEARS),
            "coverage": coverage,
            "leverage_reference_year": 2023,
            "leverage_reference_global_abs_wpa": _number(global_abs_wpa, 6),
            "v1_artifacts_overwritten": False,
        },
        "slice13": {
            "version": VALIDATION_VERSION,
            "folds": folds,
            "model_selection_years": [2024, 2025],
            "diagnostic_only_year": 2026,
            "prospective_untouched_year": 2027,
            "warnings": [contract["plus_model_warning"], "The low-volume emergency exclusion is a hindsight cohort audit and not a deployable pregame feature."],
        },
    }
    _write_json_atomic(audit, v2_audit_path(root))
    return audit


def get_performance_state_v2_audit(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = v2_audit_path(root)
    if not path.exists():
        raise FileNotFoundError("Performance State Slices 11A-13 have not been built.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    stale = [
        int(year)
        for year, stamp in payload.get("source_modified_at", {}).items()
        if stamina_dataset_path(int(year), root).exists() and stamina_dataset_path(int(year), root).stat().st_mtime_ns > int(stamp)
    ]
    payload["dataset_status"] = "stale" if stale else "current"
    if stale:
        payload.setdefault("slice13", {}).setdefault("warnings", []).append(f"Source datasets changed after build for: {', '.join(map(str, stale))}.")
    return payload
