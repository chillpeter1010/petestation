from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import joblib
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from app.core.config import settings
from app.services.player_archetype_slice4_service import slice4_warehouse_path
from app.services.player_archetype_slice5_service import slice5_prediction_path
from app.services.player_archetype_slice6ab_service import (
    _attach_years,
    _copy_atomic,
    _load_stuff_scores,
    _number,
    _rows,
    _sql_path,
    _threat_surface_query,
    _weapon_candidate_query,
    slice6a_candidate_path,
    slice6b_surface_path,
)


CONTRACT_VERSION = "player_archetype_slice6c_supported_value_v1"
TRAIN_YEAR = 2025
TEST_YEAR = 2026
TRAIN_WEAPON_YEARS = (2024, 2025)
TRAIN_THREAT_YEARS = tuple(range(2021, 2025))
MIN_WEAPON_PITCHES = 20
MIN_THREAT_PITCHES = 30
DEFAULT_PROPENSITY = 0.025
PROPENSITY_THRESHOLDS = (0.01, 0.025, 0.05, 0.10)
WEIGHT_CAPS = (5.0, 10.0, 20.0)
VALIDATION_CUTOFF = "2025-07-01"

CATEGORICAL_FEATURES = [
    "candidate_pitch_type",
    "candidate_pitch_family",
    "pitcher_throws",
    "batter_side",
    "pitcher_role",
    "count_state",
    "count_tier",
    "base_state",
]
NUMERIC_FEATURES = [
    "balls",
    "strikes",
    "outs",
    "inning",
    "appearance_pitch_number",
    "baseline_stuff_plus",
    "baseline_location_plus",
    "weapon_stuff_plus",
    "weapon_location_plus",
    "weapon_stuff_delta",
    "weapon_location_delta",
    "outing_stuff_reliability",
    "outing_location_reliability",
    "pregame_usage_rate",
    "outing_usage_rate",
    "threat_hunt_plus",
    "threat_contact_plus",
    "threat_damage_plus",
    "threat_damage_run_value_per_pitch",
    "threat_sample_reliability",
]
MODEL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def slice6c_contract_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice6c.json"


def slice6c_training_weapon_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice6c_weapon_chosen_2025.parquet"


def slice6c_training_threat_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice6c_threat_through_2024.parquet"


def slice6c_training_frame_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice6c_value_train_2025.parquet"


def slice6c_model_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice6c_value_model.joblib"


def slice6c_candidate_value_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice6c_candidate_values_2026.parquet"


def slice6c_decision_value_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice6c_decision_values_2026.parquet"


def slice6c_report_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "PLAYER_ARCHETYPES_PITCH_STRATEGY.md"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _propensity_case(candidate: str = "c.candidate_pitch_type") -> str:
    known = ("FF", "SI", "FC", "SL", "ST", "CU", "KC", "SV", "CH", "FS", "FO", "SC")
    clauses = "\n".join(f"WHEN '{pitch}' THEN p.prob_type_{pitch.lower()}" for pitch in known)
    return f"CASE {candidate} {clauses} ELSE p.prob_type_other END"


def _feature_select(
    weapon_path: Path,
    threat_path: Path,
    warehouse_path: Path,
    predictions_path: Path | None = None,
) -> str:
    propensity_select = (
        f", {_propensity_case()} AS candidate_propensity"
        if predictions_path is not None
        else ", NULL::DOUBLE AS candidate_propensity"
    )
    prediction_join = (
        f"JOIN read_parquet('{_sql_path(predictions_path)}') p USING (decision_id)"
        if predictions_path is not None
        else ""
    )
    return f"""
        WITH batter_surface AS (
            SELECT * FROM read_parquet('{_sql_path(threat_path)}')
            WHERE surface_level = 'batter' AND location_bucket = 'All'
        ),
        league_surface AS (
            SELECT * FROM read_parquet('{_sql_path(threat_path)}')
            WHERE surface_level = 'league' AND location_bucket = 'All'
        )
        SELECT
            c.*,
            w.observed_delta_run_exp,
            coalesce(b.pitches, 0)::BIGINT AS threat_pitches,
            coalesce(b.support_level, 'league_fallback') AS threat_support_level,
            coalesce(b.sample_reliability, 0.0) AS threat_sample_reliability,
            coalesce(b.hunt_plus, l.hunt_plus) AS threat_hunt_plus,
            coalesce(b.contact_plus, l.contact_plus) AS threat_contact_plus,
            coalesce(b.damage_plus, l.damage_plus) AS threat_damage_plus,
            coalesce(b.damage_run_value_per_pitch, l.damage_run_value_per_pitch)
                AS threat_damage_run_value_per_pitch
            {propensity_select}
        FROM read_parquet('{_sql_path(weapon_path)}') c
        JOIN read_parquet('{_sql_path(warehouse_path)}') w USING (decision_id)
        {prediction_join}
        LEFT JOIN batter_surface b
          ON b.batter_id = c.batter_id
         AND b.pitcher_throws = c.pitcher_throws
         AND b.count_tier = c.count_tier
         AND b.pitch_family = c.candidate_pitch_family
        JOIN league_surface l
          ON l.pitcher_throws = c.pitcher_throws
         AND l.count_tier = c.count_tier
         AND l.pitch_family = c.candidate_pitch_family
    """


def _model() -> Pipeline:
    categorical = Pipeline(
        [
            (
                "encode",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                    encoded_missing_value=-1,
                ),
            )
        ]
    )
    numeric = Pipeline([("impute", SimpleImputer(strategy="median"))])
    preprocessing = ColumnTransformer(
        [("categorical", categorical, CATEGORICAL_FEATURES), ("numeric", numeric, NUMERIC_FEATURES)],
        remainder="drop",
    )
    categorical_mask = [True] * len(CATEGORICAL_FEATURES) + [False] * len(NUMERIC_FEATURES)
    regressor = HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=0.05,
        max_iter=120,
        max_leaf_nodes=15,
        min_samples_leaf=500,
        l2_regularization=10.0,
        categorical_features=categorical_mask,
        random_state=42,
    )
    return Pipeline([("preprocess", preprocessing), ("model", regressor)])


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float | int]:
    return {
        "rows": int(len(actual)),
        "rmse": _number(math.sqrt(mean_squared_error(actual, predicted))),
        "mae": _number(mean_absolute_error(actual, predicted)),
    }


def _predict_parquet(
    model: Pipeline,
    feature_path: Path,
    output_path: Path,
    interval_half_width: float,
) -> None:
    temporary = output_path.with_suffix(".tmp.parquet")
    if temporary.exists():
        temporary.unlink()
    writer: pq.ParquetWriter | None = None
    try:
        parquet = pq.ParquetFile(feature_path)
        for batch in parquet.iter_batches(batch_size=100_000):
            table = pa.Table.from_batches([batch])
            frame = table.select(MODEL_FEATURES).to_pandas()
            prediction = model.predict(frame).astype("float64")
            table = table.append_column("predicted_batter_run_value", pa.array(prediction))
            table = table.append_column(
                "prediction_lower_90", pa.array(prediction - interval_half_width)
            )
            table = table.append_column(
                "prediction_upper_90", pa.array(prediction + interval_half_width)
            )
            if writer is None:
                writer = pq.ParquetWriter(temporary, table.schema, compression="zstd")
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()
    temporary.replace(output_path)


def _decision_query(candidate_values: Path) -> str:
    path = _sql_path(candidate_values)
    return f"""
        WITH candidates AS (
            SELECT *,
                   pregame_type_pitches >= {MIN_WEAPON_PITCHES}
                   AND threat_pitches >= {MIN_THREAT_PITCHES}
                   AND candidate_propensity >= {DEFAULT_PROPENSITY}
                   AS supported_candidate
            FROM read_parquet('{path}')
        ),
        counts AS (
            SELECT decision_id,
                   count(*) FILTER (WHERE supported_candidate) AS supported_candidates,
                   count(*) FILTER (WHERE supported_candidate AND NOT is_chosen) AS supported_alternatives
            FROM candidates GROUP BY 1
        ),
        chosen AS (
            SELECT decision_id, game_date, game_pk, at_bat_number, pitch_number,
                   pitcher_id, batter_id, catcher_id, pitcher_throws, batter_side,
                   pitcher_role, count_state, count_tier, outs, base_state, inning,
                   candidate_pitch_type AS chosen_pitch_type,
                   candidate_propensity AS chosen_propensity,
                   weapon_backoff_level AS chosen_weapon_backoff_level,
                   threat_support_level AS chosen_threat_support_level,
                   predicted_batter_run_value AS chosen_predicted_run_value,
                   prediction_lower_90 AS chosen_prediction_lower_90,
                   prediction_upper_90 AS chosen_prediction_upper_90,
                   supported_candidate AS chosen_supported
            FROM candidates WHERE is_chosen
        ),
        alternatives AS (
            SELECT decision_id, candidate_pitch_type AS best_supported_alternative,
                   candidate_propensity AS alternative_propensity,
                   predicted_batter_run_value AS alternative_predicted_run_value,
                   prediction_lower_90 AS alternative_prediction_lower_90,
                   prediction_upper_90 AS alternative_prediction_upper_90
            FROM candidates
            WHERE supported_candidate AND NOT is_chosen
            QUALIFY row_number() OVER (
                PARTITION BY decision_id ORDER BY predicted_batter_run_value, candidate_pitch_type
            ) = 1
        )
        SELECT c.decision_id, c.game_date, c.game_pk, c.at_bat_number, c.pitch_number,
               c.pitcher_id, c.batter_id, c.catcher_id, c.pitcher_throws, c.batter_side,
               c.pitcher_role, c.count_state, c.count_tier, c.outs, c.base_state, c.inning,
               c.chosen_pitch_type, c.chosen_propensity,
               c.chosen_weapon_backoff_level, c.chosen_threat_support_level,
               c.chosen_supported, n.supported_candidates, n.supported_alternatives,
               a.best_supported_alternative, a.alternative_propensity,
               c.chosen_predicted_run_value, a.alternative_predicted_run_value,
               c.chosen_predicted_run_value - a.alternative_predicted_run_value
                   AS predicted_gap_vs_best_alternative,
               c.chosen_prediction_lower_90, c.chosen_prediction_upper_90,
               a.alternative_prediction_lower_90, a.alternative_prediction_upper_90,
               c.chosen_prediction_lower_90 > a.alternative_prediction_upper_90
                   AS intervals_separate_in_alternative_favor,
               'supported_observational_comparison_not_causal' AS interpretation_scope
        FROM chosen c
        JOIN counts n USING (decision_id)
        LEFT JOIN alternatives a USING (decision_id)
        ORDER BY c.game_date, c.game_pk, c.at_bat_number, c.pitch_number
    """


def build_player_archetype_slice6c(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    training_weapon = slice6c_training_weapon_path(root)
    training_threat = slice6c_training_threat_path(root)
    training_frame = slice6c_training_frame_path(root)
    candidate_values = slice6c_candidate_value_path(root)
    decision_values = slice6c_decision_value_path(root)
    model_path = slice6c_model_path(root)
    current_weapon = slice6a_candidate_path(root)
    current_threat = slice6b_surface_path(root)
    prediction_path = slice5_prediction_path(root)
    for source in (
        slice4_warehouse_path(TRAIN_YEAR, root),
        slice4_warehouse_path(TEST_YEAR, root),
        current_weapon,
        current_threat,
        prediction_path,
        root / "derived" / "location_plus_scores.duckdb",
    ):
        if not source.exists():
            raise FileNotFoundError(source)

    location_db = root / "derived" / "location_plus_scores.duckdb"
    stuff_scores = _load_stuff_scores(root, TRAIN_WEAPON_YEARS)
    with duckdb.connect() as connection:
        connection.execute("SET preserve_insertion_order = false")
        tables = _attach_years(connection, TRAIN_WEAPON_YEARS, root)
        connection.execute(f"ATTACH '{_sql_path(location_db)}' AS loc (READ_ONLY)")
        connection.register("stuff_scores", stuff_scores)
        chosen_query = _weapon_candidate_query(
            slice4_warehouse_path(TRAIN_YEAR, root),
            tables,
            target_year=TRAIN_YEAR,
            history_years=TRAIN_WEAPON_YEARS,
        )
        _copy_atomic(connection, f"SELECT * FROM ({chosen_query}) WHERE is_chosen", training_weapon)
    del stuff_scores

    with duckdb.connect() as connection:
        connection.execute("SET preserve_insertion_order = false")
        tables = _attach_years(connection, TRAIN_THREAT_YEARS, root)
        _copy_atomic(
            connection,
            _threat_surface_query(tables, TRAIN_THREAT_YEARS),
            training_threat,
        )

    with duckdb.connect() as connection:
        _copy_atomic(
            connection,
            _feature_select(
                training_weapon,
                training_threat,
                slice4_warehouse_path(TRAIN_YEAR, root),
            ),
            training_frame,
        )

    train = pd.read_parquet(training_frame)
    train = train.loc[train["observed_delta_run_exp"].notna()].copy()
    train["game_date"] = pd.to_datetime(train["game_date"])
    development = train.loc[train["game_date"] < VALIDATION_CUTOFF]
    validation = train.loc[train["game_date"] >= VALIDATION_CUTOFF]
    validation_model = _model()
    validation_model.fit(development[MODEL_FEATURES], development["observed_delta_run_exp"])
    validation_prediction = validation_model.predict(validation[MODEL_FEATURES])
    validation_actual = validation["observed_delta_run_exp"].to_numpy(dtype=float)
    validation_mean = np.full(len(validation), development["observed_delta_run_exp"].mean())
    validation_threat = validation["threat_damage_run_value_per_pitch"].to_numpy(dtype=float)
    interval_half_width = float(np.quantile(np.abs(validation_actual - validation_prediction), 0.90))
    validation_metrics = {
        "model": _metrics(validation_actual, validation_prediction),
        "training_mean": _metrics(validation_actual, validation_mean),
        "threat_only": _metrics(validation_actual, validation_threat),
        "absolute_residual_q90": _number(interval_half_width),
    }

    final_model = _model()
    final_model.fit(train[MODEL_FEATURES], train["observed_delta_run_exp"])
    temporary_model = model_path.with_suffix(".tmp.joblib")
    joblib.dump(
        {
            "contract_version": CONTRACT_VERSION,
            "features": MODEL_FEATURES,
            "model": final_model,
            "interval_half_width_90": interval_half_width,
            "train_year": TRAIN_YEAR,
        },
        temporary_model,
    )
    temporary_model.replace(model_path)
    del train, development, validation, validation_model

    feature_temp = candidate_values.with_suffix(".features.tmp.parquet")
    with duckdb.connect() as connection:
        _copy_atomic(
            connection,
            _feature_select(
                current_weapon,
                current_threat,
                slice4_warehouse_path(TEST_YEAR, root),
                prediction_path,
            ),
            feature_temp,
        )
    _predict_parquet(final_model, feature_temp, candidate_values, interval_half_width)
    feature_temp.unlink()

    with duckdb.connect() as connection:
        _copy_atomic(connection, _decision_query(candidate_values), decision_values)

        candidate_path = _sql_path(candidate_values)
        decision_path = _sql_path(decision_values)
        warehouse_path = _sql_path(slice4_warehouse_path(TEST_YEAR, root))
        candidate_audit = connection.execute(
            f"""
            SELECT count(*) AS row_count,
                   count(DISTINCT decision_id) decisions,
                   count(*) FILTER (WHERE is_chosen) chosen_rows,
                   count(*) FILTER (WHERE candidate_propensity IS NULL OR candidate_propensity < 0
                                      OR candidate_propensity > 1) bad_propensity_rows,
                   count(*) FILTER (WHERE predicted_batter_run_value IS NULL) null_prediction_rows
            FROM read_parquet('{candidate_path}')
            """
        ).fetchone()
        decision_audit = connection.execute(
            f"""
            SELECT count(*) AS row_count,
                   count(*) - count(DISTINCT decision_id) AS duplicates,
                   count(*) FILTER (WHERE supported_candidates >= 2) multi_candidate_decisions,
                   count(*) FILTER (WHERE chosen_supported) chosen_supported_decisions,
                   count(*) FILTER (WHERE best_supported_alternative IS NOT NULL) alternative_decisions,
                   count(*) FILTER (WHERE intervals_separate_in_alternative_favor) interval_separated_decisions,
                   avg(predicted_gap_vs_best_alternative)
                     FILTER (WHERE predicted_gap_vs_best_alternative IS NOT NULL) mean_predicted_gap
            FROM read_parquet('{decision_path}')
            """
        ).fetchone()
        test_frame = connection.execute(
            f"""
            SELECT c.observed_delta_run_exp actual,
                   c.predicted_batter_run_value predicted,
                   c.threat_damage_run_value_per_pitch threat
            FROM read_parquet('{candidate_path}') c
            WHERE c.is_chosen AND c.observed_delta_run_exp IS NOT NULL
            """
        ).fetchdf()
        test_actual = test_frame["actual"].to_numpy(dtype=float)
        test_prediction = test_frame["predicted"].to_numpy(dtype=float)
        test_mean = np.full(len(test_frame), float(test_frame["actual"].mean()))
        test_threat = test_frame["threat"].to_numpy(dtype=float)
        test_metrics = {
            "model": _metrics(test_actual, test_prediction),
            "test_mean_descriptive_only": _metrics(test_actual, test_mean),
            "threat_only": _metrics(test_actual, test_threat),
        }

        overlap = []
        for threshold in PROPENSITY_THRESHOLDS:
            row = connection.execute(
                f"""
                WITH eligible AS (
                    SELECT decision_id, is_chosen,
                           pregame_type_pitches >= {MIN_WEAPON_PITCHES}
                           AND threat_pitches >= {MIN_THREAT_PITCHES}
                           AND candidate_propensity >= {float(threshold)} AS supported
                    FROM read_parquet('{candidate_path}')
                ), decision_counts AS (
                    SELECT decision_id, count(*) FILTER (WHERE supported) supported_candidates,
                           bool_or(is_chosen AND supported) chosen_supported
                    FROM eligible GROUP BY 1
                )
                SELECT count(*) FILTER (WHERE supported_candidates >= 2),
                       count(*) FILTER (WHERE chosen_supported), count(*)
                FROM decision_counts
                """
            ).fetchone()
            overlap.append(
                {
                    "propensity_threshold": threshold,
                    "decisions_with_two_supported_candidates": int(row[0]),
                    "two_candidate_coverage": _number(row[0] / row[2]),
                    "chosen_supported_decisions": int(row[1]),
                    "chosen_support_coverage": _number(row[1] / row[2]),
                }
            )

        weighting = []
        for threshold in PROPENSITY_THRESHOLDS:
            for cap in WEIGHT_CAPS:
                row = connection.execute(
                    f"""
                    WITH eligible AS (
                        SELECT c.observed_delta_run_exp outcome,
                               least(1.0 / greatest(c.candidate_propensity, {float(threshold)}), {float(cap)}) AS weight
                        FROM read_parquet('{candidate_path}') c
                        WHERE c.is_chosen
                          AND c.pregame_type_pitches >= {MIN_WEAPON_PITCHES}
                          AND c.threat_pitches >= {MIN_THREAT_PITCHES}
                          AND c.candidate_propensity >= {float(threshold)}
                          AND c.observed_delta_run_exp IS NOT NULL
                    )
                    SELECT count(*), power(sum(weight), 2) / nullif(sum(weight * weight), 0),
                           sum(weight * outcome) / nullif(sum(weight), 0)
                    FROM eligible
                    """
                ).fetchone()
                weighting.append(
                    {
                        "propensity_threshold": threshold,
                        "weight_cap": cap,
                        "rows": int(row[0]),
                        "effective_sample_size": _number(row[1]),
                        "weighted_observed_run_value": _number(row[2]),
                    }
                )

        yamamoto = _rows(
            connection,
            f"""
            SELECT candidate_pitch_type, is_chosen, round(candidate_propensity, 4) candidate_propensity,
                   pregame_type_pitches, threat_pitches, threat_support_level,
                   round(weapon_stuff_delta, 2) weapon_stuff_delta,
                   round(weapon_location_delta, 2) weapon_location_delta,
                   round(threat_hunt_plus, 1) threat_hunt_plus,
                   round(threat_contact_plus, 1) threat_contact_plus,
                   round(threat_damage_plus, 1) threat_damage_plus,
                   round(predicted_batter_run_value, 5) predicted_batter_run_value,
                   pregame_type_pitches >= {MIN_WEAPON_PITCHES}
                     AND threat_pitches >= {MIN_THREAT_PITCHES}
                     AND candidate_propensity >= {DEFAULT_PROPENSITY} AS supported_candidate
            FROM read_parquet('{candidate_path}')
            WHERE game_pk = 823926 AND pitcher_id = 808967 AND batter_id = 543510
              AND at_bat_number = 44 AND pitch_number = 2
            ORDER BY predicted_batter_run_value, candidate_pitch_type
            """,
        )
        yamamoto_decision = _rows(
            connection,
            f"""
            SELECT * FROM read_parquet('{decision_path}')
            WHERE game_pk = 823926 AND pitcher_id = 808967 AND batter_id = 543510
              AND at_bat_number = 44 AND pitch_number = 2
            """,
        )

    decision_rows = int(decision_audit[0])
    interval_separated = int(decision_audit[5])
    model_improves_validation = (
        validation_metrics["model"]["rmse"] < validation_metrics["training_mean"]["rmse"]
        and validation_metrics["model"]["rmse"] < validation_metrics["threat_only"]["rmse"]
    )
    model_improves_test = test_metrics["model"]["rmse"] < test_metrics["threat_only"]["rmse"]
    integrity_ready = bool(
        int(candidate_audit[1]) == decision_rows
        and int(candidate_audit[2]) == decision_rows
        and int(candidate_audit[3]) == 0
        and int(candidate_audit[4]) == 0
        and int(decision_audit[1]) == 0
    )
    payload = {
        "contract_version": CONTRACT_VERSION,
        "status": "ready" if integrity_ready else "failed_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "development": "2025 first half",
            "validation": "2025 second half",
            "test": "2026, evaluation only and not used for model selection",
            "outcome": "Observed batter delta_run_exp per pitch; lower is better for the pitcher.",
            "slice5_retrained": False,
        },
        "support_contract": {
            "minimum_pitcher_type_history": MIN_WEAPON_PITCHES,
            "minimum_batter_context_history": MIN_THREAT_PITCHES,
            "default_exact_type_propensity": DEFAULT_PROPENSITY,
            "propensity_thresholds": list(PROPENSITY_THRESHOLDS),
            "weight_caps": list(WEIGHT_CAPS),
            "candidate_interpretation": "A supported candidate is comparable enough for sensitivity analysis, not a known counterfactual outcome.",
        },
        "value_model": {
            "model": "regularized_hist_gradient_boosting",
            "features": MODEL_FEATURES,
            "post_pitch_features_allowed": False,
            "validation_2025_second_half": validation_metrics,
            "test_2026": test_metrics,
            "model_improves_validation": model_improves_validation,
            "model_improves_test_vs_threat_only": model_improves_test,
            "prediction_interval": "Symmetric 90% residual interval calibrated on the 2025 second half; diagnostic, not a causal interval.",
        },
        "audit": {
            "candidate_rows": int(candidate_audit[0]),
            "decisions": int(candidate_audit[1]),
            "chosen_rows": int(candidate_audit[2]),
            "bad_propensity_rows": int(candidate_audit[3]),
            "null_prediction_rows": int(candidate_audit[4]),
            "decision_rows": decision_rows,
            "decision_duplicates": int(decision_audit[1]),
            "default_multi_candidate_decisions": int(decision_audit[2]),
            "default_multi_candidate_coverage": _number(int(decision_audit[2]) / decision_rows),
            "default_chosen_supported_decisions": int(decision_audit[3]),
            "default_chosen_support_coverage": _number(int(decision_audit[3]) / decision_rows),
            "default_alternative_decisions": int(decision_audit[4]),
            "interval_separated_decisions": interval_separated,
            "interval_separated_coverage": _number(interval_separated / decision_rows),
            "mean_predicted_gap_vs_best_alternative": _number(decision_audit[6]),
        },
        "overlap_sensitivity": overlap,
        "propensity_weight_sensitivity": weighting,
        "case_823926_yamamoto_mccann_candidates": yamamoto,
        "case_823926_yamamoto_mccann_decision": yamamoto_decision,
        "release_gate": {
            "integrity_ready": integrity_ready,
            "aggregate_supported_value_ready": bool(
                integrity_ready and model_improves_validation and model_improves_test
            ),
            "individual_best_pitch_ready": False,
            "causal_claim_supported": False,
            "reason": "Per-pitch outcome intervals and observational action assignment remain too uncertain for factual best-pitch labels.",
            "next_step": "Slice 6D may report aggregate entropy and exploitability sensitivity only within the supported overlap set.",
        },
        "artifacts": {
            "training_weapon_2025": str(training_weapon),
            "training_threat_through_2024": str(training_threat),
            "training_frame_2025": str(training_frame),
            "value_model": str(model_path),
            "candidate_values_2026": str(candidate_values),
            "candidate_values_2026_sha256": _sha256(candidate_values),
            "decision_values_2026": str(decision_values),
            "decision_values_2026_sha256": _sha256(decision_values),
        },
    }
    slice6c_contract_path(root).write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
            default=_json_default,
        ),
        encoding="utf-8",
    )
    return payload


def get_player_archetype_slice6c(data_dir: Path | None = None) -> dict[str, Any]:
    return json.loads(slice6c_contract_path(data_dir).read_text(encoding="utf-8"))


def render_slice6c_report(payload: dict[str, Any]) -> str:
    audit = payload["audit"]
    validation = payload["value_model"]["validation_2025_second_half"]
    test = payload["value_model"]["test_2026"]
    lines = [
        "# Player Archetypes Slice 6C — Supported Strategy Value",
        "",
        f"Contract: `{payload['contract_version']}`  ",
        f"Status: **{payload['status']}**  ",
        "",
        "## Support contract",
        "",
        f"- Pitcher exact-type history: at least {MIN_WEAPON_PITCHES} prior pitches.",
        f"- Batter hand/count-tier/family history: at least {MIN_THREAT_PITCHES} prior pitches.",
        f"- Default frozen Slice 5 exact-type propensity: at least {DEFAULT_PROPENSITY:.3f}.",
        "- Passing these gates means comparable enough for sensitivity analysis, not a known counterfactual result.",
        "",
        "## Value model",
        "",
        "The regularized gradient-boosting model uses only pre-pitch weapon state, batter threat, count, base/out and role features. Lower predicted batter run value is better for the pitcher.",
        "",
        "| Evaluation | Model RMSE | Threat-only RMSE | Mean RMSE | Model MAE |",
        "|---|---:|---:|---:|---:|",
        f"| 2025 second half | {validation['model']['rmse']:.6f} | {validation['threat_only']['rmse']:.6f} | {validation['training_mean']['rmse']:.6f} | {validation['model']['mae']:.6f} |",
        f"| 2026 | {test['model']['rmse']:.6f} | {test['threat_only']['rmse']:.6f} | {test['test_mean_descriptive_only']['rmse']:.6f} | {test['model']['mae']:.6f} |",
        f"- The diagnostic 90% single-pitch residual half-width is {validation['absolute_residual_q90']:.6f} runs.",
        "",
        "## 2026 overlap",
        "",
        f"- Candidate rows: {audit['candidate_rows']:,}; decisions: {audit['decisions']:,}; duplicate decisions: {audit['decision_duplicates']}.",
        f"- At the default gate, {audit['default_multi_candidate_decisions']:,} decisions ({audit['default_multi_candidate_coverage']:.2%}) have at least two supported choices.",
        f"- The observed choice itself is supported for {audit['default_chosen_supported_decisions']:,} decisions ({audit['default_chosen_support_coverage']:.2%}).",
        f"- Only {audit['interval_separated_decisions']:,} decisions ({audit['interval_separated_coverage']:.4%}) separate the chosen and best-supported-alternative 90% outcome intervals.",
        "",
        "## Release boundary",
        "",
        f"- Aggregate supported value ready: **{payload['release_gate']['aggregate_supported_value_ready']}**.",
        "- Individual best-pitch labels remain disabled. The action assignment is observational and single-pitch run value is noisy.",
        "- Slice 6D may use only the supported overlap set for entropy and exploitability sensitivity.",
        "",
    ]
    return "\n".join(lines)
