"""Reusable Location+ feature and scoring calculations."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.api.schemas.common import AnalysisResponse, MetricItem, ResponseMeta
from app.core.config import settings
from app.repositories.pitch_repository import load_pitcher_cached_season
from app.services.discipline_service import SWING_EVENTS, meatball_zone_mask, red_strike_zone_mask
from app.services.personal_service import dataframe_to_table_payload, display_pitch_name, normalize_pitch_names


STRIKE_ZONE_BOX = (-0.83, 1.5, 1.66, 2.0)
EXPANDED_SHADOW_BOX = (-1.33, 1.17, 2.66, 2.66)
EXPANDED_CHASE_BOX = (-2.0, 0.5, 4.0, 4.0)
EXPANDED_HEART_X = (-0.67, 0.67)
EXPANDED_SHADOW_VERTICAL_EXTENSION = 0.33
ORIGINAL_HEART_BOX = (
    EXPANDED_HEART_X[0],
    STRIKE_ZONE_BOX[1] + EXPANDED_SHADOW_VERTICAL_EXTENSION,
    EXPANDED_HEART_X[1] - EXPANDED_HEART_X[0],
    STRIKE_ZONE_BOX[3] - EXPANDED_SHADOW_VERTICAL_EXTENSION * 2,
)

LOCATION_FEATURE_COLUMNS = [
    "zone_pct",
    "heart_pct",
    "meatball_pct",
    "shadow_pct",
    "chase_pct",
    "waste_pct",
    "edge_pct",
    "o_swing_pct",
    "first_pitch_strike_pct",
    "hitter_ahead_pct",
    "pitcher_ahead_pct",
    "two_strike_pct",
]


def _numeric_series(data: pd.DataFrame, column: str) -> pd.Series:
    if column not in data.columns:
        return pd.Series(np.nan, index=data.index, dtype="float64")
    return pd.to_numeric(data[column], errors="coerce")


def _text_series(data: pd.DataFrame, column: str) -> pd.Series:
    if column not in data.columns:
        return pd.Series("", index=data.index, dtype="object")
    return data[column].fillna("").astype(str).str.lower().str.strip()


def _box_mask(plate_x: pd.Series, plate_z: pd.Series, box: tuple[float, float, float, float]) -> pd.Series:
    x_min, z_min, width, height = box
    return plate_x.between(x_min, x_min + width) & plate_z.between(z_min, z_min + height)


def add_location_features(data: pd.DataFrame) -> pd.DataFrame:
    """Add red-zone, heart, shadow, chase, and count context flags."""

    working = normalize_pitch_names(data.copy())
    plate_x = _numeric_series(working, "plate_x") * -1.0
    plate_z = _numeric_series(working, "plate_z")
    zone_num = _numeric_series(working, "zone")
    description = _text_series(working, "description")
    balls = _numeric_series(working, "balls")
    strikes = _numeric_series(working, "strikes")
    pitch_number = _numeric_series(working, "pitch_number")

    in_zone = red_strike_zone_mask(working)
    has_coordinates = plate_x.notna() & plate_z.notna()
    heart = _box_mask(plate_x, plate_z, ORIGINAL_HEART_BOX)
    shadow = _box_mask(plate_x, plate_z, EXPANDED_SHADOW_BOX) & ~heart
    chase = _box_mask(plate_x, plate_z, EXPANDED_CHASE_BOX) & ~_box_mask(plate_x, plate_z, EXPANDED_SHADOW_BOX)
    waste = has_coordinates & ~_box_mask(plate_x, plate_z, EXPANDED_CHASE_BOX)

    working["_display_plate_x"] = plate_x
    working["_plate_z"] = plate_z
    working["_in_zone"] = in_zone
    working["_heart_zone"] = heart.where(has_coordinates, zone_num.isin([1, 3, 5, 7, 9])).fillna(False)
    working["_meatball_zone"] = meatball_zone_mask(working)
    working["_shadow_zone"] = shadow.where(has_coordinates, zone_num.isin([11, 12, 13, 14])).fillna(False)
    working["_chase_zone"] = chase.where(has_coordinates, zone_num.isin([15, 16, 17, 18, 19])).fillna(False)
    working["_waste_zone"] = waste.fillna(False)
    working["_edge_zone"] = zone_num.isin([2, 4, 6, 8, 11, 12, 13, 14, 16, 17, 18, 19])
    working["_is_swing"] = description.isin(SWING_EVENTS)
    working["_out_zone"] = has_coordinates & ~in_zone
    working["_first_pitch"] = pitch_number.eq(1)
    working["_hitter_ahead"] = balls > strikes
    working["_pitcher_ahead"] = strikes > balls
    working["_two_strike"] = strikes.eq(2)
    return working


def _rate(mask: pd.Series, denominator: int | float | None = None) -> float:
    if denominator is None:
        denominator = len(mask)
    if not denominator:
        return float("nan")
    return float(mask.sum() / denominator * 100.0)


def _location_row(group: pd.DataFrame, label: str) -> dict[str, Any]:
    pitch_count = len(group)
    out_zone = group["_out_zone"] if "_out_zone" in group else pd.Series(dtype="bool")
    swings = group["_is_swing"] if "_is_swing" in group else pd.Series(dtype="bool")
    first_pitch = group["_first_pitch"] if "_first_pitch" in group else pd.Series(dtype="bool")
    return {
        "Pitch": label,
        "pitches": pitch_count,
        "zone_pct": _rate(group["_in_zone"]) if pitch_count else np.nan,
        "heart_pct": _rate(group["_heart_zone"]) if pitch_count else np.nan,
        "meatball_pct": _rate(group["_meatball_zone"]) if pitch_count else np.nan,
        "shadow_pct": _rate(group["_shadow_zone"]) if pitch_count else np.nan,
        "chase_pct": _rate(group["_chase_zone"]) if pitch_count else np.nan,
        "waste_pct": _rate(group["_waste_zone"]) if pitch_count else np.nan,
        "edge_pct": _rate(group["_edge_zone"]) if pitch_count else np.nan,
        "o_swing_pct": _rate(swings[out_zone], int(out_zone.sum())) if int(out_zone.sum()) else np.nan,
        "first_pitch_strike_pct": _rate(group.loc[first_pitch, "_in_zone"], int(first_pitch.sum())) if int(first_pitch.sum()) else np.nan,
        "hitter_ahead_pct": _rate(group["_hitter_ahead"]) if pitch_count else np.nan,
        "pitcher_ahead_pct": _rate(group["_pitcher_ahead"]) if pitch_count else np.nan,
        "two_strike_pct": _rate(group["_two_strike"]) if pitch_count else np.nan,
    }


def build_location_feature_table(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()

    working = add_location_features(data)
    rows = [_location_row(working, "Overall")]
    if "pitch_name" in working.columns:
        for pitch_name in working["pitch_name"].dropna().astype(str).value_counts().index.tolist():
            pitch_group = working[working["pitch_name"].astype(str).eq(pitch_name)].copy()
            rows.append(_location_row(pitch_group, display_pitch_name(pitch_name)))
    return pd.DataFrame(rows)


def build_location_feature_diagnostics(feature_df: pd.DataFrame, source_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rows.append({"check": "source_pitches", "value": int(len(source_df)), "status": "ok" if len(source_df) else "empty"})
    rows.append({
        "check": "coordinate_coverage",
        "value": round(float((_numeric_series(source_df, "plate_x").notna() & _numeric_series(source_df, "plate_z").notna()).mean() * 100.0), 1)
        if len(source_df)
        else 0.0,
        "status": "ok" if len(source_df) and {"plate_x", "plate_z"}.issubset(source_df.columns) else "missing",
    })
    for column in LOCATION_FEATURE_COLUMNS:
        if column not in feature_df.columns or feature_df.empty:
            coverage = 0.0
        else:
            coverage = float(pd.to_numeric(feature_df[column], errors="coerce").notna().mean() * 100.0)
        rows.append({
            "check": column,
            "value": round(coverage, 1),
            "status": "ok" if coverage >= 80 else ("partial" if coverage > 0 else "missing"),
        })
    return pd.DataFrame(rows)


def build_prototype_location_scores(feature_df: pd.DataFrame) -> pd.DataFrame:
    """Transparent command proxy until trained Location+ artifacts are connected."""

    if feature_df.empty:
        return pd.DataFrame()

    scored = feature_df.copy()
    zone = pd.to_numeric(scored.get("zone_pct"), errors="coerce").fillna(50.0)
    shadow = pd.to_numeric(scored.get("shadow_pct"), errors="coerce").fillna(25.0)
    heart = pd.to_numeric(scored.get("heart_pct"), errors="coerce").fillna(15.0)
    waste = pd.to_numeric(scored.get("waste_pct"), errors="coerce").fillna(5.0)
    edge = pd.to_numeric(scored.get("edge_pct"), errors="coerce").fillna(20.0)
    o_swing = pd.to_numeric(scored.get("o_swing_pct"), errors="coerce").fillna(25.0)

    scored["prototype_location_plus"] = (
        100
        + (shadow - 25.0) * 0.35
        + (edge - 20.0) * 0.20
        + (o_swing - 25.0) * 0.15
        - (heart - 15.0) * 0.25
        - (waste - 5.0) * 0.50
        + (zone - 50.0).abs() * -0.05
    ).round(1)
    scored["model_status"] = "prototype_proxy"
    columns = ["Pitch", "pitches", "prototype_location_plus", *LOCATION_FEATURE_COLUMNS, "model_status"]
    return scored[[column for column in columns if column in scored.columns]].copy()


def get_location_features(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> AnalysisResponse:
    pitch_df = load_pitcher_cached_season(year=year, pitcher_id=pitcher_id, data_dir=settings.data_dir, start_date=start_date, end_date=end_date)
    feature_df = build_location_feature_table(pitch_df)
    diagnostics = build_location_feature_diagnostics(feature_df, pitch_df)
    warnings = []
    if pitch_df.empty:
        warnings.append("No pitch-level rows found for this pitcher/date range.")

    return AnalysisResponse(
        meta=ResponseMeta(year=year, warnings=warnings),
        summary=[
            MetricItem(key="source_pitches", label="Source Pitches", value=int(len(pitch_df))),
            MetricItem(key="feature_rows", label="Feature Rows", value=int(len(feature_df))),
            MetricItem(key="feature_columns", label="Feature Columns", value=len(LOCATION_FEATURE_COLUMNS)),
        ],
        tables={
            "location_features": dataframe_to_table_payload(feature_df),
            "feature_diagnostics": dataframe_to_table_payload(diagnostics),
        },
    )


def get_location_score(
    year: int,
    pitcher_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> AnalysisResponse:
    pitch_df = load_pitcher_cached_season(year=year, pitcher_id=pitcher_id, data_dir=settings.data_dir, start_date=start_date, end_date=end_date)
    feature_df = build_location_feature_table(pitch_df)
    score_df = build_prototype_location_scores(feature_df)
    diagnostics = build_location_feature_diagnostics(feature_df, pitch_df)
    warnings = ["Location+ score is a prototype proxy until trained model artifacts are connected."]
    if pitch_df.empty:
        warnings.append("No pitch-level rows found for this pitcher/date range.")

    return AnalysisResponse(
        meta=ResponseMeta(year=year, warnings=warnings),
        summary=[
            MetricItem(key="model_status", label="Model Status", value="prototype_proxy"),
            MetricItem(key="source_pitches", label="Source Pitches", value=int(len(pitch_df))),
            MetricItem(key="feature_rows", label="Feature Rows", value=int(len(score_df))),
        ],
        tables={
            "location_scores": dataframe_to_table_payload(score_df),
            "location_features": dataframe_to_table_payload(feature_df),
            "feature_diagnostics": dataframe_to_table_payload(diagnostics),
        },
    )
