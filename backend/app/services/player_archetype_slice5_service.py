from __future__ import annotations

import gc
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
from scipy.optimize import minimize_scalar
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.core.config import settings
from app.services.player_archetype_slice4_service import slice4_warehouse_path


CONTRACT_VERSION = "player_archetype_slice5_belief_update_v1"
RANDOM_SEED = 20261015
TRAIN_YEARS = (2021, 2022, 2023, 2024)
CALIBRATION_YEAR = 2025
TEST_YEAR = 2026
TRAIN_SAMPLE_PCT = 25

FAMILY_CLASSES = ("Fastball", "Breaking", "Offspeed", "Other")
TYPE_CLASSES = ("FF", "SI", "FC", "SL", "ST", "CU", "KC", "SV", "CH", "FS", "FO", "SC", "OTHER")
TYPE_FAMILY = {
    "FF": "Fastball", "SI": "Fastball", "FC": "Fastball",
    "SL": "Breaking", "ST": "Breaking", "CU": "Breaking", "KC": "Breaking", "SV": "Breaking",
    "CH": "Offspeed", "FS": "Offspeed", "FO": "Offspeed", "SC": "Offspeed",
    "OTHER": "Other",
}
SOURCE_MAPS = {
    "pitcher": ("prior_pitcher_count_side_mix", "prior_pitcher_count_side_pitches"),
    "catcher": ("prior_catcher_context_mix", "prior_catcher_context_pitches"),
    "pair": ("prior_pair_context_mix", "prior_pair_context_pitches"),
    "h2h": ("prior_h2h_mix", "prior_h2h_pitches"),
}

BASE_CATEGORICAL = (
    "pitcher_role", "pitcher_throws", "batter_side", "count_state", "outs", "base_state",
    "inning_half", "platoon_state", "prior_pitch_family", "prior_pitch_result",
)
TAG_CATEGORICAL = (
    "pitcher_prior_tag_1", "pitcher_prior_tag_2", "pitcher_prior_tag_3", "pitcher_prior_tag_4",
    "batter_prior_tag_1", "batter_prior_tag_2", "batter_prior_tag_3", "batter_prior_tag_4",
)
BASE_NUMERIC = (
    "inning", "score_margin_clipped", "times_through_order", "log_appearance_pitch",
    "log_prior_pitcher", "log_prior_batter", "log_prior_catcher", "log_prior_pair", "log_prior_h2h",
)
TAG_NUMERIC = ("pitcher_prior_tag_reliability", "batter_prior_tag_reliability")


def slice5_contract_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice5.json"


def slice5_model_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice5_models.joblib"


def slice5_prediction_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice5_predictions_2026.parquet"


def slice5_report_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "PLAYER_ARCHETYPES_PITCH_STRATEGY.md"


def _number(value: Any, digits: int = 6) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return round(numeric, digits) if math.isfinite(numeric) else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sql_paths(paths: list[Path]) -> str:
    return "[" + ",".join("'" + path.resolve().as_posix().replace("'", "''") + "'" for path in paths) + "]"


def _paths(root: Path, years: tuple[int, ...]) -> list[Path]:
    paths = [slice4_warehouse_path(year, root) for year in years]
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing Slice 4 warehouses: {missing}")
    return paths


def _count_expressions() -> list[str]:
    expressions: list[str] = []
    known = TYPE_CLASSES[:-1]
    for source, (map_column, total_column) in SOURCE_MAPS.items():
        aliases: list[str] = []
        for pitch_type in known:
            alias = f"cnt_{source}_{pitch_type}"
            aliases.append(alias)
            expressions.append(
                f"CAST(coalesce(map_extract_value({map_column}, '{pitch_type}'), 0) AS DOUBLE) AS {alias}"
            )
        sum_sql = " + ".join(aliases)
        expressions.append(
            f"greatest(CAST({total_column} AS DOUBLE) - ({sum_sql}), 0) AS cnt_{source}_OTHER"
        )
    return expressions


def _target_code_sql() -> str:
    known = ", ".join(f"'{code}'" for code in TYPE_CLASSES[:-1])
    return f"CASE WHEN target_pitch_type IN ({known}) THEN target_pitch_type ELSE 'OTHER' END"


def _model_columns() -> list[str]:
    raw_numeric = [
        "inning", "pitcher_score_margin", "times_through_order", "appearance_pitch_number",
        "prior_pitcher_pitches", "prior_batter_pitches", "prior_catcher_pitches",
        "prior_pair_pitches", "prior_h2h_pitches",
        "pitcher_prior_tag_reliability", "batter_prior_tag_reliability",
    ]
    return list(BASE_CATEGORICAL) + list(TAG_CATEGORICAL) + raw_numeric


def _load_rows(
    root: Path,
    years: tuple[int, ...],
    *,
    sample_pct: int | None = None,
    include_counts: bool = False,
) -> pd.DataFrame:
    selected = [
        "decision_id", "year", "game_date", "game_pk", "at_bat_number", "pitch_number",
        "pitcher_id", "batter_id", "catcher_id", "target_pitch_family",
        f"{_target_code_sql()} AS target_pitch_code",
        "h2h_support_level", "context_backoff_level",
    ] + _model_columns()
    if include_counts:
        selected.extend(_count_expressions())
    sample = "" if sample_pct is None else f" AND hash(decision_id) % 100 < {int(sample_pct)}"
    query = f"""
        SELECT {', '.join(selected)}
        FROM read_parquet({_sql_paths(_paths(root, years))}, union_by_name=true)
        WHERE target_pitch_family IN ('Fastball', 'Breaking', 'Offspeed', 'Other') {sample}
        ORDER BY game_date, game_pk, at_bat_number, pitch_number
    """
    with duckdb.connect() as connection:
        frame = connection.execute(query).fetchdf()
    return _prepare_features(frame)


def _prepare_features(frame: pd.DataFrame) -> pd.DataFrame:
    for column in BASE_CATEGORICAL + TAG_CATEGORICAL:
        frame[column] = frame[column].fillna("__MISSING__").astype(str)
    frame["score_margin_clipped"] = pd.to_numeric(frame["pitcher_score_margin"], errors="coerce").clip(-10, 10)
    for raw, transformed in (
        ("appearance_pitch_number", "log_appearance_pitch"),
        ("prior_pitcher_pitches", "log_prior_pitcher"),
        ("prior_batter_pitches", "log_prior_batter"),
        ("prior_catcher_pitches", "log_prior_catcher"),
        ("prior_pair_pitches", "log_prior_pair"),
        ("prior_h2h_pitches", "log_prior_h2h"),
    ):
        numeric = pd.to_numeric(frame[raw], errors="coerce").fillna(0).clip(lower=0)
        frame[transformed] = np.log1p(numeric)
    return frame


def _new_model(include_tags: bool) -> Pipeline:
    categorical = list(BASE_CATEGORICAL) + (list(TAG_CATEGORICAL) if include_tags else [])
    numeric = list(BASE_NUMERIC) + (list(TAG_NUMERIC) if include_tags else [])
    preprocessor = ColumnTransformer(
        [
            (
                "categorical",
                OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=50),
                categorical,
            ),
            (
                "numeric",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            ),
        ]
    )
    return Pipeline(
        [
            ("features", preprocessor),
            (
                "model",
                LogisticRegression(
                    C=0.25,
                    solver="saga",
                    l1_ratio=0.0,
                    max_iter=120,
                    tol=1e-3,
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def _features(include_tags: bool) -> list[str]:
    return (
        list(BASE_CATEGORICAL)
        + (list(TAG_CATEGORICAL) if include_tags else [])
        + list(BASE_NUMERIC)
        + (list(TAG_NUMERIC) if include_tags else [])
    )


def _aligned_probabilities(model: Pipeline, frame: pd.DataFrame, include_tags: bool) -> np.ndarray:
    raw = np.asarray(model.predict_proba(frame[_features(include_tags)]), dtype=float)
    classes = list(model.named_steps["model"].classes_)
    aligned = np.full((len(frame), len(FAMILY_CLASSES)), 1e-9, dtype=float)
    for source_index, label in enumerate(classes):
        aligned[:, FAMILY_CLASSES.index(str(label))] = raw[:, source_index]
    return aligned / aligned.sum(axis=1, keepdims=True)


def _temperature_scale(probabilities: np.ndarray, temperature: float) -> np.ndarray:
    logits = np.log(np.clip(probabilities, 1e-9, 1.0)) / max(float(temperature), 1e-3)
    logits -= logits.max(axis=1, keepdims=True)
    scaled = np.exp(logits)
    return scaled / scaled.sum(axis=1, keepdims=True)


def _fit_temperature(truth: np.ndarray, probabilities: np.ndarray) -> float:
    target = np.asarray([FAMILY_CLASSES.index(str(value)) for value in truth], dtype=int)

    def objective(temperature: float) -> float:
        scaled = _temperature_scale(probabilities, temperature)
        return float(-np.log(np.clip(scaled[np.arange(len(target)), target], 1e-12, 1.0)).mean())

    result = minimize_scalar(objective, bounds=(0.5, 3.0), method="bounded", options={"xatol": 1e-3})
    return float(result.x)


def _family_indices(values: pd.Series | np.ndarray) -> np.ndarray:
    lookup = {label: index for index, label in enumerate(FAMILY_CLASSES)}
    return np.asarray([lookup[str(value)] for value in values], dtype=int)


def _type_indices(values: pd.Series | np.ndarray) -> np.ndarray:
    lookup = {label: index for index, label in enumerate(TYPE_CLASSES)}
    return np.asarray([lookup[str(value)] for value in values], dtype=int)


def _metrics(truth: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    if len(truth) == 0:
        return {"rows": 0, "status": "empty"}
    target = np.asarray(truth, dtype=int)
    clipped = np.clip(probabilities, 1e-12, 1.0)
    clipped /= clipped.sum(axis=1, keepdims=True)
    one_hot = np.eye(clipped.shape[1], dtype=float)[target]
    prediction = clipped.argmax(axis=1)
    top_two = np.argpartition(clipped, -min(2, clipped.shape[1]), axis=1)[:, -min(2, clipped.shape[1]):]
    confidence = clipped.max(axis=1)
    correct = prediction == target
    recalls = [float(correct[target == index].mean()) for index in range(clipped.shape[1]) if np.any(target == index)]
    ece = 0.0
    for lower in np.linspace(0.0, 0.9, 10):
        upper = lower + 0.1
        mask = (confidence >= lower) & ((confidence < upper) if upper < 1.0 else (confidence <= upper))
        if mask.any():
            ece += float(mask.mean()) * abs(float(confidence[mask].mean()) - float(correct[mask].mean()))
    return {
        "rows": int(len(target)),
        "status": "ready",
        "log_loss": _number(-np.log(clipped[np.arange(len(target)), target]).mean()),
        "brier": _number(np.square(clipped - one_hot).sum(axis=1).mean()),
        "top1_accuracy": _number(correct.mean()),
        "top2_accuracy": _number(np.any(top_two == target[:, None], axis=1).mean()),
        "macro_recall": _number(np.mean(recalls)),
        "ece_10": _number(ece),
        "mean_confidence": _number(confidence.mean()),
    }


def _static_family_prior(root: Path) -> tuple[dict[tuple[str, str, str], np.ndarray], dict[str, np.ndarray]]:
    query = f"""
        SELECT pitcher_role, count_state, batter_side, target_pitch_family, count(*) AS n
        FROM read_parquet({_sql_paths(_paths(root, TRAIN_YEARS))}, union_by_name=true)
        GROUP BY 1, 2, 3, 4
    """
    with duckdb.connect() as connection:
        counts = connection.execute(query).fetchdf()
    global_counts = np.asarray(
        [counts.loc[counts["target_pitch_family"].eq(label), "n"].sum() for label in FAMILY_CLASSES], dtype=float
    )
    global_probability = (global_counts + 1.0) / (global_counts.sum() + len(FAMILY_CLASSES))
    role_map: dict[str, np.ndarray] = {}
    for role, group in counts.groupby("pitcher_role", dropna=False):
        values = np.asarray(
            [group.loc[group["target_pitch_family"].eq(label), "n"].sum() for label in FAMILY_CLASSES], dtype=float
        )
        role_map[str(role)] = (values + 50.0 * global_probability) / (values.sum() + 50.0)
    fine_map: dict[tuple[str, str, str], np.ndarray] = {}
    for key, group in counts.groupby(["pitcher_role", "count_state", "batter_side"], dropna=False):
        role = str(key[0])
        values = np.asarray(
            [group.loc[group["target_pitch_family"].eq(label), "n"].sum() for label in FAMILY_CLASSES], dtype=float
        )
        role_probability = role_map.get(role, global_probability)
        fine_map[tuple(str(value) for value in key)] = (values + 50.0 * role_probability) / (values.sum() + 50.0)
    role_map["__GLOBAL__"] = global_probability
    return fine_map, role_map


def _static_probabilities(
    frame: pd.DataFrame,
    fine_map: dict[tuple[str, str, str], np.ndarray],
    role_map: dict[str, np.ndarray],
) -> np.ndarray:
    global_probability = role_map["__GLOBAL__"]
    rows = zip(frame["pitcher_role"], frame["count_state"], frame["batter_side"], strict=True)
    return np.asarray(
        [
            fine_map.get((str(role), str(count), str(side)), role_map.get(str(role), global_probability))
            for role, count, side in rows
        ],
        dtype=float,
    )


def _count_arrays(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {}
    for source in SOURCE_MAPS:
        arrays[source] = frame[[f"cnt_{source}_{pitch_type}" for pitch_type in TYPE_CLASSES]].to_numpy(
            dtype=np.float32, copy=True
        )
    return arrays


def _family_count_arrays(type_counts: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    family_indexes = {
        family: [index for index, pitch_type in enumerate(TYPE_CLASSES) if TYPE_FAMILY[pitch_type] == family]
        for family in FAMILY_CLASSES
    }
    return {
        source: np.column_stack([values[:, family_indexes[family]].sum(axis=1) for family in FAMILY_CLASSES])
        for source, values in type_counts.items()
    }


def _posterior_probabilities(
    base: np.ndarray,
    counts: dict[str, np.ndarray],
    weights: dict[str, float],
) -> np.ndarray:
    strength = float(weights["prior_strength"])
    alpha = strength * np.asarray(base, dtype=float)
    denominator = np.full(len(base), strength, dtype=float)
    for source in SOURCE_MAPS:
        weight = float(weights.get(source, 0.0))
        if weight <= 0:
            continue
        alpha = alpha + weight * counts[source]
        denominator += weight * counts[source].sum(axis=1)
    return alpha / np.clip(denominator[:, None], 1e-12, None)


def _target_log_loss(
    base: np.ndarray,
    counts: dict[str, np.ndarray],
    target: np.ndarray,
    weights: dict[str, float],
) -> float:
    probabilities = _posterior_probabilities(base, counts, weights)
    return float(-np.log(np.clip(probabilities[np.arange(len(target)), target], 1e-12, 1.0)).mean())


def _tune_updates(
    base: np.ndarray,
    counts: dict[str, np.ndarray],
    target: np.ndarray,
) -> tuple[dict[str, float], dict[str, float]]:
    best_player: tuple[float, dict[str, float]] | None = None
    for strength in (20.0, 50.0, 100.0, 200.0):
        for pitcher_weight in (0.25, 0.5, 1.0):
            weights = {
                "prior_strength": strength,
                "pitcher": pitcher_weight,
                "catcher": 0.0,
                "pair": 0.0,
                "h2h": 0.0,
            }
            loss = _target_log_loss(base, counts, target, weights)
            if best_player is None or loss < best_player[0]:
                best_player = (loss, weights)
    assert best_player is not None
    player_weights = best_player[1]

    best_full: tuple[float, dict[str, float]] | None = None
    for catcher_weight in (0.0, 0.05, 0.10):
        for pair_weight in (0.0, 0.05, 0.10):
            for h2h_weight in (0.0, 0.05, 0.10):
                weights = {
                    **player_weights,
                    "catcher": catcher_weight,
                    "pair": pair_weight,
                    "h2h": h2h_weight,
                }
                loss = _target_log_loss(base, counts, target, weights)
                if best_full is None or loss < best_full[0]:
                    best_full = (loss, weights)
    assert best_full is not None
    return player_weights, best_full[1]


def _exact_prior(root: Path) -> tuple[dict[tuple[str, str, str, str], np.ndarray], dict[tuple[str, str], np.ndarray]]:
    query = f"""
        SELECT pitcher_role, count_state, batter_side, target_pitch_family,
               {_target_code_sql()} AS target_pitch_code, count(*) AS n
        FROM read_parquet({_sql_paths(_paths(root, TRAIN_YEARS))}, union_by_name=true)
        GROUP BY 1, 2, 3, 4, 5
    """
    with duckdb.connect() as connection:
        counts = connection.execute(query).fetchdf()
    role_map: dict[tuple[str, str], np.ndarray] = {}
    for key, group in counts.groupby(["pitcher_role", "target_pitch_family"], dropna=False):
        values = np.asarray(
            [group.loc[group["target_pitch_code"].eq(label), "n"].sum() for label in TYPE_CLASSES], dtype=float
        )
        family = str(key[1])
        indexes = [index for index, pitch_type in enumerate(TYPE_CLASSES) if TYPE_FAMILY[pitch_type] == family]
        values[indexes] += 1.0
        values /= values.sum()
        role_map[(str(key[0]), family)] = values
    fine_map: dict[tuple[str, str, str, str], np.ndarray] = {}
    for key, group in counts.groupby(
        ["pitcher_role", "count_state", "batter_side", "target_pitch_family"], dropna=False
    ):
        values = np.asarray(
            [group.loc[group["target_pitch_code"].eq(label), "n"].sum() for label in TYPE_CLASSES], dtype=float
        )
        role_key = (str(key[0]), str(key[3]))
        fallback = role_map[role_key]
        values = values + 30.0 * fallback
        values /= values.sum()
        fine_map[tuple(str(value) for value in key)] = values
    return fine_map, role_map


def _exact_prior_probabilities(
    frame: pd.DataFrame,
    fine_map: dict[tuple[str, str, str, str], np.ndarray],
    role_map: dict[tuple[str, str], np.ndarray],
) -> np.ndarray:
    result = np.zeros((len(frame), len(TYPE_CLASSES)), dtype=np.float32)
    grouping = frame.groupby(["pitcher_role", "count_state", "batter_side"], sort=False, dropna=False).indices
    for raw_key, indexes in grouping.items():
        role, count, side = (str(value) for value in raw_key)
        for family in FAMILY_CLASSES:
            vector = fine_map.get((role, count, side, family), role_map.get((role, family)))
            if vector is None:
                family_indexes = [i for i, code in enumerate(TYPE_CLASSES) if TYPE_FAMILY[code] == family]
                vector = np.zeros(len(TYPE_CLASSES), dtype=float)
                vector[family_indexes] = 1.0 / len(family_indexes)
            result[np.asarray(indexes, dtype=int)] += vector.astype(np.float32)
    return result


def _exact_probabilities(
    family_probabilities: np.ndarray,
    exact_prior: np.ndarray,
    type_counts: dict[str, np.ndarray],
    weights: dict[str, float],
    type_strength: float,
) -> np.ndarray:
    result = np.zeros((len(family_probabilities), len(TYPE_CLASSES)), dtype=float)
    for family_index, family in enumerate(FAMILY_CLASSES):
        indexes = [index for index, code in enumerate(TYPE_CLASSES) if TYPE_FAMILY[code] == family]
        alpha = type_strength * exact_prior[:, indexes].astype(float)
        denominator = np.full(len(result), type_strength, dtype=float)
        for source in SOURCE_MAPS:
            weight = float(weights.get(source, 0.0))
            if weight <= 0:
                continue
            source_counts = type_counts[source][:, indexes]
            alpha += weight * source_counts
            denominator += weight * source_counts.sum(axis=1)
        conditional = alpha / np.clip(denominator[:, None], 1e-12, None)
        result[:, indexes] = family_probabilities[:, family_index, None] * conditional
    return result / result.sum(axis=1, keepdims=True)


def _top_tag_coefficients(model: Pipeline) -> dict[str, list[dict[str, Any]]]:
    names = np.asarray(model.named_steps["features"].get_feature_names_out(), dtype=object)
    tag_mask = np.asarray(["prior_tag_" in str(name) for name in names], dtype=bool)
    tag_names = names[tag_mask]
    coefficients = np.asarray(model.named_steps["model"].coef_, dtype=float)[:, tag_mask]
    classes = [str(value) for value in model.named_steps["model"].classes_]
    output: dict[str, list[dict[str, Any]]] = {}
    for class_index, label in enumerate(classes):
        order = np.argsort(np.abs(coefficients[class_index]))[::-1][:12]
        output[label] = [
            {"feature": str(tag_names[index]), "coefficient": _number(coefficients[class_index, index])}
            for index in order
        ]
    return output


def _subgroup_metrics(frame: pd.DataFrame, truth: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    pitcher_tag_missing = frame["pitcher_prior_tag_1"].eq("__MISSING__").to_numpy()
    batter_tag_missing = frame["batter_prior_tag_1"].eq("__MISSING__").to_numpy()
    pitcher_low = frame["prior_pitcher_pitches"].to_numpy(dtype=float) < 20
    catcher_low = frame["prior_catcher_pitches"].to_numpy(dtype=float) < 20
    batter_low = frame["prior_batter_pitches"].to_numpy(dtype=float) < 20
    masks = {
        "all": np.ones(len(frame), dtype=bool),
        "pitcher_tag_missing": pitcher_tag_missing,
        "batter_tag_missing": batter_tag_missing,
        "pitcher_hard_cold": pitcher_tag_missing & pitcher_low,
        "batter_hard_cold": batter_tag_missing & batter_low,
        "pitcher_catcher_low": pitcher_low & catcher_low,
        "all_three_hard_cold": pitcher_tag_missing & pitcher_low & catcher_low & batter_tag_missing & batter_low,
    }
    for level in ("supported", "limited", "unavailable"):
        masks[f"h2h_{level}"] = frame["h2h_support_level"].eq(level).to_numpy()
    result: dict[str, Any] = {}
    for name, mask in masks.items():
        if int(mask.sum()) < 100:
            result[name] = {"rows": int(mask.sum()), "status": "insufficient_for_metric"}
        else:
            result[name] = _metrics(truth[mask], probabilities[mask])
    return result


def _write_predictions(
    root: Path,
    frame: pd.DataFrame,
    family_probabilities: np.ndarray,
    exact_probabilities: np.ndarray,
    selected_model: str,
) -> Path:
    output = frame[
        [
            "decision_id", "year", "game_date", "game_pk", "at_bat_number", "pitch_number",
            "pitcher_id", "batter_id", "catcher_id", "target_pitch_family", "target_pitch_code",
            "context_backoff_level", "h2h_support_level", "prior_pitcher_pitches",
            "prior_batter_pitches", "prior_catcher_pitches",
        ]
    ].copy()
    for index, label in enumerate(FAMILY_CLASSES):
        output[f"prob_family_{label.lower()}"] = family_probabilities[:, index]
    for index, label in enumerate(TYPE_CLASSES):
        output[f"prob_type_{label.lower()}"] = exact_probabilities[:, index]
    output["predicted_family"] = np.asarray(FAMILY_CLASSES, dtype=object)[family_probabilities.argmax(axis=1)]
    output["predicted_pitch_type"] = np.asarray(TYPE_CLASSES, dtype=object)[exact_probabilities.argmax(axis=1)]
    output["family_confidence"] = family_probabilities.max(axis=1)
    output["family_entropy"] = -np.sum(
        family_probabilities * np.log(np.clip(family_probabilities, 1e-12, 1.0)), axis=1
    )
    output["selected_model"] = selected_model
    path = slice5_prediction_path(root)
    temporary = path.with_suffix(".tmp.parquet")
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect() as connection:
        connection.register("predictions", output)
        connection.execute(f"COPY predictions TO '{temporary.resolve().as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    temporary.replace(path)
    return path


def _save_models(root: Path, payload: dict[str, Any], context_model: Pipeline, tag_model: Pipeline) -> Path:
    path = slice5_model_path(root)
    temporary = path.with_suffix(".tmp.joblib")
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "contract_version": CONTRACT_VERSION,
            "context_model": context_model,
            "tag_model": tag_model,
            "family_classes": FAMILY_CLASSES,
            "type_classes": TYPE_CLASSES,
            "temperatures": payload["calibration"]["temperatures"],
            "selected_base": payload["selection"]["selected_base"],
            "selected_family_model": payload["selection"]["selected_family_model"],
            "player_weights": payload["selection"]["player_weights"],
            "hierarchical_weights": payload["selection"]["hierarchical_weights"],
            "exact_type_strength": payload["selection"]["exact_type_strength"],
        },
        temporary,
        compress=3,
    )
    temporary.replace(path)
    return path


def _model_diagnostics(model: Pipeline) -> dict[str, Any]:
    estimator = model.named_steps["model"]
    transformed = model.named_steps["features"].get_feature_names_out()
    return {
        "features_after_encoding": int(len(transformed)),
        "iterations": [int(value) for value in np.asarray(estimator.n_iter_).ravel()],
        "converged": bool(np.asarray(estimator.n_iter_).max() < estimator.max_iter),
    }


def build_player_archetype_slice5(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    train = _load_rows(root, TRAIN_YEARS, sample_pct=TRAIN_SAMPLE_PCT, include_counts=False)
    context_model = _new_model(include_tags=False)
    tag_model = _new_model(include_tags=True)
    context_model.fit(train[_features(False)], train["target_pitch_family"])
    tag_model.fit(train[_features(True)], train["target_pitch_family"])
    train_rows = int(len(train))
    train_distribution = {
        label: int(train["target_pitch_family"].eq(label).sum()) for label in FAMILY_CLASSES
    }
    del train
    gc.collect()

    static_fine, static_role = _static_family_prior(root)
    exact_fine, exact_role = _exact_prior(root)
    development = _load_rows(root, (CALIBRATION_YEAR,), include_counts=True)
    cutoff = pd.to_datetime(development["game_date"]).quantile(0.5)
    calibration_mask = pd.to_datetime(development["game_date"]).le(cutoff).to_numpy()
    validation_mask = ~calibration_mask
    truth_all = _family_indices(development["target_pitch_family"])

    context_raw = _aligned_probabilities(context_model, development, include_tags=False)
    tag_raw = _aligned_probabilities(tag_model, development, include_tags=True)
    context_temperature = _fit_temperature(
        development.loc[calibration_mask, "target_pitch_family"].to_numpy(), context_raw[calibration_mask]
    )
    tag_temperature = _fit_temperature(
        development.loc[calibration_mask, "target_pitch_family"].to_numpy(), tag_raw[calibration_mask]
    )
    context_probabilities = _temperature_scale(context_raw, context_temperature)
    tag_probabilities = _temperature_scale(tag_raw, tag_temperature)
    static_probabilities = _static_probabilities(development, static_fine, static_role)

    validation_truth = truth_all[validation_mask]
    validation_metrics: dict[str, Any] = {
        "static_context": _metrics(validation_truth, static_probabilities[validation_mask]),
        "regularized_context": _metrics(validation_truth, context_probabilities[validation_mask]),
        "regularized_tags": _metrics(validation_truth, tag_probabilities[validation_mask]),
    }
    selected_base = (
        "regularized_tags"
        if validation_metrics["regularized_tags"]["log_loss"] <= validation_metrics["regularized_context"]["log_loss"]
        else "regularized_context"
    )
    selected_base_all = tag_probabilities if selected_base == "regularized_tags" else context_probabilities

    type_counts = _count_arrays(development)
    family_counts = _family_count_arrays(type_counts)
    tuning_base = selected_base_all[validation_mask]
    tuning_counts = {source: values[validation_mask] for source, values in family_counts.items()}
    player_weights, hierarchical_weights = _tune_updates(tuning_base, tuning_counts, validation_truth)
    player_probabilities = _posterior_probabilities(selected_base_all, family_counts, player_weights)
    hierarchical_probabilities = _posterior_probabilities(selected_base_all, family_counts, hierarchical_weights)
    validation_metrics["player_only_update"] = _metrics(validation_truth, player_probabilities[validation_mask])
    validation_metrics["hierarchical_update"] = _metrics(
        validation_truth, hierarchical_probabilities[validation_mask]
    )
    candidate_probabilities = {
        selected_base: selected_base_all,
        "player_only_update": player_probabilities,
        "hierarchical_update": hierarchical_probabilities,
    }
    selected_family_model = min(
        candidate_probabilities,
        key=lambda name: float(validation_metrics[name]["log_loss"]),
    )
    selected_development = candidate_probabilities[selected_family_model]
    selected_weights = (
        hierarchical_weights
        if selected_family_model == "hierarchical_update"
        else player_weights
        if selected_family_model == "player_only_update"
        else {"prior_strength": 100.0, "pitcher": 0.0, "catcher": 0.0, "pair": 0.0, "h2h": 0.0}
    )

    exact_prior = _exact_prior_probabilities(development, exact_fine, exact_role)
    validation_type_truth = _type_indices(development.loc[validation_mask, "target_pitch_code"])
    exact_candidates: dict[float, float] = {}
    for strength in (10.0, 30.0, 60.0, 100.0):
        exact = _exact_probabilities(
            selected_development[validation_mask],
            exact_prior[validation_mask],
            {source: values[validation_mask] for source, values in type_counts.items()},
            selected_weights,
            strength,
        )
        exact_candidates[strength] = float(_metrics(validation_type_truth, exact)["log_loss"])
    exact_type_strength = min(exact_candidates, key=exact_candidates.get)
    validation_exact = _exact_probabilities(
        selected_development[validation_mask],
        exact_prior[validation_mask],
        {source: values[validation_mask] for source, values in type_counts.items()},
        selected_weights,
        exact_type_strength,
    )
    validation_exact_metrics = _metrics(validation_type_truth, validation_exact)
    development_rows = int(len(development))
    calibration_rows = int(calibration_mask.sum())
    validation_rows = int(validation_mask.sum())
    del development, context_raw, tag_raw, context_probabilities, tag_probabilities
    del static_probabilities, player_probabilities, hierarchical_probabilities, selected_development
    del exact_prior, validation_exact, type_counts, family_counts
    gc.collect()

    test = _load_rows(root, (TEST_YEAR,), include_counts=True)
    test_truth = _family_indices(test["target_pitch_family"])
    test_static = _static_probabilities(test, static_fine, static_role)
    test_context = _temperature_scale(
        _aligned_probabilities(context_model, test, include_tags=False), context_temperature
    )
    test_tags = _temperature_scale(_aligned_probabilities(tag_model, test, include_tags=True), tag_temperature)
    test_base = test_tags if selected_base == "regularized_tags" else test_context
    test_type_counts = _count_arrays(test)
    test_family_counts = _family_count_arrays(test_type_counts)
    test_player = _posterior_probabilities(test_base, test_family_counts, player_weights)
    test_hierarchical = _posterior_probabilities(test_base, test_family_counts, hierarchical_weights)
    test_candidates = {
        "static_context": test_static,
        "regularized_context": test_context,
        "regularized_tags": test_tags,
        "player_only_update": test_player,
        "hierarchical_update": test_hierarchical,
    }
    test_metrics = {name: _metrics(test_truth, probabilities) for name, probabilities in test_candidates.items()}
    selected_test = test_candidates[selected_family_model]

    test_exact_prior = _exact_prior_probabilities(test, exact_fine, exact_role)
    test_exact = _exact_probabilities(
        selected_test,
        test_exact_prior,
        test_type_counts,
        selected_weights,
        exact_type_strength,
    )
    test_exact_metrics = _metrics(_type_indices(test["target_pitch_code"]), test_exact)
    subgroup_metrics = _subgroup_metrics(test, test_truth, selected_test)
    prediction_path = _write_predictions(root, test, selected_test, test_exact, selected_family_model)

    base_loss = float(test_metrics[selected_base]["log_loss"])
    hierarchical_loss = float(test_metrics["hierarchical_update"]["log_loss"])
    validation_base_loss = float(validation_metrics[selected_base]["log_loss"])
    validation_hierarchical_loss = float(validation_metrics["hierarchical_update"]["log_loss"])
    release_supported = bool(
        validation_hierarchical_loss < validation_base_loss
        and hierarchical_loss < base_loss
        and float(test_metrics["hierarchical_update"]["brier"]) <= float(test_metrics[selected_base]["brier"])
        and float(test_metrics["hierarchical_update"]["ece_10"]) <= float(test_metrics[selected_base]["ece_10"]) + 0.002
    )

    payload: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "scope": {
            "target": "next pitch family with secondary conditional exact pitch type",
            "train_years": list(TRAIN_YEARS),
            "calibration_year": CALIBRATION_YEAR,
            "test_year": TEST_YEAR,
            "test_used_for_selection": False,
            "train_sample_pct": TRAIN_SAMPLE_PCT,
        },
        "rows": {
            "train_sample": train_rows,
            "train_sample_family_distribution": train_distribution,
            "development_2025": development_rows,
            "calibration_2025_first_half": calibration_rows,
            "validation_2025_second_half": validation_rows,
            "test_2026": int(len(test)),
        },
        "feature_contract": {
            "context_categorical": list(BASE_CATEGORICAL),
            "context_numeric": list(BASE_NUMERIC),
            "prior_tag_categorical": list(TAG_CATEGORICAL),
            "prior_tag_numeric": list(TAG_NUMERIC),
            "online_updates": list(SOURCE_MAPS),
            "post_decision_features_allowed": False,
            "player_ids_in_regularized_model": False,
            "missing_tag_policy": "Explicit missing category; no average tag is imputed. Predictions back off to context and supported strictly-prior counts.",
        },
        "calibration": {
            "cutoff_date": str(pd.Timestamp(cutoff).date()),
            "temperatures": {
                "regularized_context": _number(context_temperature),
                "regularized_tags": _number(tag_temperature),
            },
        },
        "selection": {
            "selected_base": selected_base,
            "selected_family_model": selected_family_model,
            "player_weights": {key: _number(value) for key, value in player_weights.items()},
            "hierarchical_weights": {key: _number(value) for key, value in hierarchical_weights.items()},
            "exact_type_strength": _number(exact_type_strength),
            "exact_strength_candidates": {str(key): _number(value) for key, value in exact_candidates.items()},
            "hierarchical_release_supported": release_supported,
        },
        "model_diagnostics": {
            "regularized_context": _model_diagnostics(context_model),
            "regularized_tags": _model_diagnostics(tag_model),
            "top_tag_coefficients": _top_tag_coefficients(tag_model),
        },
        "validation_2025_second_half": {
            "family_models": validation_metrics,
            "exact_pitch_selected_model": validation_exact_metrics,
        },
        "test_2026": {
            "family_models": test_metrics,
            "exact_pitch_selected_model": test_exact_metrics,
            "selected_model_subgroups": subgroup_metrics,
        },
        "interpretation": {
            "catcher_effect": "Associative residual only; not evidence that the catcher personally called a pitch.",
            "probability_meaning": "Forecast probability conditional on public pre-pitch information and observed prior choices, not causal optimality.",
            "cold_start": "Low-support rows remain scored with wider, population-shrunk beliefs; they are not dropped or assigned an average tag.",
            "exact_pitch": "Two-stage family probability multiplied by a within-family empirical-Bayes pitch-type distribution.",
        },
    }
    model_path = _save_models(root, payload, context_model, tag_model)
    payload["artifacts"] = {
        "models": str(model_path),
        "models_sha256": _sha256(model_path),
        "predictions_2026": str(prediction_path),
        "predictions_sha256": _sha256(prediction_path),
    }
    contract_path = slice5_contract_path(root)
    contract_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return payload


def get_player_archetype_slice5(data_dir: Path | None = None) -> dict[str, Any]:
    return json.loads(slice5_contract_path(data_dir).read_text(encoding="utf-8"))


def _metric_row(name: str, metrics: dict[str, Any]) -> str:
    return (
        f"| {name} | {metrics['rows']:,} | {metrics['log_loss']:.6f} | {metrics['brier']:.6f} | "
        f"{metrics['top1_accuracy']:.3%} | {metrics['top2_accuracy']:.3%} | "
        f"{metrics['macro_recall']:.3%} | {metrics['ece_10']:.3%} |"
    )


def render_slice5_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Player Archetypes Slice 5 — Bayesian belief updating",
        "",
        f"Contract: `{payload['contract_version']}`  ",
        f"Status: **{payload['status']}**  ",
        "Split: **2021–2024 train → 2025 first-half calibration / second-half validation → untouched 2026 test**",
        "",
        "## Model contract",
        "",
        "- Regularized context and prior-tag multinomial models never receive player IDs or post-decision observations.",
        "- Empirical-Bayes updates use only strictly earlier pitcher, catcher, pitcher-catcher and pitcher-batter counts.",
        "- Missing tags remain an explicit missing state and back off to context; they are never assigned an Average tag.",
        "- Exact pitch is a second stage: selected family probability × within-family pitch-type posterior.",
        "",
        "## 2025 second-half validation",
        "",
        "| Model | Rows | Log loss | Brier | Top-1 | Top-2 | Macro recall | ECE |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, metrics in payload["validation_2025_second_half"]["family_models"].items():
        lines.append(_metric_row(name, metrics))
    lines.extend(
        [
            "",
            "## 2026 untouched test",
            "",
            "| Model | Rows | Log loss | Brier | Top-1 | Top-2 | Macro recall | ECE |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, metrics in payload["test_2026"]["family_models"].items():
        lines.append(_metric_row(name, metrics))
    selected = payload["selection"]
    exact = payload["test_2026"]["exact_pitch_selected_model"]
    lines.extend(
        [
            "",
            "## Selection",
            "",
            f"- Selected regularized base: `{selected['selected_base']}`.",
            f"- Selected family model on 2025 validation: `{selected['selected_family_model']}`.",
            f"- Hierarchical release gate: **{'passed' if selected['hierarchical_release_supported'] else 'not passed'}**.",
            f"- 2026 exact-pitch log loss / Top-1 / Top-2: **{exact['log_loss']:.6f} / {exact['top1_accuracy']:.3%} / {exact['top2_accuracy']:.3%}**.",
            "",
            "## Cold-start interpretation",
            "",
            "Rows below 100 are reported as insufficient rather than converted into unstable performance claims.",
            "",
            "| Subgroup | Rows | Status | Log loss |",
            "|---|---:|---|---:|",
        ]
    )
    for name, metrics in payload["test_2026"]["selected_model_subgroups"].items():
        loss = "-" if metrics.get("log_loss") is None else f"{metrics['log_loss']:.6f}"
        lines.append(f"| {name} | {metrics['rows']:,} | {metrics['status']} | {loss} |")
    lines.extend(
        [
            "",
            "## Limits",
            "",
            "- These probabilities explain observed selection patterns; they do not say which pitch was causally optimal.",
            "- Catcher and pairing terms remain associations after partial pooling, not proof of who called the pitch.",
            "- 2026 is a fixed test. Do not retune the model after reading its metrics without declaring a new version and a new future test season.",
            "",
        ]
    )
    return "\n".join(lines)
