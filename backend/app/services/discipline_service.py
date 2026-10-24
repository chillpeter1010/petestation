"""Reusable discipline calculations for starter, bullpen, and personal views."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

from app.api.schemas.common import TablePayload


SWING_EVENTS = {
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "foul_bunt",
    "hit_into_play",
    "hit_into_play_no_out",
    "hit_into_play_score",
    "missed_bunt",
}
WHIFF_EVENTS = {"swinging_strike", "swinging_strike_blocked", "foul_tip", "missed_bunt"}
CALLED_STRIKE_EVENTS = {"called_strike"}
IN_PLAY_EVENTS = {"hit_into_play", "hit_into_play_no_out", "hit_into_play_score"}
FOUL_EVENTS = {"foul", "foul_tip", "foul_bunt"}
BALL_EVENTS = {"ball", "blocked_ball", "ball_in_dirt", "hit_by_pitch", "pitchout"}
OUT_EVENTS = {
    "field_out",
    "force_out",
    "double_play",
    "triple_play",
    "grounded_into_double_play",
    "fielders_choice_out",
    "strikeout",
    "strikeout_double_play",
    "sac_bunt",
    "sac_fly",
    "sac_fly_double_play",
}
HIT_EVENTS = {"single", "double", "triple", "home_run"}
NON_AB_EVENTS = {"walk", "intent_walk", "hit_by_pitch", "sac_fly", "sac_bunt", "sac_fly_double_play", "catcher_interf"}

RESULT_PANEL_SPECS = [
    ("called_strike", "Called Strike"),
    ("swing_strike", "Swing Strike"),
    ("in_play", "In-Play"),
    ("foul_ball", "Foul"),
]
PA_RESULT_PANEL_SPECS = [
    ("pa_out", "Out"),
    ("pa_hit", "Hit"),
    ("pa_home_run", "Home Run"),
    ("pa_strikeout", "Strikeout"),
]
BBTYPE_PANEL_SPECS = [
    ("ground_ball", "Ground Ball"),
    ("fly_ball", "Fly Ball"),
    ("line_drive", "Line Drive"),
    ("popup", "Popup"),
]
COUNT_PANEL_SPECS = [
    ("count_0_0", "0-0"),
    ("count_batter_ahead", "Hitter Ahead"),
    ("count_pitcher_ahead", "Pitcher Ahead"),
    ("count_two_strikes", "Two Strikes"),
]
COUNT_SWING_PANEL_SPECS = [
    ("count_0_0", "0-0 Swings"),
    ("count_batter_ahead", "Hitter Ahead Swings"),
    ("count_pitcher_ahead", "Pitcher Ahead Swings"),
    ("count_two_strikes", "Two-Strike Swings"),
]
EXACT_COUNT_SPECS = [
    ("count_0_0", "0-0"),
    ("count_1_0", "1-0"),
    ("count_2_0", "2-0"),
    ("count_3_0", "3-0"),
    ("count_0_1", "0-1"),
    ("count_1_1", "1-1"),
    ("count_2_1", "2-1"),
    ("count_3_1", "3-1"),
    ("count_0_2", "0-2"),
    ("count_1_2", "1-2"),
    ("count_2_2", "2-2"),
    ("count_3_2", "3-2"),
]

LocationPayloadBuilder = Callable[[pd.DataFrame], list[dict[str, Any]]]

STRIKE_ZONE_X_MIN = -0.83
STRIKE_ZONE_X_MAX = 0.83
STRIKE_ZONE_Z_MIN = 1.5
STRIKE_ZONE_Z_MAX = 3.5
MEATBALL_X_MAX = 0.83 / 3.0
MEATBALL_Z_NORM_MIN = 1.0 / 3.0
MEATBALL_Z_NORM_MAX = 2.0 / 3.0


def clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def dataframe_to_table_payload(df: pd.DataFrame) -> TablePayload:
    if df.empty:
        return TablePayload()
    rows = [{key: clean_value(value) for key, value in row.items()} for row in df.to_dict(orient="records")]
    columns = [{"key": column, "label": column} for column in df.columns]
    return TablePayload(columns=columns, rows=rows)


def normalize_text_series(data: pd.DataFrame, column: str) -> pd.Series:
    return data.get(column, pd.Series(index=data.index, dtype="object")).fillna("").astype(str).str.lower().str.strip()


def numeric_series(data: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(data.get(column, pd.Series(index=data.index, dtype="float")), errors="coerce")


def red_strike_zone_mask(data: pd.DataFrame) -> pd.Series:
    """Use the visual red strike-zone box when plate coordinates are available."""
    zone_num = numeric_series(data, "zone")
    fallback = zone_num.between(1, 9)
    plate_x = numeric_series(data, "plate_x")
    plate_z = numeric_series(data, "plate_z")
    has_coordinates = plate_x.notna() & plate_z.notna()
    geometric = (
        plate_x.between(STRIKE_ZONE_X_MIN, STRIKE_ZONE_X_MAX)
        & plate_z.between(STRIKE_ZONE_Z_MIN, STRIKE_ZONE_Z_MAX)
    )
    return geometric.where(has_coordinates, fallback).fillna(False)


def meatball_zone_mask(data: pd.DataFrame) -> pd.Series:
    """Return the Savant-compatible middle-middle (zone 5) miss proxy.

    Statcast's zone 5 is the primary source so the aggregate rate stays
    comparable with Baseball Savant Meatball%.  When ``zone`` is unavailable,
    fall back to the horizontal and vertical middle thirds of that batter's
    recorded strike zone.  This describes observed location, not intended
    target, so callers must not present it as a verified command miss.
    """

    zone_num = numeric_series(data, "zone")
    has_zone = zone_num.notna()
    plate_x = numeric_series(data, "plate_x")
    plate_z = numeric_series(data, "plate_z")
    sz_top = numeric_series(data, "sz_top")
    sz_bot = numeric_series(data, "sz_bot")
    zone_height = (sz_top - sz_bot).where((sz_top - sz_bot) > 0)
    plate_z_norm = (plate_z - sz_bot) / zone_height
    coordinate_middle = (
        plate_x.abs().le(MEATBALL_X_MAX)
        & plate_z_norm.between(MEATBALL_Z_NORM_MIN, MEATBALL_Z_NORM_MAX)
    )
    return zone_num.eq(5).where(has_zone, coordinate_middle).fillna(False)


def add_discipline_flags(data: pd.DataFrame) -> pd.DataFrame:
    working = data.copy()
    description = normalize_text_series(working, "description")
    events = normalize_text_series(working, "events")
    zone_num = numeric_series(working, "zone")
    plate_x = numeric_series(working, "plate_x")
    plate_z = numeric_series(working, "plate_z")
    has_location = (plate_x.notna() & plate_z.notna()) | zone_num.notna()
    swings = description.isin(SWING_EVENTS)
    contact = description.isin(FOUL_EVENTS | IN_PLAY_EVENTS)

    working["_description_norm"] = description
    working["_events_norm"] = events
    working["_zone_num"] = zone_num
    working["_is_strike"] = description.isin(CALLED_STRIKE_EVENTS | WHIFF_EVENTS | FOUL_EVENTS | IN_PLAY_EVENTS)
    working["_is_swing"] = swings
    working["_is_contact"] = contact
    working["_is_whiff"] = description.isin(WHIFF_EVENTS)
    working["_is_called_strike"] = description.isin(CALLED_STRIKE_EVENTS)
    working["_is_swstr"] = description.isin({"swinging_strike", "swinging_strike_blocked", "missed_bunt"})
    working["_in_zone"] = red_strike_zone_mask(working)
    working["_out_zone"] = has_location & ~working["_in_zone"]
    working["_edge_zone"] = zone_num.isin([2, 4, 6, 8, 11, 12, 13, 14, 16, 17, 18, 19])
    working["_heart_zone"] = zone_num.isin([1, 3, 5, 7, 9])
    working["_meatball_zone"] = meatball_zone_mask(working)
    working["_first_pitch"] = numeric_series(working, "pitch_number").eq(1)
    return working


def summarize_discipline_group(group: pd.DataFrame, label: str, pitcher: str = "", team: str = "") -> dict[str, Any]:
    pitch_count = len(group)
    swing_mask = group["_is_swing"] if "_is_swing" in group else pd.Series(dtype="bool")
    contact_mask = group["_is_contact"] if "_is_contact" in group else pd.Series(dtype="bool")
    in_zone_mask = group["_in_zone"] if "_in_zone" in group else pd.Series(dtype="bool")
    out_zone_mask = group["_out_zone"] if "_out_zone" in group else pd.Series(dtype="bool")
    first_pitch_mask = group["_first_pitch"] if "_first_pitch" in group else pd.Series(dtype="bool")

    return {
        "Pitcher": pitcher,
        "Team": team,
        "Pitch": label,
        "Pitches": pitch_count,
        "Strike%": group["_is_strike"].mean() * 100 if pitch_count else np.nan,
        "Zone%": in_zone_mask.mean() * 100 if pitch_count else np.nan,
        "Swing%": swing_mask.mean() * 100 if pitch_count else np.nan,
        "Contact%": (contact_mask.sum() / swing_mask.sum() * 100) if swing_mask.sum() else np.nan,
        "Z-Swing%": (swing_mask[in_zone_mask].sum() / in_zone_mask.sum() * 100) if in_zone_mask.sum() else np.nan,
        "Z-Contact%": (contact_mask[in_zone_mask].sum() / swing_mask[in_zone_mask].sum() * 100) if swing_mask[in_zone_mask].sum() else np.nan,
        "O-Swing%": (swing_mask[out_zone_mask].sum() / out_zone_mask.sum() * 100) if out_zone_mask.sum() else np.nan,
        "O-Contact%": (contact_mask[out_zone_mask].sum() / swing_mask[out_zone_mask].sum() * 100) if swing_mask[out_zone_mask].sum() else np.nan,
        "Whiff%": (group["_is_whiff"].sum() / swing_mask.sum() * 100) if swing_mask.sum() else np.nan,
        "Edge%": group["_edge_zone"].mean() * 100 if pitch_count else np.nan,
        "1st Strike%": group.loc[first_pitch_mask, "_is_strike"].mean() * 100 if first_pitch_mask.sum() else np.nan,
        "Meatball%": group["_meatball_zone"].mean() * 100 if pitch_count else np.nan,
        "CStr%": group["_is_called_strike"].mean() * 100 if pitch_count else np.nan,
        "SwStr%": group["_is_swstr"].mean() * 100 if pitch_count else np.nan,
        "CSW%": (group["_is_called_strike"] | group["_is_whiff"]).mean() * 100 if pitch_count else np.nan,
    }


def build_pitcher_discipline_table(data: pd.DataFrame, player_name: str = "", team: str = "") -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()

    working = add_discipline_flags(data)
    rows = [summarize_discipline_group(working, "Overall", player_name, team)]
    if "pitch_name" in working.columns:
        for pitch_name in working["pitch_name"].dropna().astype(str).value_counts().index.tolist():
            pitch_group = working[working["pitch_name"].astype(str).eq(pitch_name)].copy()
            rows.append(summarize_discipline_group(pitch_group, pitch_name, player_name, team))
    return pd.DataFrame(rows)


def build_pitcher_panel_metrics(data: pd.DataFrame) -> list[dict[str, Any]]:
    if data.empty:
        return [
            {"label": "Str%", "value": None},
            {"label": "Zone%", "value": None},
            {"label": "Swing%", "value": None},
            {"label": "O-Swing%", "value": None},
            {"label": "Whiff%", "value": None},
            {"label": "AVG", "value": None},
        ]

    working = add_discipline_flags(data)
    events = working["_events_norm"]
    swings = working["_is_swing"]
    whiffs = working["_is_whiff"]
    strikes = working["_is_strike"]
    out_zone = working["_out_zone"]
    hits = events.isin(HIT_EVENTS)
    ab_mask = events.ne("") & ~events.isin(NON_AB_EVENTS)
    ab_count = int(ab_mask.sum())
    return [
        {"label": "Str%", "value": clean_value(strikes.mean() * 100 if len(working) else np.nan), "unit": "%"},
        {"label": "Zone%", "value": clean_value(working["_in_zone"].mean() * 100 if len(working) else np.nan), "unit": "%"},
        {"label": "Swing%", "value": clean_value(swings.mean() * 100 if len(working) else np.nan), "unit": "%"},
        {"label": "O-Swing%", "value": clean_value(swings[out_zone].sum() / out_zone.sum() * 100 if out_zone.sum() else np.nan), "unit": "%"},
        {"label": "Whiff%", "value": clean_value(whiffs.sum() / swings.sum() * 100 if swings.sum() else np.nan), "unit": "%"},
        {"label": "AVG", "value": clean_value(hits[ab_mask].sum() / ab_count if ab_count else np.nan)},
    ]


def build_pitch_mix(data: pd.DataFrame) -> list[dict[str, Any]]:
    if data.empty or "pitch_name" not in data.columns:
        return []
    counts = data["pitch_name"].dropna().astype(str).value_counts().rename_axis("pitch").reset_index(name="pitches")
    total = int(counts["pitches"].sum())
    counts["rate"] = counts["pitches"] / total if total else 0
    return [{key: clean_value(value) for key, value in row.items()} for row in counts.to_dict(orient="records")]


def build_panel_payload(data: pd.DataFrame, location_builder: LocationPayloadBuilder) -> dict[str, Any]:
    return {
        "rows": location_builder(data),
        "metrics": build_pitcher_panel_metrics(data),
        "pitch_mix": build_pitch_mix(data),
        "pitches": int(len(data)),
    }


def frames_to_panel_payloads(
    specs: list[tuple[str, str]],
    frames: dict[str, pd.DataFrame],
    location_builder: LocationPayloadBuilder,
) -> list[dict[str, Any]]:
    return [
        {"key": key, "label": label, **build_panel_payload(frames.get(key, pd.DataFrame()), location_builder)}
        for key, label in specs
    ]


def build_result_panel_frames(data: pd.DataFrame) -> dict[str, pd.DataFrame]:
    description = normalize_text_series(data, "description")
    return {
        "called_strike": data[description.isin(CALLED_STRIKE_EVENTS)].copy(),
        "swing_strike": data[description.isin(WHIFF_EVENTS)].copy(),
        "in_play": data[description.isin(IN_PLAY_EVENTS)].copy(),
        "foul_ball": data[description.isin(FOUL_EVENTS)].copy(),
    }


def build_pa_result_frames(data: pd.DataFrame) -> dict[str, pd.DataFrame]:
    events = normalize_text_series(data, "events")
    return {
        "pa_out": data[events.isin(OUT_EVENTS)].copy(),
        "pa_hit": data[events.isin(HIT_EVENTS)].copy(),
        "pa_home_run": data[events.eq("home_run")].copy(),
        "pa_strikeout": data[events.isin({"strikeout", "strikeout_double_play"})].copy(),
    }


def build_batted_ball_type_frames(data: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if "bb_type" not in data.columns:
        return {key: pd.DataFrame() for key, _ in BBTYPE_PANEL_SPECS}
    bb_type = data["bb_type"].fillna("").astype(str).str.lower().str.strip()
    return {
        "ground_ball": data[bb_type.eq("ground_ball")].copy(),
        "fly_ball": data[bb_type.eq("fly_ball")].copy(),
        "line_drive": data[bb_type.eq("line_drive")].copy(),
        "popup": data[bb_type.eq("popup")].copy(),
    }


def build_count_situation_frames(data: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if data.empty or not {"balls", "strikes"}.issubset(data.columns):
        return {key: pd.DataFrame() for key, _ in COUNT_PANEL_SPECS}
    working = data.copy()
    working["balls"] = pd.to_numeric(working["balls"], errors="coerce")
    working["strikes"] = pd.to_numeric(working["strikes"], errors="coerce")
    working = working.dropna(subset=["balls", "strikes"]).copy()
    return {
        "count_0_0": working[working["balls"].eq(0) & working["strikes"].eq(0)].copy(),
        "count_batter_ahead": working[working["balls"] > working["strikes"]].copy(),
        "count_pitcher_ahead": working[working["strikes"] > working["balls"]].copy(),
        "count_two_strikes": working[working["strikes"].eq(2)].copy(),
    }


def build_count_swing_frames(data: pd.DataFrame) -> dict[str, pd.DataFrame]:
    description = normalize_text_series(data, "description")
    return build_count_situation_frames(data[description.isin(SWING_EVENTS)].copy())


def build_exact_count_frames(data: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if data.empty or not {"balls", "strikes"}.issubset(data.columns):
        return {key: pd.DataFrame() for key, _ in EXACT_COUNT_SPECS}
    working = data.copy()
    working["balls"] = pd.to_numeric(working["balls"], errors="coerce")
    working["strikes"] = pd.to_numeric(working["strikes"], errors="coerce")
    working = working.dropna(subset=["balls", "strikes"]).copy()
    frames: dict[str, pd.DataFrame] = {}
    for key, _ in EXACT_COUNT_SPECS:
        _, balls_text, strikes_text = key.split("_")
        frames[key] = working[working["balls"].eq(int(balls_text)) & working["strikes"].eq(int(strikes_text))].copy()
    return frames


def build_discipline_panel_groups(data: pd.DataFrame, location_builder: LocationPayloadBuilder) -> dict[str, Any]:
    return {
        "result": {
            "pitch_result": frames_to_panel_payloads(RESULT_PANEL_SPECS, build_result_panel_frames(data), location_builder),
            "pa_result": frames_to_panel_payloads(PA_RESULT_PANEL_SPECS, build_pa_result_frames(data), location_builder),
            "batted_ball": frames_to_panel_payloads(BBTYPE_PANEL_SPECS, build_batted_ball_type_frames(data), location_builder),
        },
        "discipline": {
            "count_situation": frames_to_panel_payloads(COUNT_PANEL_SPECS, build_count_situation_frames(data), location_builder),
            "count_swing": frames_to_panel_payloads(COUNT_SWING_PANEL_SPECS, build_count_swing_frames(data), location_builder),
        },
        "situation": {
            "exact_count": frames_to_panel_payloads(EXACT_COUNT_SPECS, build_exact_count_frames(data), location_builder),
        },
    }


def build_starter_style_discipline_payload(
    data: pd.DataFrame,
    location_builder: LocationPayloadBuilder,
    player_name: str = "",
    team: str = "",
) -> dict[str, Any]:
    discipline_table = build_pitcher_discipline_table(data, player_name=player_name, team=team)
    return {
        "tables": {
            "pitcher_discipline": dataframe_to_table_payload(discipline_table),
        },
        "charts": {
            "panel_groups": build_discipline_panel_groups(data, location_builder),
        },
    }
