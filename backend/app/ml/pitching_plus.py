"""Research-to-production Pitching+ training and export.

The base model estimates the complete pitch from physical traits, actual
location, and pre-pitch context.  A separate sequence challenger adds only
information that was known before the current pitch.  Keeping both artifacts
separate lets validation decide whether pitch order adds real out-of-sample
signal without silently changing the public Pitching+ definition.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import log_loss, mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from app.ml.location_plus import (
    OUTCOMES,
    apply_temperature,
    calibration_error,
    choose_temperature,
    expected_run_value,
    outcome_run_values,
)
from app.ml.stuff_plus import PHYSICAL_FEATURES, SOURCE_COLUMNS as STUFF_SOURCE_COLUMNS, build_training_frame


LOCATION_FEATURES = [
    "plate_x",
    "plate_z_norm",
    "plate_x_batter",
    "distance_from_zone_center",
]
GAME_CONTEXT_FEATURES = ["balls", "strikes", "outs_when_up", "on_1b", "on_2b", "on_3b"]
BASE_CATEGORICAL_FEATURES = ["pitch_type", "stand", "p_throws"]
BASE_NUMERIC_FEATURES = PHYSICAL_FEATURES + LOCATION_FEATURES + GAME_CONTEXT_FEATURES
BASE_FEATURES = BASE_NUMERIC_FEATURES + BASE_CATEGORICAL_FEATURES

SEQUENCE_NUMERIC_FEATURES = [
    "sequence_position",
    "delta_release_speed_from_previous",
    "delta_ivb_from_previous",
    "delta_adj_hb_from_previous",
    "delta_plate_x_batter_from_previous",
    "delta_plate_z_norm_from_previous",
]
SEQUENCE_CATEGORICAL_FEATURES = ["previous_pitch_type"]
SEQUENCE_FEATURES = BASE_FEATURES + SEQUENCE_NUMERIC_FEATURES + SEQUENCE_CATEGORICAL_FEATURES
SEQUENCE_KEYS = ["game_pk", "at_bat_number", "pitch_number", "pitch_uid"]
SOURCE_COLUMNS = list(dict.fromkeys([*STUFF_SOURCE_COLUMNS, *SEQUENCE_KEYS]))


@dataclass(frozen=True)
class SplitMetrics:
    rows: int
    log_loss: float
    brier_score: float
    calibration_error: float
    run_value_mae: float
    run_value_rmse: float
    run_value_correlation: float | None
    grouped_correlation: float | None


def database_path(data_dir: Path, year: int) -> Path:
    return data_dir / f"MLB{year}" / f"mlb_{year}.duckdb"


def load_season(data_dir: Path, year: int, sample_fraction: float = 1.0) -> pd.DataFrame:
    """Load complete plate appearances so lag features remain valid when sampled."""

    path = database_path(data_dir, year)
    if not path.exists():
        raise FileNotFoundError(f"Missing season database: {path}")
    threshold = round(sample_fraction * 1_000_000)
    sampling = "" if sample_fraction >= 1 else f"AND hash(game_pk, at_bat_number) % 1000000 < {threshold}"
    columns = ", ".join(SOURCE_COLUMNS)
    with duckdb.connect(str(path), read_only=True) as conn:
        frame = conn.execute(
            f"""
            SELECT {columns}
            FROM pitches
            WHERE game_type = 'R'
              AND game_pk IS NOT NULL
              AND at_bat_number IS NOT NULL
              AND pitch_number IS NOT NULL
              AND pitcher IS NOT NULL
              AND pitch_type IS NOT NULL
              AND delta_run_exp IS NOT NULL
              AND release_speed IS NOT NULL
              AND pfx_x IS NOT NULL
              AND pfx_z IS NOT NULL
              AND plate_x IS NOT NULL
              AND plate_z IS NOT NULL
              AND sz_top > sz_bot
              {sampling}
            """
        ).fetchdf()
    frame["season"] = int(year)
    return frame.reset_index(drop=True)


def load_seasons(data_dir: Path, years: Iterable[int], sample_fraction: float = 1.0) -> pd.DataFrame:
    return pd.concat(
        [load_season(data_dir, int(year), sample_fraction=sample_fraction) for year in years],
        ignore_index=True,
    )


def build_pitching_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Add full-pitch and within-plate-appearance sequence features."""

    frame = build_training_frame(raw)
    frame["plate_x_batter"] = frame["plate_x"] * np.where(frame["stand"].eq("L"), -1.0, 1.0)
    frame["distance_from_zone_center"] = np.sqrt(
        (frame["plate_x"] / 0.83) ** 2 + ((frame["plate_z_norm"] - 0.5) / 0.5) ** 2
    )
    frame = frame.sort_values(["season", "game_pk", "at_bat_number", "pitch_number"], kind="stable")
    groups = frame.groupby(["season", "game_pk", "at_bat_number"], sort=False)
    previous_type = groups["pitch_type"].shift(1)
    frame["previous_pitch_type"] = previous_type.fillna("START")
    frame["sequence_position"] = groups.cumcount() + 1
    for source, target in [
        ("release_speed", "delta_release_speed_from_previous"),
        ("ivb", "delta_ivb_from_previous"),
        ("adj_hb", "delta_adj_hb_from_previous"),
        ("plate_x_batter", "delta_plate_x_batter_from_previous"),
        ("plate_z_norm", "delta_plate_z_norm_from_previous"),
    ]:
        frame[target] = (frame[source] - groups[source].shift(1)).fillna(0.0)
    return frame.reset_index(drop=True)


def make_pipeline(*, sequence: bool, random_state: int = 42, n_estimators: int = 260) -> Pipeline:
    numeric_features = BASE_NUMERIC_FEATURES + (SEQUENCE_NUMERIC_FEATURES if sequence else [])
    categorical_features = BASE_CATEGORICAL_FEATURES + (SEQUENCE_CATEGORICAL_FEATURES if sequence else [])
    numeric = Pipeline([("imputer", SimpleImputer(strategy="median"))])
    categorical = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
        ]
    )
    preprocessor = ColumnTransformer(
        [("numeric", numeric, numeric_features), ("categorical", categorical, categorical_features)]
    )
    classifier = XGBClassifier(
        objective="multi:softprob",
        eval_metric="mlogloss",
        tree_method="hist",
        n_estimators=n_estimators,
        max_depth=6,
        learning_rate=0.05,
        min_child_weight=30,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=2.0,
        n_jobs=-1,
        random_state=random_state,
    )
    return Pipeline([("features", preprocessor), ("model", classifier)])


def _correlation(actual: np.ndarray, predicted: np.ndarray) -> float | None:
    valid = np.isfinite(actual) & np.isfinite(predicted)
    if valid.sum() < 2 or np.std(actual[valid]) == 0 or np.std(predicted[valid]) == 0:
        return None
    return float(np.corrcoef(actual[valid], predicted[valid])[0, 1])


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
    predicted = expected_run_value(probabilities, classes, run_values)
    actual = frame["delta_run_exp"].to_numpy(dtype="float64")
    grouped = frame[["season", "pitcher", "pitch_type", "delta_run_exp"]].copy()
    grouped["prediction"] = predicted
    grouped = grouped.groupby(["season", "pitcher", "pitch_type"], as_index=False).agg(
        pitches=("delta_run_exp", "size"), actual=("delta_run_exp", "mean"), prediction=("prediction", "mean")
    )
    grouped = grouped[grouped["pitches"] >= 50]
    return SplitMetrics(
        rows=int(len(frame)),
        log_loss=float(log_loss(y_true, probabilities, labels=classes)),
        brier_score=float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1))),
        calibration_error=calibration_error(y_true, probabilities, classes),
        run_value_mae=float(mean_absolute_error(actual, predicted)),
        run_value_rmse=float(math.sqrt(mean_squared_error(actual, predicted))),
        run_value_correlation=_correlation(actual, predicted),
        grouped_correlation=_correlation(grouped["actual"].to_numpy(), grouped["prediction"].to_numpy()),
    )


def pitching_scale(frame: pd.DataFrame, xrv: np.ndarray, minimum_pitches: int) -> dict[str, float | int]:
    grouped = frame[["season", "pitcher"]].copy()
    grouped["xrv_pitching"] = xrv
    grouped = grouped.groupby(["season", "pitcher"], as_index=False).agg(
        pitches=("xrv_pitching", "size"), xrv_pitching=("xrv_pitching", "mean")
    )
    qualified = grouped[grouped["pitches"] >= minimum_pitches]
    if len(qualified) < 2 or qualified["xrv_pitching"].std(ddof=0) == 0:
        raise ValueError("Not enough qualified pitcher seasons to define Pitching+ scale")
    return {
        "mean_xrv": float(qualified["xrv_pitching"].mean()),
        "sd_xrv": float(qualified["xrv_pitching"].std(ddof=0)),
        "points_per_sd": 10.0,
        "minimum_pitches": int(minimum_pitches),
        "qualified_pitcher_seasons": int(len(qualified)),
    }


def _probabilities(model: Pipeline, frame: pd.DataFrame, features: list[str], temperature: float) -> np.ndarray:
    return apply_temperature(model.predict_proba(frame[features]), temperature)


def _plus(xrv: pd.Series | np.ndarray, scale: dict[str, float | int]) -> np.ndarray:
    return 100.0 + 10.0 * (float(scale["mean_xrv"]) - np.asarray(xrv)) / float(scale["sd_xrv"])


def export_2026_scores(
    frame: pd.DataFrame,
    probabilities: np.ndarray,
    classes: np.ndarray,
    run_values: dict[str, float],
    scale: dict[str, float | int],
    artifact_dir: Path,
    export_year: int = 2026,
) -> dict[str, str | int]:
    scored = frame[["pitch_uid", "game_pk", "game_date", "pitcher", "pitch_type"]].copy()
    scored["xrv_pitching"] = expected_run_value(probabilities, classes, run_values)
    scored["pitching_plus"] = _plus(scored["xrv_pitching"], scale)
    pitch_path = artifact_dir / f"pitching_plus_pitches_{int(export_year)}.parquet"
    pitch_temporary = pitch_path.with_suffix(".tmp.parquet")
    scored.to_parquet(pitch_temporary, index=False)
    pitcher = scored.groupby("pitcher", as_index=False).agg(
        pitches=("xrv_pitching", "size"), xrv_pitching=("xrv_pitching", "mean")
    )
    pitcher["pitching_plus"] = _plus(pitcher["xrv_pitching"], scale)
    pitcher_path = artifact_dir / f"pitching_plus_pitchers_{int(export_year)}.csv"
    pitcher_temporary = pitcher_path.with_suffix(".tmp.csv")
    pitcher.to_csv(pitcher_temporary, index=False)
    pitch_type = scored.groupby(["pitcher", "pitch_type"], as_index=False).agg(
        pitches=("xrv_pitching", "size"), xrv_pitching=("xrv_pitching", "mean")
    )
    pitch_type["pitching_plus"] = _plus(pitch_type["xrv_pitching"], scale)
    pitch_type_path = artifact_dir / f"pitching_plus_pitch_types_{int(export_year)}.csv"
    pitch_type_temporary = pitch_type_path.with_suffix(".tmp.csv")
    pitch_type.to_csv(pitch_type_temporary, index=False)
    pitch_temporary.replace(pitch_path)
    pitcher_temporary.replace(pitcher_path)
    pitch_type_temporary.replace(pitch_type_path)
    return {
        "pitch_rows": int(len(scored)),
        "pitcher_rows": int(len(pitcher)),
        "pitch_type_rows": int(len(pitch_type)),
        "pitch_path": str(pitch_path),
        "pitcher_path": str(pitcher_path),
        "pitch_type_path": str(pitch_type_path),
    }


def train_pitching_plus(
    data_dir: Path,
    artifact_dir: Path,
    n_estimators: int = 260,
    sample_fraction: float = 0.25,
) -> dict[str, object]:
    """Train the base metric and a separately evaluated sequence challenger."""

    started = time.perf_counter()
    if not 0 < sample_fraction <= 1:
        raise ValueError("sample_fraction must be in (0, 1]")
    frame = build_pitching_frame(load_seasons(data_dir, range(2021, 2027), sample_fraction))
    train = frame[frame["season"].between(2021, 2024)].copy()
    validation = frame[frame["season"].eq(2025)].copy()
    test = frame[frame["season"].eq(2026)].copy()
    run_values = outcome_run_values(train)

    candidates: dict[str, dict[str, object]] = {}
    trained: dict[str, Pipeline] = {}
    for name, features, sequence in [
        ("base", BASE_FEATURES, False),
        ("sequence", SEQUENCE_FEATURES, True),
    ]:
        model = make_pipeline(sequence=sequence, n_estimators=n_estimators)
        model.fit(train[features], train["outcome_code"])
        classes = model.named_steps["model"].classes_
        validation_raw = model.predict_proba(validation[features])
        temperature = choose_temperature(validation["outcome_code"].to_numpy(dtype="int64"), validation_raw, classes)
        validation_probabilities = apply_temperature(validation_raw, temperature)
        test_probabilities = _probabilities(model, test, features, temperature)
        candidates[name] = {
            "features": features,
            "temperature": temperature,
            "validation_metrics": asdict(evaluate(validation, validation_probabilities, classes, run_values)),
            "test_metrics": asdict(evaluate(test, test_probabilities, classes, run_values)),
        }
        trained[name] = model

    # The public candidate remains the interpretable complete-pitch base model.
    # Sequence is retained as a challenger until it clears all release gates.
    base_development_model = trained["base"]
    base_development_classes = base_development_model.named_steps["model"].classes_
    base_validation_probabilities = _probabilities(
        base_development_model,
        validation,
        BASE_FEATURES,
        float(candidates["base"]["temperature"]),
    )
    validation_xrv = expected_run_value(
        base_validation_probabilities,
        base_development_classes,
        run_values,
    )
    # Define the public scale on genuinely unseen 2025 predictions.  Using
    # in-sample production predictions would make the spread look artificially
    # large and would destabilize the meaning of ten plus-points.
    scale = pitching_scale(
        validation,
        validation_xrv,
        minimum_pitches=max(40, round(500 * sample_fraction)),
    )

    production_train = frame[frame["season"].between(2021, 2025)].copy()
    production_model = make_pipeline(sequence=False, n_estimators=n_estimators)
    production_model.fit(production_train[BASE_FEATURES], production_train["outcome_code"])
    production_classes = production_model.named_steps["model"].classes_
    production_run_values = outcome_run_values(production_train)
    production_reference_probabilities = _probabilities(
        production_model,
        validation,
        BASE_FEATURES,
        float(candidates["base"]["temperature"]),
    )
    production_reference_xrv = expected_run_value(
        production_reference_probabilities,
        production_classes,
        production_run_values,
    )
    production_reference = pitching_scale(
        validation,
        production_reference_xrv,
        minimum_pitches=max(40, round(500 * sample_fraction)),
    )
    scale["mean_xrv"] = float(production_reference["mean_xrv"])
    scale["center_model"] = "production model on 2025 reference season"
    scale["spread_model"] = "development model on unseen 2025 validation season"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(production_model, artifact_dir / "pete_pitching_pipeline.joblib", compress=3)
    joblib.dump(trained["sequence"], artifact_dir / "pete_pitching_sequence_challenger.joblib", compress=3)
    test_probabilities = _probabilities(
        production_model, test, BASE_FEATURES, float(candidates["base"]["temperature"])
    )
    exports = export_2026_scores(
        test,
        test_probabilities,
        production_classes,
        production_run_values,
        scale,
        artifact_dir,
        export_year=2026,
    )
    metadata: dict[str, object] = {
        "model_version": "pete_pitching_complete_pitch_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "public_candidate": "base",
        "definition": "Independent complete-pitch outcome model using physical traits, actual location, and pre-pitch context.",
        "development_train_years": [2021, 2022, 2023, 2024],
        "validation_year": 2025,
        "test_year": 2026,
        "production_train_years": [2021, 2022, 2023, 2024, 2025],
        "outcomes": [OUTCOMES[int(value)] for value in production_classes],
        "run_values": production_run_values,
        "pitching_plus_scale": scale,
        "candidates": candidates,
        "sequence_policy": "Research challenger only; lag features never cross game/plate-appearance boundaries.",
        "rows": {
            "development_train": int(len(train)),
            "validation": int(len(validation)),
            "test": int(len(test)),
            "production_train": int(len(production_train)),
        },
        "sample_fraction": sample_fraction,
        "n_estimators": n_estimators,
        "exports": exports,
        "training_seconds": time.perf_counter() - started,
    }
    (artifact_dir / "pete_pitching_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metadata


def refresh_pitching_exports(
    data_dir: Path,
    artifact_dir: Path,
    reference_year: int = 2025,
    export_year: int = 2026,
) -> dict[str, object]:
    """Re-center the production artifact and export every pitch for one season."""

    metadata_path = artifact_dir / "pete_pitching_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    model: Pipeline = joblib.load(artifact_dir / "pete_pitching_pipeline.joblib")
    temperature = float(dict(metadata["candidates"])["base"]["temperature"])
    run_values = {str(key): float(value) for key, value in dict(metadata["run_values"]).items()}
    classes = model.named_steps["model"].classes_

    reference = build_pitching_frame(load_season(data_dir, reference_year, 1.0))
    reference_probabilities = _probabilities(model, reference, BASE_FEATURES, temperature)
    reference_xrv = expected_run_value(reference_probabilities, classes, run_values)
    reference_scale = pitching_scale(reference, reference_xrv, minimum_pitches=500)
    scale = dict(metadata["pitching_plus_scale"])

    export_source = load_season(data_dir, export_year, 1.0)
    export = build_pitching_frame(export_source)
    export_probabilities = _probabilities(model, export, BASE_FEATURES, temperature)
    export_xrv = expected_run_value(export_probabilities, classes, run_values)
    export_scale = pitching_scale(
        export,
        export_xrv,
        minimum_pitches=int(scale["minimum_pitches"]),
    )
    # A plus metric is centered on the league being displayed.  Keep the
    # out-of-sample 2025 spread, but re-center on the current export season so
    # distribution drift cannot move the league average away from 100.
    scale["mean_xrv"] = float(export_scale["mean_xrv"])
    scale["reference_year"] = int(reference_year)
    scale["center_year"] = int(export_year)
    scale["reference_mean_xrv"] = float(reference_scale["mean_xrv"])
    scale["center_model"] = "production model on export-season qualified pitchers"
    scale["spread_model"] = "development model on unseen validation season"
    exports = export_2026_scores(
        export, export_probabilities, classes, run_values, scale, artifact_dir, export_year=export_year
    )
    metadata["pitching_plus_scale"] = scale
    metadata["exports"] = exports
    metadata["export_year"] = int(export_year)
    metadata["exported_at"] = datetime.now(timezone.utc).isoformat()
    dates = pd.to_datetime(export.get("game_date"), errors="coerce")
    metadata["data_as_of"] = dates.max().date().isoformat() if dates.notna().any() else None
    source_dates = pd.to_datetime(export_source.get("game_date"), errors="coerce")
    metadata["source_data_as_of"] = source_dates.max().date().isoformat() if source_dates.notna().any() else None
    metadata_temporary = metadata_path.with_suffix(".tmp")
    metadata_temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    metadata_temporary.replace(metadata_path)
    return metadata
