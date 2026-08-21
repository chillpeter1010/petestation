from __future__ import annotations

import sqlite3
from contextlib import closing
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.api.schemas.batter_stuff_attack import (
    StuffAttackCurvePoint,
    StuffAttackFilters,
    StuffAttackLeaderboardRow,
    StuffAttackMetricSet,
    StuffAttackResponse,
)
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.batter_service import list_batter_leaderboard
from app.services.pitch_stuff_cache_service import cache_path

PITCH_GROUPS = {
    "fastballs": ("FF", "SI"),
    "all_fastballs": ("FF", "SI", "FC"),
    "four_seam": ("FF",),
    "sinker": ("SI",),
    "cutter": ("FC",),
}
PITCH_GROUP_OPTIONS = [
    {"value": "fastballs", "label": "Four-Seam + Sinker"},
    {"value": "four_seam", "label": "Four-Seam"},
    {"value": "sinker", "label": "Sinker"},
    {"value": "cutter", "label": "Cutter"},
    {"value": "all_fastballs", "label": "All fastballs"},
]
PITCH_TYPE_GROUPS = [
    {"key": "fastball", "label": "Fastball", "options": [
        {"value": "FF", "label": "Four-Seam Fastball"},
        {"value": "SI", "label": "Sinker"},
        {"value": "FC", "label": "Cutter"},
    ]},
    {"key": "breaking", "label": "Breaking Ball", "options": [
        {"value": "SL", "label": "Slider"},
        {"value": "ST", "label": "Sweeper"},
        {"value": "CU", "label": "Curveball"},
        {"value": "KC", "label": "Knuckle Curve"},
        {"value": "SV", "label": "Slurve"},
    ]},
    {"key": "offspeed", "label": "Offspeed", "options": [
        {"value": "CH", "label": "Changeup"},
        {"value": "FS", "label": "Split-Finger"},
        {"value": "FO", "label": "Forkball"},
    ]},
    {"key": "specialty", "label": "Specialty", "options": [
        {"value": "KN", "label": "Knuckleball"},
        {"value": "EP", "label": "Eephus"},
        {"value": "CS", "label": "Slow Curve"},
    ]},
]
ALLOWED_PITCH_TYPES = {
    option["value"]
    for group in PITCH_TYPE_GROUPS
    for option in group["options"]
}
STUFF_BINS = {
    "lt95": (None, 95.0, "< 95"),
    "95_104": (95.0, 105.0, "95–104"),
    "105_114": (105.0, 115.0, "105–114"),
    "115_plus": (115.0, None, ">= 115"),
}
STUFF_BIN_OPTIONS = [{"value": key, "label": values[2]} for key, values in STUFF_BINS.items()]
SWING_DESCRIPTIONS = {
    "swinging_strike", "swinging_strike_blocked", "foul", "foul_tip",
    "hit_into_play", "foul_bunt", "missed_bunt",
}
WHIFF_DESCRIPTIONS = {"swinging_strike", "swinging_strike_blocked", "missed_bunt"}
CONTEXT_COLUMNS = ["pitch_type", "balls", "strikes", "stand", "p_throws", "_x_region", "_z_region"]
AXIS_OPTIONS = [
    {"key": "adjusted_swing_pct", "label": "Adjusted Swing%", "unit": "%", "population": "Pitches seen", "description": "Swing rate recentered for pitch context."},
    {"key": "swing_pct", "label": "Swing%", "unit": "%", "population": "Pitches seen", "description": "Swings divided by pitches seen."},
    {"key": "chase_pct", "label": "Chase%", "unit": "%", "population": "Pitches outside zone", "description": "Swings at pitches outside the rule-book zone."},
    {"key": "adjusted_contact_pct", "label": "Adjusted Contact%", "unit": "%", "population": "Swings", "description": "Contact rate recentered for pitch context."},
    {"key": "contact_pct", "label": "Contact%", "unit": "%", "population": "Swings", "description": "Contact divided by swings."},
    {"key": "whiff_pct", "label": "Whiff%", "unit": "%", "population": "Swings", "description": "Swinging misses divided by swings."},
    {"key": "adjusted_rv_per_100_swings", "label": "Adjusted RV / 100 swings", "unit": "RV", "population": "Swings", "description": "Run value per 100 swings recentered for pitch context."},
    {"key": "rv_per_100_swings", "label": "RV / 100 swings", "unit": "RV", "population": "Swings", "description": "Batter run value per 100 swings."},
    {"key": "avg_bat_speed", "label": "Avg Bat Speed", "unit": "mph", "population": "Competitive swings", "description": "Average sweet-spot speed over competitive swings."},
    {"key": "fast_swing_pct", "label": "Fast Swing Rate", "unit": "%", "population": "Competitive swings", "description": "Competitive swings at 75 mph or faster."},
    {"key": "avg_swing_length", "label": "Avg Swing Length", "unit": "ft", "population": "Tracked swings", "description": "Average distance traveled by the bat head."},
    {"key": "avg_attack_angle", "label": "Avg Attack Angle", "unit": "deg", "population": "Tracked swings", "description": "Vertical bat direction at impact or closest approach."},
    {"key": "ideal_attack_angle_pct", "label": "Ideal Attack Angle Rate", "unit": "%", "population": "Tracked swings", "description": "Tracked swings with attack angle from 5 to 20 degrees."},
    {"key": "avg_swing_path_tilt", "label": "Avg Swing Path Tilt", "unit": "deg", "population": "Tracked swings", "description": "Average angular orientation of the swing plane."},
    {"key": "avg_exit_velocity", "label": "Avg Exit Velocity", "unit": "mph", "population": "Fair batted balls", "description": "Average launch speed on fair batted balls."},
    {"key": "hard_hit_pct", "label": "Hard-Hit Rate", "unit": "%", "population": "Fair batted balls", "description": "Fair batted balls at 95 mph or faster."},
    {"key": "barrel_pct", "label": "Barrel Rate", "unit": "%", "population": "Fair batted balls", "description": "Barrels divided by fair batted balls."},
    {"key": "xwoba_contact", "label": "xwOBA on Contact", "unit": "rate", "population": "Fair batted balls", "description": "Expected wOBA on fair contact."},
    {"key": "avg_launch_angle", "label": "Avg Launch Angle", "unit": "deg", "population": "Fair batted balls", "description": "Average vertical launch angle."},
    {"key": "avg_miss_distance", "label": "Avg Miss Distance", "unit": "in", "population": "Tracked whiffs", "description": "Average closest bat-to-ball distance on swinging misses."},
]


def get_batter_stuff_attack(
    year: int = 2026,
    pitch_group: str = "fastballs",
    pitch_types: tuple[str, ...] | None = None,
    pitcher_hand: str = "All",
    stuff_bin: str = "115_plus",
    minimum_pitches: int = 50,
    batter_id: int | None = None,
) -> StuffAttackResponse:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    score_path = cache_path(settings.data_dir)
    available_years = _available_score_years(score_path)
    filters = StuffAttackFilters(
        available_years=available_years,
        pitch_groups=PITCH_GROUP_OPTIONS,
        pitch_type_groups=PITCH_TYPE_GROUPS,
        stuff_bins=STUFF_BIN_OPTIONS,
        axis_options=AXIS_OPTIONS,
    )
    if not db_path.exists() or not score_path.exists() or year not in available_years:
        return StuffAttackResponse(
            year=year,
            pitch_group=pitch_group,
            selected_pitch_types=_resolve_pitch_types(pitch_group, pitch_types),
            pitcher_hand=_resolve_pitcher_hand(pitcher_hand),
            stuff_bin=stuff_bin,
            minimum_pitches=minimum_pitches,
            filters=filters,
            warnings=[f"Per-pitch Stuff+ is not available for {year}."],
        )

    joined = _load_joined_rows(year, db_path.stat().st_mtime_ns, score_path.stat().st_mtime_ns)
    identities = {
        int(row["player_id"]): (str(row["name"]), str(row["team"]))
        for row in list_batter_leaderboard(year)
    }
    return build_stuff_attack_response(
        joined,
        identities=identities,
        year=year,
        pitch_group=pitch_group,
        pitch_types=pitch_types,
        pitcher_hand=pitcher_hand,
        stuff_bin=stuff_bin,
        minimum_pitches=max(0, minimum_pitches),
        batter_id=batter_id,
        filters=filters,
    )


def build_stuff_attack_response(
    data: pd.DataFrame,
    identities: dict[int, tuple[str, str]],
    year: int,
    pitch_group: str = "fastballs",
    pitch_types: tuple[str, ...] | None = None,
    pitcher_hand: str = "All",
    stuff_bin: str = "115_plus",
    minimum_pitches: int = 50,
    batter_id: int | None = None,
    filters: StuffAttackFilters | None = None,
) -> StuffAttackResponse:
    group_key = pitch_group if pitch_group in PITCH_GROUPS else "fastballs"
    selected_pitch_types = _resolve_pitch_types(group_key, pitch_types)
    selected_hand = _resolve_pitcher_hand(pitcher_hand)
    bin_key = stuff_bin if stuff_bin in STUFF_BINS else "115_plus"
    family = data[data["pitch_type"].isin(selected_pitch_types)].copy()
    if selected_hand != "All":
        family = family[family["p_throws"].fillna("").astype(str).str.upper().eq(selected_hand)].copy()
    matched = _select_stuff_bin(family, bin_key)
    prepared = _add_metric_flags(matched)
    league = _metric_set(prepared)
    league_axis_metrics = _axis_metrics(prepared, league)
    rows = _aggregate_batters(prepared, identities)
    qualifying = [row for row in rows if row.pitches_seen >= minimum_pitches]
    qualifying.sort(
        key=lambda row: (
            row.adjusted_rv_per_100_swings is not None,
            row.adjusted_rv_per_100_swings or -999.0,
            row.pitches_seen,
        ),
        reverse=True,
    )
    selected = next((row for row in rows if row.batter_id == batter_id), None)
    curve = _build_response_curve(family, batter_id) if batter_id is not None else []
    total_source = int(data.attrs.get("source_rows", len(data)))
    scored_source = int(data.attrs.get("scored_rows", data["pitch_stuff_plus"].notna().sum()))
    return StuffAttackResponse(
        year=year,
        data_updated_at=str(pd.to_datetime(data["game_date"], errors="coerce").max())[:10] if not data.empty else None,
        pitch_group=group_key,
        selected_pitch_types=list(selected_pitch_types),
        pitcher_hand=selected_hand,
        stuff_bin=bin_key,
        minimum_pitches=minimum_pitches,
        matched_pitches=len(prepared),
        matched_batters=int(prepared["batter"].nunique()) if not prepared.empty else 0,
        qualifying_batters=len(qualifying),
        join_coverage_pct=round(scored_source / total_source * 100, 2) if total_source else None,
        league=league,
        league_axis_metrics=league_axis_metrics,
        leaderboard=qualifying,
        selected_batter=selected,
        response_curve=curve,
        filters=filters or StuffAttackFilters(pitch_groups=PITCH_GROUP_OPTIONS, pitch_type_groups=PITCH_TYPE_GROUPS, stuff_bins=STUFF_BIN_OPTIONS, axis_options=AXIS_OPTIONS),
    )


def _resolve_pitch_types(pitch_group: str, pitch_types: tuple[str, ...] | None) -> tuple[str, ...]:
    if pitch_types:
        selected = tuple(dict.fromkeys(value.upper() for value in pitch_types if value.upper() in ALLOWED_PITCH_TYPES))
        if selected:
            return selected
    return PITCH_GROUPS.get(pitch_group, PITCH_GROUPS["fastballs"])


def _resolve_pitcher_hand(value: str) -> str:
    normalized = str(value or "All").upper()
    return normalized if normalized in {"L", "R"} else "All"


@lru_cache(maxsize=4)
def _load_joined_rows(year: int, _db_mtime: int, _score_mtime: int) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    score_path = cache_path(settings.data_dir)
    with duckdb.connect(str(db_path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        table = resolve_pitch_table(tables)
        pitches = connection.execute(
            f"""
            SELECT game_pk, at_bat_number, pitch_number, pitcher, batter, game_date,
                   pitch_type, description, balls, strikes, plate_x, plate_z,
                   sz_top, sz_bot, stand, p_throws, launch_speed, launch_angle,
                   launch_speed_angle, estimated_woba_using_speedangle, delta_run_exp,
                   bat_speed, swing_length, attack_angle, attack_direction,
                   swing_path_tilt, intercept_ball_minus_batter_pos_x_inches,
                   intercept_ball_minus_batter_pos_y_inches, hyper_speed, miss_distance
            FROM {table}
            WHERE game_type = 'R' AND batter IS NOT NULL
            """
        ).fetchdf()
    with closing(sqlite3.connect(score_path, timeout=30)) as connection:
        version_row = connection.execute(
            """
            SELECT model_version
            FROM pitch_stuff_pitcher_state
            WHERE year = ?
            GROUP BY model_version
            ORDER BY MAX(calculated_at) DESC
            LIMIT 1
            """,
            [year],
        ).fetchone()
        if not version_row:
            return pd.DataFrame()
        scores = pd.read_sql_query(
            """
            SELECT game_pk, at_bat_number, pitch_number, pitcher, pitch_stuff_plus
            FROM pitch_stuff_scores
            WHERE year = ? AND model_version = ?
            """,
            connection,
            params=[year, version_row[0]],
        )
    keys = ["game_pk", "at_bat_number", "pitch_number", "pitcher"]
    joined = pitches.merge(scores, on=keys, how="left", validate="one_to_one")
    joined.attrs["source_rows"] = len(pitches)
    joined.attrs["scored_rows"] = int(joined["pitch_stuff_plus"].notna().sum())
    joined = _add_competitive_swing_flag(joined)
    return joined[joined["pitch_stuff_plus"].notna()].reset_index(drop=True)


def _available_score_years(path: Path) -> list[int]:
    if not path.exists():
        return []
    with closing(sqlite3.connect(path, timeout=30)) as connection:
        return [int(row[0]) for row in connection.execute("SELECT DISTINCT year FROM pitch_stuff_scores ORDER BY year DESC")]


def _select_stuff_bin(data: pd.DataFrame, key: str) -> pd.DataFrame:
    low, high, _ = STUFF_BINS[key]
    score = pd.to_numeric(data["pitch_stuff_plus"], errors="coerce")
    mask = score.notna()
    if low is not None:
        mask &= score.ge(low)
    if high is not None:
        mask &= score.lt(high)
    return data[mask].copy()


def _add_metric_flags(data: pd.DataFrame, include_expected: bool = True) -> pd.DataFrame:
    if data.empty:
        return data.copy()
    result = data.copy()
    description = result["description"].fillna("").astype(str).str.lower()
    result["_swing"] = description.isin(SWING_DESCRIPTIONS)
    result["_whiff"] = description.isin(WHIFF_DESCRIPTIONS)
    result["_contact"] = result["_swing"] & ~result["_whiff"]
    result["_bbe"] = description.eq("hit_into_play")
    result["_hard_hit"] = result["_bbe"] & pd.to_numeric(result["launch_speed"], errors="coerce").ge(95)
    result["_barrel"] = result["_bbe"] & pd.to_numeric(result["launch_speed_angle"], errors="coerce").eq(6)
    top = pd.to_numeric(result["sz_top"], errors="coerce")
    bottom = pd.to_numeric(result["sz_bot"], errors="coerce")
    plate_x = pd.to_numeric(result["plate_x"], errors="coerce")
    plate_z = pd.to_numeric(result["plate_z"], errors="coerce")
    valid_height = top.gt(bottom)
    result["_zone"] = plate_x.between(-0.83, 0.83) & plate_z.ge(bottom.where(valid_height, 1.5)) & plate_z.le(top.where(valid_height, 3.5))
    normalized_z = (plate_z - bottom.where(valid_height, 1.5)) / (top.where(valid_height, 3.5) - bottom.where(valid_height, 1.5))
    result["_x_region"] = pd.cut(plate_x, [-np.inf, -0.83, 0.83, np.inf], labels=False).fillna(-1)
    result["_z_region"] = pd.cut(normalized_z, [-np.inf, 0, 1, np.inf], labels=False).fillna(-1)
    result["_rv"] = pd.to_numeric(result["delta_run_exp"], errors="coerce")
    result["_xwoba_contact"] = pd.to_numeric(result["estimated_woba_using_speedangle"], errors="coerce").where(result["_bbe"])
    for column in ("bat_speed", "swing_length", "attack_angle", "attack_direction", "swing_path_tilt", "intercept_ball_minus_batter_pos_x_inches", "intercept_ball_minus_batter_pos_y_inches", "hyper_speed", "miss_distance", "launch_angle"):
        result[column] = pd.to_numeric(result[column], errors="coerce") if column in result else np.nan
    if "_competitive_swing" not in result:
        result = _add_competitive_swing_flag(result)
    result["_competitive_bat_speed"] = result["bat_speed"].where(result["_competitive_swing"])
    result["_fast_swing"] = result["_competitive_swing"] & result["bat_speed"].ge(75)
    result["_ideal_attack_angle"] = result["attack_angle"].between(5, 20).where(result["attack_angle"].notna())
    result["_miss_distance"] = result["miss_distance"].where(result["_whiff"])
    if include_expected:
        for column in CONTEXT_COLUMNS:
            result[column] = result[column].fillna("-")
        context = result.groupby(CONTEXT_COLUMNS, dropna=False)
        result["_expected_swing"] = context["_swing"].transform("mean")
        result["_expected_contact"] = result["_contact"].where(result["_swing"]).groupby([result[column] for column in CONTEXT_COLUMNS], dropna=False).transform("mean")
        result["_expected_rv"] = context["_rv"].transform("mean")
        result["_expected_swing_rv"] = result["_rv"].where(result["_swing"]).groupby([result[column] for column in CONTEXT_COLUMNS], dropna=False).transform("mean")
    return result


def _add_competitive_swing_flag(data: pd.DataFrame) -> pd.DataFrame:
    result = data.copy()
    if result.empty:
        result["_competitive_swing"] = pd.Series(dtype=bool)
        return result
    description = result["description"].fillna("").astype(str).str.lower()
    swing = description.isin(SWING_DESCRIPTIONS)
    bat_speed = pd.to_numeric(result["bat_speed"], errors="coerce") if "bat_speed" in result else pd.Series(np.nan, index=result.index)
    exit_velocity = pd.to_numeric(result["launch_speed"], errors="coerce") if "launch_speed" in result else pd.Series(np.nan, index=result.index)
    tracked = bat_speed.where(swing)
    threshold = tracked.groupby(result["batter"]).transform(lambda values: values.quantile(0.10))
    result["_competitive_swing"] = swing & bat_speed.notna() & (bat_speed.ge(threshold) | (bat_speed.ge(60) & exit_velocity.ge(90)))
    return result


def _aggregate_batters(data: pd.DataFrame, identities: dict[int, tuple[str, str]]) -> list[StuffAttackLeaderboardRow]:
    if data.empty:
        return []
    league_swing = data["_swing"].mean()
    league_contact = data.loc[data["_swing"], "_contact"].mean()
    league_rv = data["_rv"].mean()
    league_swing_rv = data.loc[data["_swing"], "_rv"].mean()
    grouped = data.groupby("batter", sort=False)
    aggregate = grouped.agg(
        pitches_seen=("batter", "size"),
        swings=("_swing", "sum"),
        batted_balls=("_bbe", "sum"),
        expected_swing=("_expected_swing", "mean"),
        rv_mean=("_rv", "mean"),
        expected_rv=("_expected_rv", "mean"),
    )
    swing_groups = data[data["_swing"]].groupby("batter", sort=False).agg(
        contacts=("_contact", "sum"),
        whiffs=("_whiff", "sum"),
        expected_contact=("_expected_contact", "mean"),
        swing_rv=("_rv", "mean"),
        expected_swing_rv=("_expected_swing_rv", "mean"),
    )
    bbe_groups = data[data["_bbe"]].groupby("batter", sort=False).agg(
        hard_hits=("_hard_hit", "sum"),
        barrels=("_barrel", "sum"),
        xwoba_contact=("_xwoba_contact", "mean"),
    )
    zone_groups = data[data["_zone"]].groupby("batter", sort=False)["_swing"].agg(["sum", "count"]).rename(columns={"sum": "zone_swings", "count": "zone_pitches"})
    chase_groups = data[~data["_zone"]].groupby("batter", sort=False)["_swing"].agg(["sum", "count"]).rename(columns={"sum": "chase_swings", "count": "chase_pitches"})
    aggregate = aggregate.join([swing_groups, bbe_groups, zone_groups, chase_groups])
    rows: list[StuffAttackLeaderboardRow] = []
    for batter, values in aggregate.iterrows():
        batter_id = int(batter)
        batter_data = grouped.get_group(batter)
        name, team = identities.get(batter_id, (f"Batter {batter_id}", "-"))
        pitches_seen = int(values["pitches_seen"])
        swings = int(values["swings"])
        batted_balls = int(values["batted_balls"])
        swing_rate = _divide(values["swings"], pitches_seen)
        contact_rate = _divide(values.get("contacts"), swings)
        swing_rv = _number(values.get("swing_rv"), 100)
        adjusted_swing = _number(swing_rate - values["expected_swing"] + league_swing, 100)
        adjusted_contact = _number(contact_rate - values.get("expected_contact") + league_contact, 100)
        adjusted_rv_seen = _number(values["rv_mean"] - values["expected_rv"] + league_rv, 100)
        adjusted_rv_swings = _number(values.get("swing_rv") - values.get("expected_swing_rv") + league_swing_rv, 100)
        base_metrics = StuffAttackMetricSet(
            pitches_seen=pitches_seen,
            swings=swings,
            batted_balls=batted_balls,
            swing_pct=_number(swing_rate, 100),
            zone_swing_pct=_number(_divide(values.get("zone_swings"), values.get("zone_pitches")), 100),
            chase_pct=_number(_divide(values.get("chase_swings"), values.get("chase_pitches")), 100),
            contact_pct=_number(contact_rate, 100),
            whiff_pct=_number(_divide(values.get("whiffs"), swings), 100),
            hard_hit_pct=_number(_divide(values.get("hard_hits"), batted_balls), 100),
            barrel_pct=_number(_divide(values.get("barrels"), batted_balls), 100),
            xwoba_contact=_number(values.get("xwoba_contact")),
            rv_per_100_seen=_number(values.get("rv_mean"), 100),
            rv_per_100_swings=swing_rv,
        )
        axis_metrics = _axis_metrics(batter_data, base_metrics)
        axis_metrics.update({
            "adjusted_swing_pct": adjusted_swing,
            "adjusted_contact_pct": adjusted_contact,
            "adjusted_rv_per_100_swings": adjusted_rv_swings,
        })
        rows.append(
            StuffAttackLeaderboardRow(
                batter_id=batter_id,
                name=name,
                team=team,
                **base_metrics.model_dump(),
                adjusted_swing_pct=adjusted_swing,
                adjusted_contact_pct=adjusted_contact,
                adjusted_rv_per_100_seen=adjusted_rv_seen,
                adjusted_rv_per_100_swings=adjusted_rv_swings,
                axis_metrics=axis_metrics,
                axis_samples=_axis_samples(batter_data),
                sample_status="Stable" if pitches_seen >= 100 else "Developing" if pitches_seen >= 50 else "Small sample",
            )
        )
    return rows


def _metric_set(data: pd.DataFrame) -> StuffAttackMetricSet:
    if data.empty:
        return StuffAttackMetricSet()
    swings = data[data["_swing"]]
    bbe = data[data["_bbe"]]
    zone = data[data["_zone"]]
    chase = data[~data["_zone"]]
    return StuffAttackMetricSet(
        pitches_seen=len(data),
        swings=len(swings),
        batted_balls=len(bbe),
        swing_pct=_rate(data["_swing"]),
        zone_swing_pct=_rate(zone["_swing"]),
        chase_pct=_rate(chase["_swing"]),
        contact_pct=_rate(swings["_contact"]),
        whiff_pct=_rate(swings["_whiff"]),
        hard_hit_pct=_rate(bbe["_hard_hit"]),
        barrel_pct=_rate(bbe["_barrel"]),
        xwoba_contact=_mean(bbe["_xwoba_contact"]),
        rv_per_100_seen=_mean(data["_rv"], 100),
        rv_per_100_swings=_mean(swings["_rv"], 100),
    )


def _axis_metrics(data: pd.DataFrame, metrics: StuffAttackMetricSet) -> dict[str, float | None]:
    swings = data[data["_swing"]]
    competitive = data[data["_competitive_swing"]]
    bbe = data[data["_bbe"]]
    whiffs = data[data["_whiff"]]
    values = {
        "adjusted_swing_pct": metrics.swing_pct,
        "swing_pct": metrics.swing_pct,
        "chase_pct": metrics.chase_pct,
        "adjusted_contact_pct": metrics.contact_pct,
        "contact_pct": metrics.contact_pct,
        "whiff_pct": metrics.whiff_pct,
        "adjusted_rv_per_100_swings": metrics.rv_per_100_swings,
        "rv_per_100_swings": metrics.rv_per_100_swings,
        "avg_bat_speed": _mean(competitive["bat_speed"]),
        "fast_swing_pct": _rate(competitive["_fast_swing"]),
        "avg_swing_length": _mean(swings["swing_length"]),
        "avg_attack_angle": _mean(swings["attack_angle"]),
        "ideal_attack_angle_pct": _rate(swings["_ideal_attack_angle"].dropna()),
        "avg_swing_path_tilt": _mean(swings["swing_path_tilt"]),
        "avg_exit_velocity": _mean(bbe["launch_speed"]),
        "hard_hit_pct": metrics.hard_hit_pct,
        "barrel_pct": metrics.barrel_pct,
        "xwoba_contact": metrics.xwoba_contact,
        "avg_launch_angle": _mean(bbe["launch_angle"]),
        "avg_miss_distance": _mean(whiffs["_miss_distance"]),
    }
    return values


def _axis_samples(data: pd.DataFrame) -> dict[str, int]:
    swings = data[data["_swing"]]
    bbe = data[data["_bbe"]]
    competitive = data[data["_competitive_swing"]]
    whiffs = data[data["_whiff"]]
    return {
        "adjusted_swing_pct": len(data), "swing_pct": len(data),
        "chase_pct": int((~data["_zone"]).sum()),
        "adjusted_contact_pct": len(swings), "contact_pct": len(swings), "whiff_pct": len(swings),
        "adjusted_rv_per_100_swings": len(swings), "rv_per_100_swings": len(swings),
        "avg_bat_speed": int(competitive["bat_speed"].notna().sum()), "fast_swing_pct": len(competitive),
        "avg_swing_length": int(swings["swing_length"].notna().sum()),
        "avg_attack_angle": int(swings["attack_angle"].notna().sum()),
        "ideal_attack_angle_pct": int(swings["attack_angle"].notna().sum()),
        "avg_swing_path_tilt": int(swings["swing_path_tilt"].notna().sum()),
        "avg_exit_velocity": int(bbe["launch_speed"].notna().sum()),
        "hard_hit_pct": len(bbe), "barrel_pct": len(bbe),
        "xwoba_contact": int(bbe["_xwoba_contact"].notna().sum()),
        "avg_launch_angle": int(bbe["launch_angle"].notna().sum()),
        "avg_miss_distance": int(whiffs["_miss_distance"].notna().sum()),
    }


def _build_response_curve(data: pd.DataFrame, batter_id: int) -> list[StuffAttackCurvePoint]:
    points: list[StuffAttackCurvePoint] = []
    prepared_family = _add_metric_flags(data, include_expected=False)
    for key, (_, _, label) in STUFF_BINS.items():
        prepared = _select_stuff_bin(prepared_family, key)
        batter = prepared[pd.to_numeric(prepared["batter"], errors="coerce").eq(batter_id)]
        metrics = _metric_set(batter)
        league = _metric_set(prepared)
        points.append(
            StuffAttackCurvePoint(
                key=key,
                label=label,
                **metrics.model_dump(),
                league_swing_pct=league.swing_pct,
                league_contact_pct=league.contact_pct,
                league_rv_per_100_seen=league.rv_per_100_seen,
            )
        )
    return points


def _rate(values: pd.Series) -> float | None:
    return _mean(values.astype(float), 100)


def _mean(values: pd.Series, multiplier: float = 1) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    return round(float(numeric.mean() * multiplier), 3) if not numeric.empty else None


def _divide(numerator: Any, denominator: Any) -> float:
    if pd.isna(numerator) or pd.isna(denominator) or float(denominator) == 0:
        return np.nan
    return float(numerator) / float(denominator)


def _number(value: Any, multiplier: float = 1) -> float | None:
    return None if value is None or pd.isna(value) else round(float(value) * multiplier, 3)


def _adjusted_rate(observed: pd.Series, expected: pd.Series, league: float) -> float | None:
    value = _adjusted_value(observed.astype(float), expected, league, 100)
    return value


def _adjusted_value(observed: pd.Series, expected: pd.Series, league: float, multiplier: float) -> float | None:
    paired = pd.DataFrame({"observed": observed, "expected": expected}).dropna()
    if paired.empty or pd.isna(league):
        return None
    return round(float((paired["observed"].mean() - paired["expected"].mean() + league) * multiplier), 3)
