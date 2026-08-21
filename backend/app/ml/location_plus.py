"""Independent Location+ training pipeline.

The model deliberately excludes pitcher identity and pitch-shape measurements.
It estimates outcome probabilities from location, pitch type, count, handedness,
and base/out context, then converts those probabilities to expected run value.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier


OUTCOMES = [
    "ball",
    "called_strike",
    "swinging_strike",
    "foul",
    "hit_by_pitch",
    "weak",
    "topped",
    "under",
    "flare_burner",
    "solid",
    "barrel",
    "in_play_other",
]

NUMERIC_FEATURES = [
    "plate_x",
    "plate_z_norm",
    "plate_x_batter",
    "distance_from_zone_center",
    "balls",
    "strikes",
    "outs_when_up",
    "on_1b",
    "on_2b",
    "on_3b",
]

CATEGORICAL_FEATURES = ["pitch_type", "stand", "p_throws"]
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

SOURCE_COLUMNS = [
    "game_date",
    "game_type",
    "pitcher",
    "pitch_type",
    "pitch_name",
    "plate_x",
    "plate_z",
    "sz_top",
    "sz_bot",
    "balls",
    "strikes",
    "outs_when_up",
    "on_1b",
    "on_2b",
    "on_3b",
    "stand",
    "p_throws",
    "description",
    "events",
    "launch_speed_angle",
    "delta_run_exp",
]


@dataclass(frozen=True)
class SplitMetrics:
    rows: int
    log_loss: float
    brier_score: float
    calibration_error: float
    run_value_mae: float
    run_value_correlation: float | None


def database_path(data_dir: Path, year: int) -> Path:
    return data_dir / f"MLB{year}" / f"mlb_{year}.duckdb"


def load_seasons(data_dir: Path, years: Iterable[int]) -> pd.DataFrame:
    """Load only columns needed by the Location+ pipeline."""

    frames: list[pd.DataFrame] = []
    columns = ", ".join(SOURCE_COLUMNS)
    for year in years:
        path = database_path(data_dir, int(year))
        if not path.exists():
            raise FileNotFoundError(f"Missing season database: {path}")
        with duckdb.connect(str(path), read_only=True) as conn:
            frame = conn.execute(
                f"""
                SELECT {columns}
                FROM pitches
                WHERE game_type = 'R'
                  AND plate_x IS NOT NULL
                  AND plate_z IS NOT NULL
                  AND sz_top > sz_bot
                """
            ).fetchdf()
        frame["season"] = int(year)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def classify_outcome(frame: pd.DataFrame) -> pd.Series:
    """Map Statcast descriptions/contact classes to mutually exclusive labels."""

    description = frame["description"].fillna("").astype(str).str.lower()
    events = frame["events"].fillna("").astype(str).str.lower()
    contact = pd.to_numeric(frame["launch_speed_angle"], errors="coerce")
    result = pd.Series("", index=frame.index, dtype="object")

    result.loc[description.isin({"ball", "blocked_ball", "pitchout"})] = "ball"
    result.loc[description.eq("called_strike")] = "called_strike"
    result.loc[description.isin({"swinging_strike", "swinging_strike_blocked", "missed_bunt"})] = "swinging_strike"
    result.loc[description.isin({"foul", "foul_tip", "foul_bunt"})] = "foul"
    result.loc[description.eq("hit_by_pitch") | events.eq("hit_by_pitch")] = "hit_by_pitch"

    in_play = description.isin({"hit_into_play", "hit_into_play_no_out", "hit_into_play_score"})
    contact_labels = {1: "weak", 2: "topped", 3: "under", 4: "flare_burner", 5: "solid", 6: "barrel"}
    for value, label in contact_labels.items():
        result.loc[in_play & contact.eq(value)] = label
    result.loc[in_play & result.eq("")] = "in_play_other"
    return result.replace("", np.nan)


def build_training_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Create pre-pitch/location features without pitcher or stuff variables."""

    frame = raw.copy()
    frame["outcome"] = classify_outcome(frame)
    outcome_codes = {label: index for index, label in enumerate(OUTCOMES)}
    frame["outcome_code"] = frame["outcome"].map(outcome_codes)
    frame["plate_x"] = pd.to_numeric(frame["plate_x"], errors="coerce")
    plate_z = pd.to_numeric(frame["plate_z"], errors="coerce")
    sz_top = pd.to_numeric(frame["sz_top"], errors="coerce")
    sz_bot = pd.to_numeric(frame["sz_bot"], errors="coerce")
    zone_height = (sz_top - sz_bot).where((sz_top - sz_bot) > 0)
    frame["plate_z_norm"] = (plate_z - sz_bot) / zone_height
    frame["stand"] = frame["stand"].fillna("U").astype(str).str.upper()
    frame["p_throws"] = frame["p_throws"].fillna("U").astype(str).str.upper()
    frame["plate_x_batter"] = frame["plate_x"] * np.where(frame["stand"].eq("L"), -1.0, 1.0)
    frame["distance_from_zone_center"] = np.sqrt((frame["plate_x"] / 0.83) ** 2 + ((frame["plate_z_norm"] - 0.5) / 0.5) ** 2)
    frame["pitch_type"] = (
        frame["pitch_name"].fillna(frame["pitch_type"]).fillna("Unknown").astype(str)
    )
    for column in ["balls", "strikes", "outs_when_up"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ["on_1b", "on_2b", "on_3b"]:
        frame[column] = frame[column].notna().astype("int8")
    frame["delta_run_exp"] = pd.to_numeric(frame["delta_run_exp"], errors="coerce")
    required = ["outcome", "outcome_code", "plate_x", "plate_z_norm", "pitcher", "season"]
    return frame.dropna(subset=required).reset_index(drop=True)


def make_pipeline(random_state: int = 42, n_estimators: int = 220) -> Pipeline:
    numeric = Pipeline([("imputer", SimpleImputer(strategy="median"))])
    categorical = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
        ]
    )
    preprocessor = ColumnTransformer(
        [("numeric", numeric, NUMERIC_FEATURES), ("categorical", categorical, CATEGORICAL_FEATURES)]
    )
    classifier = XGBClassifier(
        objective="multi:softprob",
        eval_metric="mlogloss",
        tree_method="hist",
        n_estimators=n_estimators,
        max_depth=6,
        learning_rate=0.06,
        min_child_weight=20,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=2.0,
        n_jobs=-1,
        random_state=random_state,
    )
    return Pipeline([("features", preprocessor), ("model", classifier)])


def outcome_run_values(training_frame: pd.DataFrame) -> dict[str, float]:
    values = training_frame.groupby("outcome")["delta_run_exp"].mean().reindex(OUTCOMES)
    fallback = float(training_frame["delta_run_exp"].mean())
    return {label: float(values.get(label)) if pd.notna(values.get(label)) else fallback for label in OUTCOMES}


def apply_temperature(probabilities: np.ndarray, temperature: float) -> np.ndarray:
    clipped = np.clip(probabilities, 1e-12, 1.0)
    scaled = np.exp(np.log(clipped) / temperature)
    return scaled / scaled.sum(axis=1, keepdims=True)


def choose_temperature(y_true: np.ndarray, probabilities: np.ndarray, labels: np.ndarray) -> float:
    candidates = np.linspace(0.70, 1.50, 33)
    losses = [log_loss(y_true, apply_temperature(probabilities, value), labels=labels) for value in candidates]
    return float(candidates[int(np.argmin(losses))])


def expected_run_value(probabilities: np.ndarray, classes: np.ndarray, run_values: dict[str, float]) -> np.ndarray:
    vector = np.array([run_values[OUTCOMES[int(label)]] for label in classes], dtype="float64")
    return probabilities @ vector


def calibration_error(y_true: np.ndarray, probabilities: np.ndarray, classes: np.ndarray, bins: int = 15) -> float:
    predicted = classes[np.argmax(probabilities, axis=1)]
    confidence = probabilities.max(axis=1)
    correct = predicted == y_true
    edges = np.linspace(0.0, 1.0, bins + 1)
    error = 0.0
    for left, right in zip(edges[:-1], edges[1:]):
        mask = (confidence >= left) & (confidence < right if right < 1 else confidence <= right)
        if mask.any():
            error += float(mask.mean()) * abs(float(correct[mask].mean()) - float(confidence[mask].mean()))
    return error


def evaluate(
    frame: pd.DataFrame,
    probabilities: np.ndarray,
    classes: np.ndarray,
    run_values: dict[str, float],
) -> SplitMetrics:
    y_true = frame["outcome_code"].to_numpy(dtype="int64")
    class_index = {int(label): index for index, label in enumerate(classes)}
    one_hot = np.zeros_like(probabilities)
    for row, label in enumerate(y_true):
        one_hot[row, class_index[int(label)]] = 1.0
    xrv = expected_run_value(probabilities, classes, run_values)
    actual = frame["delta_run_exp"].to_numpy(dtype="float64")
    valid = np.isfinite(actual)
    correlation = None
    if valid.sum() > 1 and np.std(actual[valid]) > 0 and np.std(xrv[valid]) > 0:
        correlation = float(np.corrcoef(actual[valid], xrv[valid])[0, 1])
    return SplitMetrics(
        rows=int(len(frame)),
        log_loss=float(log_loss(y_true, probabilities, labels=classes)),
        brier_score=float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1))),
        calibration_error=calibration_error(y_true, probabilities, classes),
        run_value_mae=float(np.mean(np.abs(actual[valid] - xrv[valid]))) if valid.any() else math.nan,
        run_value_correlation=correlation,
    )


def location_scale(frame: pd.DataFrame, xrv: np.ndarray, minimum_pitches: int = 100) -> dict[str, float | int]:
    scores = frame[["season", "pitcher"]].copy()
    scores["xrv"] = xrv
    grouped = scores.groupby(["season", "pitcher"], as_index=False).agg(pitches=("xrv", "size"), xrv=("xrv", "mean"))
    qualified = grouped.loc[grouped["pitches"] >= minimum_pitches, "xrv"] * 100.0
    if len(qualified) < 2:
        raise ValueError("Not enough qualified pitcher-seasons to define the Location+ scale")
    return {
        "mean_xrv_per_100": float(qualified.mean()),
        "sd_xrv_per_100": float(qualified.std(ddof=0)),
        "points_per_sd": 10.0,
        "minimum_pitches": int(minimum_pitches),
        "qualified_pitcher_seasons": int(len(qualified)),
    }


def train_location_plus(
    data_dir: Path,
    artifact_dir: Path,
    n_estimators: int = 220,
    sample_fraction: float = 1.0,
) -> dict[str, object]:
    """Train, validate, test, refit, and persist the production Location+ model."""

    started = time.perf_counter()
    if not 0 < sample_fraction <= 1:
        raise ValueError("sample_fraction must be in (0, 1]")
    prepared_seasons: list[pd.DataFrame] = []
    retained_columns = [*MODEL_FEATURES, "outcome", "outcome_code", "delta_run_exp", "pitcher", "season"]
    for year in range(2021, 2027):
        season_frame = build_training_frame(load_seasons(data_dir, [year]))[retained_columns]
        if sample_fraction < 1:
            season_frame = season_frame.sample(frac=sample_fraction, random_state=42)
        prepared_seasons.append(season_frame)
    frame = pd.concat(prepared_seasons, ignore_index=True)

    development_train = frame[frame["season"].between(2021, 2024)].copy()
    validation = frame[frame["season"].eq(2025)].copy()
    test = frame[frame["season"].eq(2026)].copy()
    run_values = outcome_run_values(development_train)

    development_model = make_pipeline(n_estimators=n_estimators)
    development_model.fit(development_train[MODEL_FEATURES], development_train["outcome_code"])
    classes = development_model.named_steps["model"].classes_
    validation_raw = development_model.predict_proba(validation[MODEL_FEATURES])
    temperature = choose_temperature(validation["outcome_code"].to_numpy(dtype="int64"), validation_raw, classes)
    validation_probabilities = apply_temperature(validation_raw, temperature)
    test_probabilities = apply_temperature(development_model.predict_proba(test[MODEL_FEATURES]), temperature)
    validation_metrics = evaluate(validation, validation_probabilities, classes, run_values)
    test_metrics = evaluate(test, test_probabilities, classes, run_values)

    production_train = frame[frame["season"].between(2021, 2025)].copy()
    production_run_values = outcome_run_values(production_train)
    production_model = make_pipeline(n_estimators=n_estimators)
    production_model.fit(production_train[MODEL_FEATURES], production_train["outcome_code"])
    production_classes = production_model.named_steps["model"].classes_
    production_probabilities = apply_temperature(
        production_model.predict_proba(production_train[MODEL_FEATURES]), temperature
    )
    production_xrv = expected_run_value(production_probabilities, production_classes, production_run_values)
    scale = location_scale(
        production_train,
        production_xrv,
        minimum_pitches=max(5, round(100 * sample_fraction)),
    )
    heatmap_scale = {
        "mean_xrv_per_100": float(np.mean(production_xrv) * 100.0),
        "sd_xrv_per_100": float(np.std(production_xrv) * 100.0),
        "points_per_sd": 10.0,
    }

    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "location_plus_pipeline.joblib"
    metadata_path = artifact_dir / "location_plus_metadata.json"
    joblib.dump(production_model, model_path, compress=3)
    metadata: dict[str, object] = {
        "model_version": "location_plus_independent_v1",
        "definition": "Location, pitch type, count, handedness, and base/out context; no pitcher identity or stuff inputs.",
        "development_train_years": [2021, 2022, 2023, 2024],
        "validation_year": 2025,
        "test_year": 2026,
        "production_train_years": [2021, 2022, 2023, 2024, 2025],
        "features": MODEL_FEATURES,
        "outcomes": [OUTCOMES[int(value)] for value in production_classes],
        "temperature": temperature,
        "run_values": production_run_values,
        "location_plus_scale": scale,
        "location_heatmap_scale": heatmap_scale,
        "validation_metrics": asdict(validation_metrics),
        "test_metrics": asdict(test_metrics),
        "rows": {
            "development_train": int(len(development_train)),
            "validation": int(len(validation)),
            "test": int(len(test)),
            "production_train": int(len(production_train)),
        },
        "sample_fraction": sample_fraction,
        "n_estimators": n_estimators,
        "training_seconds": time.perf_counter() - started,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata
