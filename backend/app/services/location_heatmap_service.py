"""Model-backed heatmaps for the independent Location+ workbench."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd

from app.api.schemas.location import LocationHeatmapFilters, LocationHeatmapResponse
from app.core.config import settings
from app.ml.location_plus import MODEL_FEATURES, OUTCOMES, apply_temperature, expected_run_value


GRID_SIZE = 25
X_DOMAIN = (-2.0, 2.0)
Z_DOMAIN = (0.5, 4.5)
STRIKE_ZONE = (-0.83, 1.5, 0.83, 3.5)
COUNT_OPTIONS = ["All", "0-0", "0-1", "0-2", "1-0", "1-1", "1-2", "2-0", "2-1", "2-2", "3-0", "3-1", "3-2"]


def _artifact_paths() -> tuple[Path, Path]:
    directory = settings.data_dir / "models" / "location_plus"
    return directory / "location_plus_pipeline.joblib", directory / "location_plus_metadata.json"


@lru_cache(maxsize=2)
def _load_artifact(model_mtime: int, metadata_mtime: int):
    model_path, metadata_path = _artifact_paths()
    model = joblib.load(model_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return model, metadata


def load_artifact():
    model_path, metadata_path = _artifact_paths()
    if not model_path.exists() or not metadata_path.exists():
        raise FileNotFoundError("Location+ model artifacts are not available")
    return _load_artifact(model_path.stat().st_mtime_ns, metadata_path.stat().st_mtime_ns)


def _sample_years(sample: str) -> tuple[int, ...]:
    if sample == "training":
        return (2021, 2022, 2023, 2024, 2025)
    year = int(sample)
    if year < 2021 or year > 2026:
        raise ValueError("sample must be training or a season from 2021 through 2026")
    return (year,)


def _count_clause(count: str) -> tuple[str, list[int]]:
    if count == "All":
        return "", []
    if count not in COUNT_OPTIONS:
        raise ValueError("Unsupported count")
    balls, strikes = (int(value) for value in count.split("-"))
    return " AND balls = ? AND strikes = ?", [balls, strikes]


@lru_cache(maxsize=96)
def _observed_context(
    sample: str,
    pitcher_hand: str,
    batter_side: str,
    pitch_type: str,
    count: str,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    count_sql, count_params = _count_clause(count)
    context_frames: list[pd.DataFrame] = []
    density_frames: list[pd.DataFrame] = []
    total_pitches = 0
    for year in _sample_years(sample):
        path = settings.data_dir / f"MLB{year}" / f"mlb_{year}.duckdb"
        if not path.exists():
            continue
        params = [pitcher_hand, batter_side, pitch_type, *count_params]
        where = f"""
            game_type = 'R'
            AND p_throws = ?
            AND stand = ?
            AND pitch_name = ?
            AND plate_x IS NOT NULL
            AND plate_z IS NOT NULL
            {count_sql}
        """
        with duckdb.connect(str(path), read_only=True) as conn:
            context_frames.append(
                conn.execute(
                    f"""
                    SELECT balls, strikes, outs_when_up,
                           CAST(on_1b IS NOT NULL AS INTEGER) AS on_1b,
                           CAST(on_2b IS NOT NULL AS INTEGER) AS on_2b,
                           CAST(on_3b IS NOT NULL AS INTEGER) AS on_3b,
                           COUNT(*) AS pitches
                    FROM pitches
                    WHERE {where}
                    GROUP BY ALL
                    """,
                    params,
                ).fetchdf()
            )
            density = conn.execute(
                f"""
                SELECT
                    LEAST({GRID_SIZE - 1}, GREATEST(0, CAST(FLOOR((plate_x - {X_DOMAIN[0]}) / {(X_DOMAIN[1] - X_DOMAIN[0]) / GRID_SIZE}) AS INTEGER))) AS x_bin,
                    LEAST({GRID_SIZE - 1}, GREATEST(0, CAST(FLOOR((plate_z - {Z_DOMAIN[0]}) / {(Z_DOMAIN[1] - Z_DOMAIN[0]) / GRID_SIZE}) AS INTEGER))) AS z_bin,
                    COUNT(*) AS pitches
                FROM pitches
                WHERE {where}
                  AND plate_x BETWEEN {X_DOMAIN[0]} AND {X_DOMAIN[1]}
                  AND plate_z BETWEEN {Z_DOMAIN[0]} AND {Z_DOMAIN[1]}
                GROUP BY ALL
                """,
                params,
            ).fetchdf()
            density_frames.append(density)
            total_pitches += int(density["pitches"].sum()) if not density.empty else 0

    if context_frames:
        context = pd.concat(context_frames, ignore_index=True)
        context = context.groupby(["balls", "strikes", "outs_when_up", "on_1b", "on_2b", "on_3b"], as_index=False)["pitches"].sum()
    else:
        context = pd.DataFrame()
    if density_frames:
        density = pd.concat(density_frames, ignore_index=True)
        density = density.groupby(["x_bin", "z_bin"], as_index=False)["pitches"].sum()
    else:
        density = pd.DataFrame()
    return context, density, total_pitches


def _pitch_types(model) -> list[str]:
    encoder = model.named_steps["features"].named_transformers_["categorical"].named_steps["onehot"]
    excluded = {"Unknown", "Other", "Pitch Out"}
    return [str(value) for value in encoder.categories_[0] if str(value) not in excluded]


def build_location_heatmap(
    sample: str = "training",
    pitcher_hand: str = "R",
    batter_side: str = "R",
    pitch_type: str = "4-Seam Fastball",
    count: str = "All",
) -> LocationHeatmapResponse:
    pitcher_hand = pitcher_hand.upper()
    batter_side = batter_side.upper()
    if pitcher_hand not in {"L", "R"} or batter_side not in {"L", "R"}:
        raise ValueError("pitcher_hand and batter_side must be L or R")

    model, metadata = load_artifact()
    pitch_types = _pitch_types(model)
    if pitch_type not in pitch_types:
        raise ValueError("Unsupported pitch type")
    context, density, total_pitches = _observed_context(sample, pitcher_hand, batter_side, pitch_type, count)
    warnings: list[str] = []
    if context.empty:
        warnings.append("No matching historical context; using a neutral 0-0, bases-empty context.")
        context = pd.DataFrame([{"balls": 0, "strikes": 0, "outs_when_up": 0, "on_1b": 0, "on_2b": 0, "on_3b": 0, "pitches": 1}])

    context = context.copy()
    weights = context["pitches"].to_numpy(dtype="float64")
    weights /= weights.sum()
    x_step = (X_DOMAIN[1] - X_DOMAIN[0]) / GRID_SIZE
    z_step = (Z_DOMAIN[1] - Z_DOMAIN[0]) / GRID_SIZE
    x_values = X_DOMAIN[0] + (np.arange(GRID_SIZE) + 0.5) * x_step
    z_values = Z_DOMAIN[0] + (np.arange(GRID_SIZE) + 0.5) * z_step
    grid = pd.DataFrame([(x, z) for z in z_values for x in x_values], columns=["plate_x", "plate_z"])
    cell_count = len(grid)
    context_count = len(context)
    prediction = pd.DataFrame(
        {
            "plate_x": np.repeat(grid["plate_x"].to_numpy(), context_count),
            "plate_z": np.repeat(grid["plate_z"].to_numpy(), context_count),
        }
    )
    repeated = pd.concat([context.drop(columns="pitches")] * cell_count, ignore_index=True)
    for column in repeated.columns:
        prediction[column] = repeated[column].to_numpy()
    prediction["plate_z_norm"] = (prediction["plate_z"] - STRIKE_ZONE[1]) / (STRIKE_ZONE[3] - STRIKE_ZONE[1])
    prediction["plate_x_batter"] = prediction["plate_x"] * (-1.0 if batter_side == "L" else 1.0)
    prediction["distance_from_zone_center"] = np.sqrt(
        (prediction["plate_x"] / 0.83) ** 2 + ((prediction["plate_z_norm"] - 0.5) / 0.5) ** 2
    )
    prediction["pitch_type"] = pitch_type
    prediction["stand"] = batter_side
    prediction["p_throws"] = pitcher_hand

    probabilities = apply_temperature(
        model.predict_proba(prediction[MODEL_FEATURES]), float(metadata["temperature"])
    )
    probabilities = probabilities.reshape(cell_count, context_count, -1)
    mixed_probabilities = np.sum(probabilities * weights[None, :, None], axis=1)
    classes = model.named_steps["model"].classes_
    xrv = expected_run_value(mixed_probabilities, classes, metadata["run_values"])
    scale = metadata.get("location_heatmap_scale", metadata["location_plus_scale"])
    location_plus = 100.0 + float(scale["points_per_sd"]) * (
        (float(scale["mean_xrv_per_100"]) - xrv * 100.0) / float(scale["sd_xrv_per_100"])
    )
    class_index = {OUTCOMES[int(value)]: index for index, value in enumerate(classes)}
    density_lookup = {
        (int(row.x_bin), int(row.z_bin)): int(row.pitches)
        for row in density.itertuples(index=False)
    }
    maximum_density = max(density_lookup.values(), default=0)
    cells = []
    for index, row in grid.iterrows():
        x_bin = index % GRID_SIZE
        z_bin = index // GRID_SIZE
        density_count = density_lookup.get((x_bin, z_bin), 0)
        cells.append(
            {
                "x": round(float(row.plate_x), 4),
                "z": round(float(row.plate_z), 4),
                "location_plus": round(float(location_plus[index]), 1),
                "xrv": round(float(xrv[index]), 5),
                "called_strike_pct": round(float(mixed_probabilities[index, class_index["called_strike"]] * 100.0), 1),
                "whiff_pct": round(float(mixed_probabilities[index, class_index["swinging_strike"]] * 100.0), 1),
                "barrel_pct": round(float(mixed_probabilities[index, class_index["barrel"]] * 100.0), 1),
                "ball_pct": round(float(mixed_probabilities[index, class_index["ball"]] * 100.0), 1),
                "density_count": density_count,
                "density_pct": round(density_count / maximum_density * 100.0, 1) if maximum_density else 0.0,
            }
        )

    return LocationHeatmapResponse(
        model_version=str(metadata["model_version"]),
        filters=LocationHeatmapFilters(
            sample=sample,
            pitcher_hand=pitcher_hand,
            batter_side=batter_side,
            pitch_type=pitch_type,
            count=count,
        ),
        pitch_types=pitch_types,
        counts=COUNT_OPTIONS,
        sample_pitches=total_pitches,
        context_rows=context_count,
        grid_size=GRID_SIZE,
        x_domain=list(X_DOMAIN),
        z_domain=list(Z_DOMAIN),
        strike_zone=list(STRIKE_ZONE),
        cells=cells,
        warnings=warnings,
    )
