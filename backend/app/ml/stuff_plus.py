"""Independent pitch-level Pete Stuff+ training and scoring.

The outcome model learns pitcher-positive run value from physical pitch traits,
location, and pre-pitch context.  Stuff scores are then produced by holding the
physical traits fixed and averaging predictions over one deterministic league
context grid, so a pitcher's observed command does not directly raise Stuff+.
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
    classify_outcome,
    expected_run_value,
    outcome_run_values,
)
from app.ml.plus_scoring import shrink_plus


PHYSICAL_FEATURES = [
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
]
CONTEXT_FEATURES = [
    "plate_x",
    "plate_z_norm",
    "balls",
    "strikes",
]
CATEGORICAL_FEATURES = ["pitch_type", "stand", "p_throws"]
MODEL_FEATURES = PHYSICAL_FEATURES + CONTEXT_FEATURES + CATEGORICAL_FEATURES
CONTEXT_COLUMNS = CONTEXT_FEATURES + ["stand"]
SOURCE_COLUMNS = [
    "game_date",
    "game_type",
    "pitcher",
    "pitch_type",
    "pitch_name",
    "release_speed",
    "pfx_x",
    "pfx_z",
    "release_spin_rate",
    "spin_axis",
    "release_extension",
    "release_pos_x",
    "release_pos_z",
    "arm_angle",
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
    "delta_run_exp",
    "description",
    "events",
    "launch_speed_angle",
    "zone",
]
PRIMARY_FASTBALL_CODES = {"FF", "SI", "FC"}
PITCH_TYPE_FAMILIES = {
    "FF": "fastball",
    "SI": "fastball",
    "FC": "fastball",
    "FA": "fastball",
    "SL": "breaking",
    "ST": "breaking",
    "CU": "breaking",
    "KC": "breaking",
    "CS": "breaking",
    "SV": "breaking",
    "CH": "offspeed",
    "FS": "offspeed",
    "FO": "offspeed",
    "KN": "offspeed",
    "EP": "offspeed",
}
VALID_COUNTS = tuple((balls, strikes) for balls in range(4) for strikes in range(3))
STATCAST_ZONES = (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14)


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
    path = database_path(data_dir, year)
    if not path.exists():
        raise FileNotFoundError(f"Missing season database: {path}")
    columns = ", ".join(SOURCE_COLUMNS)
    with duckdb.connect(str(path), read_only=True) as conn:
        frame = conn.execute(
            f"""
            SELECT {columns}
            FROM pitches
            WHERE game_type = 'R'
              AND pitcher IS NOT NULL
              AND pitch_type IS NOT NULL
              AND delta_run_exp IS NOT NULL
              AND release_speed IS NOT NULL
              AND pfx_x IS NOT NULL
              AND pfx_z IS NOT NULL
              AND plate_x IS NOT NULL
              AND plate_z IS NOT NULL
              AND sz_top > sz_bot
            """
        ).fetchdf()
    frame["season"] = int(year)
    if sample_fraction < 1.0:
        frame = frame.sample(frac=sample_fraction, random_state=42)
    return frame.reset_index(drop=True)


def load_seasons(data_dir: Path, years: Iterable[int], sample_fraction: float = 1.0) -> pd.DataFrame:
    return pd.concat(
        [load_season(data_dir, int(year), sample_fraction=sample_fraction) for year in years],
        ignore_index=True,
    )


def build_training_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Create physical, location, context, and pitcher-positive target columns."""

    frame = raw.copy()
    frame["outcome"] = classify_outcome(frame)
    frame["outcome_code"] = frame["outcome"].map({label: index for index, label in enumerate(OUTCOMES)})
    for column in [
        "release_speed", "pfx_x", "pfx_z", "release_spin_rate", "spin_axis",
        "release_extension", "release_pos_x", "release_pos_z", "arm_angle",
        "plate_x", "plate_z", "sz_top", "sz_bot", "balls", "strikes",
        "outs_when_up", "zone", "delta_run_exp",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["pitch_type"] = frame["pitch_type"].fillna("UN").astype(str).str.upper()
    frame["stand"] = frame["stand"].fillna("U").astype(str).str.upper()
    frame["p_throws"] = frame["p_throws"].fillna("U").astype(str).str.upper()
    hand_sign = frame["p_throws"].map({"R": 1.0, "L": -1.0})
    frame["ivb"] = frame["pfx_z"] * 12.0
    frame["hb"] = frame["pfx_x"] * -12.0
    frame["adj_hb"] = frame["hb"] * hand_sign
    frame["adj_release_pos_x"] = frame["release_pos_x"] * hand_sign
    spin_radians = np.deg2rad(frame["spin_axis"])
    frame["spin_axis_x"] = np.cos(spin_radians)
    frame["spin_axis_y"] = np.sin(spin_radians) * hand_sign
    zone_height = (frame["sz_top"] - frame["sz_bot"]).where(frame["sz_top"] > frame["sz_bot"])
    frame["plate_z_norm"] = (frame["plate_z"] - frame["sz_bot"]) / zone_height
    for column in ["on_1b", "on_2b", "on_3b"]:
        frame[column] = frame[column].notna().astype("int8")

    fastballs = frame[frame["pitch_type"].isin(PRIMARY_FASTBALL_CODES)].copy()
    counts = (
        fastballs.groupby(["season", "pitcher", "pitch_type"], as_index=False)
        .size()
        .sort_values(["season", "pitcher", "size", "pitch_type"], ascending=[True, True, False, True])
        .drop_duplicates(["season", "pitcher"])
        .rename(columns={"pitch_type": "primary_fastball"})
    )
    frame = frame.merge(counts[["season", "pitcher", "primary_fastball"]], on=["season", "pitcher"], how="left")
    reference = (
        frame[frame["pitch_type"].eq(frame["primary_fastball"])]
        .groupby(["season", "pitcher"], as_index=False)
        .agg(
            primary_fastball_velo=("release_speed", "mean"),
            primary_fastball_ivb=("ivb", "mean"),
            primary_fastball_hb=("adj_hb", "mean"),
        )
    )
    frame = frame.merge(reference, on=["season", "pitcher"], how="left")
    frame["velo_diff_from_fastball"] = frame["release_speed"] - frame["primary_fastball_velo"]
    frame["ivb_diff_from_fastball"] = frame["ivb"] - frame["primary_fastball_ivb"]
    frame["hb_diff_from_fastball"] = frame["adj_hb"] - frame["primary_fastball_hb"]
    frame["pitcher_value"] = (-frame["delta_run_exp"]).clip(-2.5, 2.5)
    required = ["season", "pitcher", "pitch_type", "p_throws", "pitcher_value", "outcome_code", *PHYSICAL_FEATURES]
    return frame.dropna(subset=required).reset_index(drop=True)


def make_pipeline(random_state: int = 42, n_estimators: int = 300) -> Pipeline:
    numeric = Pipeline([("imputer", SimpleImputer(strategy="median"))])
    categorical = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
        ]
    )
    preprocessor = ColumnTransformer(
        [("numeric", numeric, PHYSICAL_FEATURES + CONTEXT_FEATURES), ("categorical", categorical, CATEGORICAL_FEATURES)]
    )
    classifier = XGBClassifier(
        objective="multi:softprob",
        eval_metric="mlogloss",
        tree_method="hist",
        n_estimators=n_estimators,
        max_depth=6,
        learning_rate=0.045,
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
    actual = frame["pitcher_value"].to_numpy(dtype="float64")
    predicted = -expected_run_value(probabilities, classes, run_values)
    y_true = frame["outcome_code"].to_numpy(dtype="int64")
    class_index = {int(label): index for index, label in enumerate(classes)}
    one_hot = np.zeros_like(probabilities)
    for row, label in enumerate(y_true):
        one_hot[row, class_index[int(label)]] = 1.0
    grouped = frame[["season", "pitcher", "pitch_type", "pitcher_value"]].copy()
    grouped["prediction"] = predicted
    grouped = grouped.groupby(["season", "pitcher", "pitch_type"], as_index=False).agg(
        pitches=("pitcher_value", "size"), actual=("pitcher_value", "mean"), prediction=("prediction", "mean")
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


def standard_context_grid(
    frame: pd.DataFrame,
) -> tuple[list[dict[str, object]], dict[str, dict[str, float]], dict[str, float]]:
    """Build the fixed 2 batter sides x 12 counts x 13 Statcast zones test."""

    source = frame[[*CONTEXT_COLUMNS, "pitch_type", "zone"]].dropna().copy()
    source["stand"] = source["stand"].astype(str).str.upper()
    source["balls"] = pd.to_numeric(source["balls"], errors="coerce")
    source["strikes"] = pd.to_numeric(source["strikes"], errors="coerce")
    source["zone"] = pd.to_numeric(source["zone"], errors="coerce")
    source = source[
        source["stand"].isin(["L", "R"])
        & source["balls"].between(0, 3)
        & source["strikes"].between(0, 2)
        & source["zone"].isin(STATCAST_ZONES)
    ].copy()
    if source.empty:
        raise ValueError("No complete rows are available for the standard Stuff+ context grid")
    source[["balls", "strikes", "zone"]] = source[["balls", "strikes", "zone"]].astype(int)

    count_weights = (
        source.groupby(["stand", "balls", "strikes"], as_index=False)
        .size()
        .rename(columns={"size": "pitches"})
    )
    count_weights["stand_count_weight"] = count_weights["pitches"] / count_weights["pitches"].sum()
    expected_count_keys = {(stand, balls, strikes) for stand in ("L", "R") for balls, strikes in VALID_COUNTS}
    observed_count_keys = set(count_weights[["stand", "balls", "strikes"]].itertuples(index=False, name=None))
    if observed_count_keys != expected_count_keys:
        raise ValueError("Training data does not cover all 24 batter-side/count contexts")

    zone_centers = (
        source.groupby("zone", as_index=False)
        .agg(plate_x=("plate_x", "median"), plate_z_norm=("plate_z_norm", "median"))
    )
    if set(zone_centers["zone"].astype(int)) != set(STATCAST_ZONES):
        raise ValueError("Training data does not cover all 13 Statcast zones")

    contexts = count_weights.merge(zone_centers, how="cross").rename(columns={"zone": "zone_id"})
    contexts = contexts[["stand", "balls", "strikes", "zone_id", "plate_x", "plate_z_norm", "stand_count_weight"]]

    zone_counts = source.groupby(["pitch_type", "zone"], as_index=False).size()
    zone_counts["weight"] = zone_counts["size"] / zone_counts.groupby("pitch_type")["size"].transform("sum")
    pitch_type_zone_weights = {
        str(pitch_type): {str(int(row.zone)): float(row.weight) for row in group.itertuples(index=False)}
        for pitch_type, group in zone_counts.groupby("pitch_type")
    }
    global_counts = source.groupby("zone").size().reindex(STATCAST_ZONES, fill_value=0)
    global_zone_weights = {
        str(int(zone)): float(count / global_counts.sum()) for zone, count in global_counts.items()
    }
    return contexts.to_dict(orient="records"), pitch_type_zone_weights, global_zone_weights


def score_standard_contexts(
    model: Pipeline,
    shape_rows: pd.DataFrame,
    contexts: list[dict[str, object]],
    temperature: float,
    run_values: dict[str, float],
    pitch_type_zone_weights: dict[str, dict[str, float]] | None = None,
    global_zone_weights: dict[str, float] | None = None,
    model_features: list[str] | None = None,
) -> np.ndarray:
    if shape_rows.empty:
        return np.array([], dtype="float64")
    context_frame = pd.DataFrame(contexts)
    selected_features = model_features or MODEL_FEATURES
    scoring_context_columns = [column for column in context_frame.columns if column in selected_features]
    pieces: list[pd.DataFrame] = []
    for row_index, (_, shape) in enumerate(shape_rows.iterrows()):
        expanded = pd.DataFrame([shape.to_dict()] * len(context_frame))
        for column in scoring_context_columns:
            expanded[column] = context_frame[column].to_numpy()
        expanded["_shape_row"] = row_index
        if "stand_count_weight" in context_frame and "zone_id" in context_frame:
            pitch_weights = (pitch_type_zone_weights or {}).get(str(shape.get("pitch_type", "")).upper())
            pitch_weights = pitch_weights or global_zone_weights or {}
            zone_weight = context_frame["zone_id"].astype(int).astype(str).map(pitch_weights).fillna(0.0)
            expanded["_context_weight"] = context_frame["stand_count_weight"].to_numpy(dtype="float64") * zone_weight.to_numpy(dtype="float64")
        else:
            expanded["_context_weight"] = 1.0 / len(context_frame)
        pieces.append(expanded)
    expanded = pd.concat(pieces, ignore_index=True)
    classes = model.named_steps["model"].classes_
    probabilities = apply_temperature(model.predict_proba(expanded[selected_features]), temperature)
    expanded["prediction"] = -expected_run_value(probabilities, classes, run_values)
    expanded["weighted_prediction"] = expanded["prediction"] * expanded["_context_weight"]
    totals = expanded.groupby("_shape_row", sort=True)["_context_weight"].transform("sum")
    if (totals <= 0).any():
        raise ValueError("Standard Stuff+ context weights must sum to a positive value")
    expanded["weighted_prediction"] = expanded["weighted_prediction"] / totals
    return expanded.groupby("_shape_row", sort=True)["weighted_prediction"].sum().to_numpy(dtype="float64")


def stuff_scale(
    model: Pipeline,
    frame: pd.DataFrame,
    contexts: list[dict[str, object]],
    temperature: float,
    run_values: dict[str, float],
    pitch_type_zone_weights: dict[str, dict[str, float]] | None = None,
    global_zone_weights: dict[str, float] | None = None,
    sampled_minimum_pitches: int = 50,
) -> dict[str, float | int]:
    grouped = frame.groupby(["season", "pitcher", "pitch_type", "p_throws"], as_index=False).agg(
        pitches=("pitcher_value", "size"),
        **{column: (column, "mean") for column in PHYSICAL_FEATURES},
    )
    qualified = grouped[grouped["pitches"] >= sampled_minimum_pitches].copy()
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
        raise ValueError("Not enough qualified pitch groups to define the Stuff+ scale")
    qualified["prediction"] = values
    qualified["pitch_family"] = qualified["pitch_type"].map(PITCH_TYPE_FAMILIES).fillna("other")

    def grouped_scales(column: str, minimum_groups: int) -> dict[str, dict[str, float | int]]:
        scales: dict[str, dict[str, float | int]] = {}
        for label, group in qualified.groupby(column):
            if len(group) < minimum_groups or group["prediction"].std(ddof=0) == 0:
                continue
            scales[str(label)] = {
                "mean_pitcher_value": float(group["prediction"].mean()),
                "sd_pitcher_value": float(group["prediction"].std(ddof=0)),
                "qualified_pitch_groups": int(len(group)),
            }
        return scales

    return {
        "mean_pitcher_value": float(np.mean(values)),
        "sd_pitcher_value": float(np.std(values)),
        "points_per_sd": 10.0,
        "minimum_pitch_type_pitches": 50,
        "sampled_scale_minimum_pitches": int(sampled_minimum_pitches),
        "season_shrinkage_pitches": 50,
        "outing_shrinkage_pitches": 10,
        "qualified_pitch_groups": int(len(values)),
        "pitch_type_scales": grouped_scales("pitch_type", minimum_groups=30),
        "pitch_family_scales": grouped_scales("pitch_family", minimum_groups=60),
    }


def train_stuff_plus(
    data_dir: Path,
    artifact_dir: Path,
    n_estimators: int = 300,
    sample_fraction: float = 0.35,
) -> dict[str, object]:
    """Train, validate, test, refit, and persist deterministic Pete Stuff+."""

    started = time.perf_counter()
    if not 0 < sample_fraction <= 1:
        raise ValueError("sample_fraction must be in (0, 1]")
    prepared = [build_training_frame(load_season(data_dir, year, sample_fraction)) for year in range(2021, 2027)]
    frame = pd.concat(prepared, ignore_index=True)
    train = frame[frame["season"].between(2021, 2024)].copy()
    validation = frame[frame["season"].eq(2025)].copy()
    test = frame[frame["season"].eq(2026)].copy()

    development_model = make_pipeline(n_estimators=n_estimators)
    development_model.fit(train[MODEL_FEATURES], train["outcome_code"])
    classes = development_model.named_steps["model"].classes_
    development_run_values = outcome_run_values(train)
    validation_raw = development_model.predict_proba(validation[MODEL_FEATURES])
    temperature = choose_temperature(validation["outcome_code"].to_numpy(dtype="int64"), validation_raw, classes)
    validation_probabilities = apply_temperature(validation_raw, temperature)
    test_probabilities = apply_temperature(development_model.predict_proba(test[MODEL_FEATURES]), temperature)

    production_train = frame[frame["season"].between(2021, 2025)].copy()
    production_model = make_pipeline(n_estimators=n_estimators)
    production_model.fit(production_train[MODEL_FEATURES], production_train["outcome_code"])
    production_run_values = outcome_run_values(production_train)
    contexts, pitch_type_zone_weights, global_zone_weights = standard_context_grid(train)
    scale = stuff_scale(
        production_model,
        production_train,
        contexts,
        temperature,
        production_run_values,
        pitch_type_zone_weights,
        global_zone_weights,
        sampled_minimum_pitches=max(5, round(50 * sample_fraction)),
    )

    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "pete_stuff_pipeline.joblib"
    metadata_path = artifact_dir / "pete_stuff_metadata.json"
    joblib.dump(production_model, model_path, compress=3)
    metadata: dict[str, object] = {
        "model_version": "pete_stuff_outcome_probability_v3_312_contexts",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "definition": "Pitch-outcome probabilities converted to expected pitcher run value over one deterministic 2-side x 12-count x 13-zone test, league weighted and pitch-type scaled; no pitcher identity or external Stuff+ target.",
        "development_train_years": [2021, 2022, 2023, 2024],
        "validation_year": 2025,
        "test_year": 2026,
        "production_train_years": [2021, 2022, 2023, 2024, 2025],
        "physical_features": PHYSICAL_FEATURES,
        "context_features": CONTEXT_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "outcomes": [OUTCOMES[int(value)] for value in production_model.named_steps["model"].classes_],
        "temperature": temperature,
        "run_values": production_run_values,
        "standard_contexts": contexts,
        "standard_context_scheme": "2 batter sides x 12 counts x 13 Statcast zones",
        "pitch_type_zone_weights": pitch_type_zone_weights,
        "global_zone_weights": global_zone_weights,
        "stuff_plus_scale": scale,
        "validation_metrics": asdict(evaluate(validation, validation_probabilities, classes, development_run_values)),
        "test_metrics": asdict(evaluate(test, test_probabilities, classes, development_run_values)),
        "rows": {
            "development_train": int(len(train)),
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


def load_artifact(artifact_dir: Path) -> tuple[Pipeline, dict[str, object]]:
    model = joblib.load(artifact_dir / "pete_stuff_pipeline.joblib")
    metadata = json.loads((artifact_dir / "pete_stuff_metadata.json").read_text(encoding="utf-8"))
    return model, metadata


def score_pitch_types(
    model: Pipeline,
    metadata: dict[str, object],
    shape_rows: pd.DataFrame,
    outing: bool = False,
) -> pd.DataFrame:
    scored = shape_rows.copy()
    artifact_features = [
        *list(metadata.get("physical_features", PHYSICAL_FEATURES)),
        *list(metadata.get("context_features", CONTEXT_FEATURES)),
        *list(metadata.get("categorical_features", CATEGORICAL_FEATURES)),
    ]
    raw = score_standard_contexts(
        model,
        scored,
        list(metadata["standard_contexts"]),
        float(metadata["temperature"]),
        {str(key): float(value) for key, value in dict(metadata["run_values"]).items()},
        {
            str(pitch_type): {str(zone): float(weight) for zone, weight in dict(weights).items()}
            for pitch_type, weights in dict(metadata.get("pitch_type_zone_weights", {})).items()
        },
        {str(zone): float(weight) for zone, weight in dict(metadata.get("global_zone_weights", {})).items()},
        artifact_features,
    )
    scale = dict(metadata["stuff_plus_scale"])
    pitch_type_scales = dict(scale.get("pitch_type_scales", {}))
    pitch_family_scales = dict(scale.get("pitch_family_scales", {}))
    means: list[float] = []
    standard_deviations: list[float] = []
    scale_sources: list[str] = []
    for pitch_type in scored["pitch_type"].astype(str).str.upper():
        selected = pitch_type_scales.get(pitch_type)
        source = f"pitch_type:{pitch_type}"
        if selected is None:
            family = PITCH_TYPE_FAMILIES.get(pitch_type, "other")
            selected = pitch_family_scales.get(family)
            source = f"pitch_family:{family}"
        if selected is None:
            selected = scale
            source = "global"
        means.append(float(selected["mean_pitcher_value"]))
        standard_deviations.append(float(selected["sd_pitcher_value"]))
        scale_sources.append(source)
    unshrunk = 100.0 + 10.0 * (raw - np.asarray(means)) / np.asarray(standard_deviations)
    shrinkage = float(scale["outing_shrinkage_pitches"] if outing else scale["season_shrinkage_pitches"])
    pitches = pd.to_numeric(scored["pitches"], errors="coerce").fillna(0).to_numpy(dtype="float64")
    adjusted, reliability = shrink_plus(unshrunk, pitches, prior_pitches=shrinkage)
    scored["raw_stuff_plus"] = unshrunk
    scored["stuff_plus"] = adjusted
    scored["reliability"] = reliability
    scored["scale_source"] = scale_sources
    return scored
