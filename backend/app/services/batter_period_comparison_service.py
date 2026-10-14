from __future__ import annotations

from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.api.schemas.batter_period_comparison import (
    BatterPeriodComparisonResponse,
    BatterPeriodMetric,
    BatterPeriodOptionsResponse,
    BatterPeriodWindow,
)
from app.api.schemas.common import ResponseMeta
from app.core.config import settings
from app.repositories.pitch_repository import available_db_years, get_season_duckdb_path, resolve_pitch_table
from app.services.batter_service import list_batter_leaderboard, list_batter_options
from app.services.discipline_service import build_discipline_panel_groups

SWING_EVENTS = {
    "swinging_strike", "swinging_strike_blocked", "foul", "foul_tip",
    "hit_into_play", "foul_bunt", "missed_bunt", "bunt_foul_tip", "swinging_pitchout",
}
WHIFF_EVENTS = {"swinging_strike", "swinging_strike_blocked", "missed_bunt", "swinging_pitchout"}
BUNT_EVENTS = {"foul_bunt", "missed_bunt", "bunt_foul_tip"}
NON_AB_EVENTS = {
    "walk", "intent_walk", "hit_by_pitch", "sac_bunt", "sac_fly",
    "sac_fly_double_play", "catcher_interf", "truncated_pa",
}
HIT_EVENTS = {"single", "double", "triple", "home_run"}
OUT_EVENTS = {"field_out", "force_out", "double_play", "triple_play", "grounded_into_double_play", "fielders_choice_out", "sac_bunt", "sac_fly", "sac_fly_double_play"}
PITCH_FAMILIES = {
    "FF": "Fastball", "SI": "Fastball", "FC": "Fastball",
    "SL": "Breaking", "ST": "Breaking", "CU": "Breaking", "KC": "Breaking", "SV": "Breaking",
    "CH": "Offspeed", "FS": "Offspeed", "FO": "Offspeed",
}

PERIOD_PERCENTILE_SPECS = [
    ("xwoba", "xwOBA", "rate", True, "xwoba", 1.0),
    ("avg_ev", "Avg Exit Velo", "mph", True, "avg_ev", 1.0),
    ("barrel_pct", "Barrel%", "percent", True, "barrel_rate", 0.01),
    ("hard_hit_pct", "Hard-Hit%", "percent", True, "hard_hit_rate", 0.01),
    ("sweet_spot_pct", "LA Sweet-Spot%", "percent", True, "sweet_spot_rate", 0.01),
    ("avg_bat_speed", "Bat Speed", "mph", True, "avg_bat_speed", 1.0),
    ("chase_pct", "Chase%", "percent", False, "chase_rate", 0.01),
    ("whiff_pct", "Whiff%", "percent", False, "whiff_rate", 0.01),
    ("k_pct", "K%", "percent", False, "strikeout_rate", 0.01),
    ("bb_pct", "BB%", "percent", True, "walk_rate", 0.01),
]


def get_batter_period_options(year: int) -> BatterPeriodOptionsResponse:
    return BatterPeriodOptionsResponse(
        meta=ResponseMeta(year=year),
        years=available_db_years(settings.data_dir),
        batters=list_batter_options(year),
    )


def get_batter_period_date_range(year: int, batter_id: int) -> dict[str, Any]:
    rows = load_batter_period_rows(year, batter_id)
    dates = pd.to_datetime(rows.get("game_date"), errors="coerce").dropna() if not rows.empty else pd.Series(dtype="datetime64[ns]")
    team_stints = build_batter_team_stints(rows)
    return {
        "year": year,
        "batter_id": batter_id,
        "start_date": dates.min().strftime("%Y-%m-%d") if not dates.empty else None,
        "end_date": dates.max().strftime("%Y-%m-%d") if not dates.empty else None,
        "pitches": int(len(rows)),
        "current_team": team_stints[-1]["team"] if team_stints else None,
        "transfer_count": max(0, len(team_stints) - 1),
        "team_stints": team_stints,
    }


def build_batter_team_stints(rows: pd.DataFrame) -> list[dict[str, Any]]:
    if rows.empty or "game_date" not in rows or "game_pk" not in rows:
        return []
    working = rows.copy()
    batter_team = working.get("batter_team", pd.Series("", index=working.index)).fillna("").astype(str).str.strip().str.upper()
    offense_team = working.get("offense_team", pd.Series("", index=working.index)).fillna("").astype(str).str.strip().str.upper()
    working["team"] = batter_team.where(batter_team.ne(""), offense_team)
    working = working.loc[working["team"].ne("") & working["game_date"].notna()].copy()
    if working.empty:
        return []
    games = (
        working.groupby(["game_pk", "game_date", "team"], as_index=False)
        .size()
        .rename(columns={"size": "pitches"})
        .sort_values(["game_date", "game_pk"])
    )
    stints: list[dict[str, Any]] = []
    for row in games.itertuples(index=False):
        team = str(row.team)
        game_date = str(row.game_date)[:10]
        if not stints or stints[-1]["team"] != team:
            stints.append(
                {
                    "stint_index": len(stints),
                    "team": team,
                    "start_date": game_date,
                    "end_date": game_date,
                    "pitches": int(row.pitches),
                    "games": 1,
                }
            )
        else:
            stints[-1]["end_date"] = game_date
            stints[-1]["pitches"] += int(row.pitches)
            stints[-1]["games"] += 1
    for stint in stints:
        stint["label"] = (
            f"{stint['team']} · {stint['start_date']} to {stint['end_date']} · "
            f"{stint['games']} G · {stint['pitches']} pitches"
        )
    return stints


def load_batter_period_rows(year: int, batter_id: int) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return pd.DataFrame()
    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = resolve_pitch_table(tables)
        if not source_table:
            return pd.DataFrame()
        rows = conn.execute(
            f"SELECT * FROM {source_table} WHERE game_type = 'R' AND batter = ?",
            [batter_id],
        ).fetchdf()
    return normalize_batter_period_rows(rows)


def normalize_batter_period_rows(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows.copy()
    result = rows.copy()
    text_columns = ["events", "description", "stand", "p_throws", "pitch_type", "pitch_name", "bb_type", "batter_team", "offense_team"]
    for column in text_columns:
        if column not in result:
            result[column] = ""
        result[column] = result[column].fillna("").astype(str).str.strip()
    result["events"] = result["events"].str.lower()
    result["description"] = result["description"].str.lower()
    result["pitch_name"] = result["pitch_name"].where(result["pitch_name"].ne(""), result["pitch_type"])
    result["game_date"] = pd.to_datetime(result.get("game_date"), errors="coerce").dt.strftime("%Y-%m-%d")
    numeric_columns = [
        "game_pk", "at_bat_number", "pitch_number", "balls", "strikes", "zone",
        "plate_x", "plate_z", "launch_speed", "launch_angle", "launch_speed_angle",
        "bat_speed", "swing_length", "attack_angle", "attack_direction", "swing_path_tilt",
        "intercept_ball_minus_batter_pos_x_inches", "intercept_ball_minus_batter_pos_y_inches",
        "miss_distance", "estimated_woba_using_speedangle", "woba_value", "woba_denom",
    ]
    for column in numeric_columns:
        if column not in result:
            result[column] = np.nan
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result["count"] = result.apply(
        lambda row: f"{int(row['balls'])}-{int(row['strikes'])}"
        if pd.notna(row["balls"]) and pd.notna(row["strikes"]) else "-",
        axis=1,
    )
    result["is_swing"] = result["description"].isin(SWING_EVENTS)
    result["is_whiff"] = result["description"].isin(WHIFF_EVENTS)
    result["pitch_family"] = result["pitch_type"].str.upper().map(PITCH_FAMILIES).fillna("Other")
    result.attrs["source_columns"] = set(rows.columns)
    return result


def apply_batter_period_filters(
    rows: pd.DataFrame,
    *,
    start_date: str,
    end_date: str,
    batter_side: str | None = None,
    pitcher_hand: str | None = None,
    pitch_family: str | None = None,
    count: str | None = None,
    pitch: str | None = None,
    pitch_result: str | None = None,
    in_play_result: str | None = None,
    pa_result: str | None = None,
) -> pd.DataFrame:
    if rows.empty:
        return rows.copy()
    filtered = rows[rows["game_date"].between(start_date, end_date)].copy()
    for column, value in (("stand", batter_side), ("p_throws", pitcher_hand), ("count", count)):
        values = _filter_values(value)
        if values:
            filtered = filtered[filtered[column].isin(values)]
    pitch_values = _filter_values(pitch)
    if pitch_values:
        filtered = filtered[filtered["pitch_name"].isin(pitch_values) | filtered["pitch_type"].isin(pitch_values)]
    family_values = _filter_values(pitch_family)
    if family_values:
        filtered = filtered[filtered["pitch_family"].isin(family_values)]
    result_values = _filter_values(pitch_result)
    if result_values:
        mask = pd.Series(False, index=filtered.index)
        for value in result_values:
            normalized = value.lower().replace(" ", "_")
            if normalized == "swing":
                mask |= filtered["is_swing"]
            elif normalized == "whiff":
                mask |= filtered["is_whiff"]
            elif normalized == "in_play":
                mask |= filtered["description"].eq("hit_into_play")
            else:
                mask |= filtered["description"].eq(normalized)
        filtered = filtered[mask]
    in_play_values = _filter_values(in_play_result)
    if in_play_values:
        filtered = filtered[filtered["bb_type"].str.lower().isin([value.lower() for value in in_play_values])]
    pa_values = _filter_values(pa_result)
    if pa_values:
        terminal = _terminal_pa_rows(filtered)
        mask = pd.Series(False, index=terminal.index)
        for value in pa_values:
            normalized = value.lower().replace(" ", "_")
            if normalized == "hit":
                mask |= terminal["events"].isin(HIT_EVENTS)
            elif normalized == "out":
                mask |= terminal["events"].isin(OUT_EVENTS)
            elif normalized == "strikeout":
                mask |= terminal["events"].isin({"strikeout", "strikeout_double_play"})
            else:
                mask |= terminal["events"].eq(normalized)
        pa_keys = terminal.loc[mask, ["game_pk", "at_bat_number"]].drop_duplicates()
        filtered = filtered.merge(pa_keys, on=["game_pk", "at_bat_number"], how="inner")
    return filtered


def compute_batter_period_metrics(rows: pd.DataFrame) -> dict[str, tuple[float | int | None, int]]:
    pitches = int(len(rows))
    if rows.empty:
        return {key: (None, 0) for key in _metric_keys()}
    pa = _terminal_pa_rows(rows)
    events = pa["events"]
    ab = ~events.isin(NON_AB_EVENTS)
    hits = events.isin(HIT_EVENTS)
    walks = events.isin({"walk", "intent_walk"})
    strikeouts = events.isin({"strikeout", "strikeout_double_play"})
    hbp = events.eq("hit_by_pitch")
    sacrifice_flies = events.isin({"sac_fly", "sac_fly_double_play"})
    ab_count = int(ab.sum())
    pa_count = int(len(pa))
    hit_count = int(hits.sum())
    walk_count = int(walks.sum())
    obp_denominator = ab_count + walk_count + int(hbp.sum()) + int(sacrifice_flies.sum())
    total_bases = int(events.map({"single": 1, "double": 2, "triple": 3, "home_run": 4}).fillna(0).sum())
    woba_denom = pd.to_numeric(pa["woba_denom"], errors="coerce")
    valid_woba = woba_denom.fillna(0).gt(0)
    woba_denominator = int(valid_woba.sum())
    woba = _weighted_woba(pa["woba_value"], woba_denom)
    expected = pd.to_numeric(pa["estimated_woba_using_speedangle"], errors="coerce").fillna(
        pd.to_numeric(pa["woba_value"], errors="coerce")
    )
    xwoba = _weighted_woba(expected, woba_denom)

    swings = rows["is_swing"]
    swing_count = int(swings.sum())
    whiffs = int(rows["is_whiff"].sum())
    zones = pd.to_numeric(rows["zone"], errors="coerce")
    out_zone = zones.notna() & ~zones.between(1, 9)
    chase_count = int((swings & out_zone).sum())
    batted = rows["description"].eq("hit_into_play")
    exit_velocity = pd.to_numeric(rows["launch_speed"], errors="coerce")
    tracked_bbe = batted & exit_velocity.notna()
    tracked_count = int(tracked_bbe.sum())
    speed_angle = pd.to_numeric(rows["launch_speed_angle"], errors="coerce")
    barrel_mask = batted & speed_angle.notna()
    launch_angle = pd.to_numeric(rows["launch_angle"], errors="coerce")
    sweet_spot_mask = batted & launch_angle.notna()

    return {
        "pa": (pa_count, pa_count),
        "ab": (ab_count, pa_count),
        "ops": (_safe_rate(hit_count + walk_count + int(hbp.sum()), obp_denominator, scale=1) + _safe_rate(total_bases, ab_count, scale=1)
                if obp_denominator and ab_count else None, pa_count),
        "woba": (woba, woba_denominator),
        "xwoba": (xwoba, woba_denominator),
        "avg": (_safe_rate(hit_count, ab_count, scale=1), ab_count),
        "obp": (_safe_rate(hit_count + walk_count + int(hbp.sum()), obp_denominator, scale=1), obp_denominator),
        "slg": (_safe_rate(total_bases, ab_count, scale=1), ab_count),
        "avg_ev": (_finite_or_none(exit_velocity[tracked_bbe].mean()), tracked_count),
        "max_ev": (_finite_or_none(exit_velocity[tracked_bbe].max()), tracked_count),
        "barrel_pct": (_safe_rate(int((speed_angle.eq(6) & barrel_mask).sum()), int(barrel_mask.sum())), int(barrel_mask.sum())),
        "hard_hit_pct": (_safe_rate(int((exit_velocity.ge(95) & tracked_bbe).sum()), tracked_count), tracked_count),
        "sweet_spot_pct": (_safe_rate(int((launch_angle.between(8, 32) & sweet_spot_mask).sum()), int(sweet_spot_mask.sum())), int(sweet_spot_mask.sum())),
        "swing_pct": (_safe_rate(swing_count, pitches), pitches),
        "chase_pct": (_safe_rate(chase_count, int(out_zone.sum())), int(out_zone.sum())),
        "contact_pct": (_safe_rate(swing_count - whiffs, swing_count), swing_count),
        "whiff_pct": (_safe_rate(whiffs, swing_count), swing_count),
        "k_pct": (_safe_rate(int(strikeouts.sum()), pa_count), pa_count),
        "bb_pct": (_safe_rate(walk_count, pa_count), pa_count),
        "k_bb_pct": (_safe_rate(int(strikeouts.sum()) - walk_count, pa_count), pa_count),
    }


METRIC_SPECS = [
    ("pa", "PA", "sample", "count", "count", "PA"),
    ("ab", "AB", "sample", "count", "count", "PA"),
    ("ops", "OPS", "production", "rate", "rate", "PA"),
    ("woba", "wOBA", "production", "rate", "rate", "wOBA PA"),
    ("xwoba", "xwOBA", "production", "rate", "rate", "wOBA PA"),
    ("avg", "AVG", "production", "rate", "rate", "AB"),
    ("obp", "OBP", "production", "rate", "rate", "OBP PA"),
    ("slg", "SLG", "production", "rate", "rate", "AB"),
    ("avg_ev", "Avg EV", "contact", "mph", "mph", "Tracked BBE"),
    ("max_ev", "Max EV", "contact", "mph", "mph", "Tracked BBE"),
    ("barrel_pct", "Barrel%", "contact", "pct", "pp", "Classified BBE"),
    ("hard_hit_pct", "HardHit%", "contact", "pct", "pp", "Tracked BBE"),
    ("sweet_spot_pct", "SweetSpot%", "contact", "pct", "pp", "Launch-angle BBE"),
    ("swing_pct", "Swing%", "discipline", "pct", "pp", "Pitches"),
    ("chase_pct", "Chase%", "discipline", "pct", "pp", "Out-of-zone pitches"),
    ("contact_pct", "Contact%", "discipline", "pct", "pp", "Swings"),
    ("whiff_pct", "Whiff%", "discipline", "pct", "pp", "Swings"),
    ("k_pct", "K%", "discipline", "pct", "pp", "PA"),
    ("bb_pct", "BB%", "discipline", "pct", "pp", "PA"),
    ("k_bb_pct", "K-BB%", "discipline", "pct", "pp", "PA"),
    ("avg_bat_speed", "Avg Bat Speed", "tracking", "mph", "mph", "Competitive swings"),
    ("fast_swing_pct", "Fast Swing%", "tracking", "pct", "pp", "Competitive swings"),
    ("competitive_pct", "Competitive%", "tracking", "pct", "pp", "Tracked swings"),
    ("avg_swing_length", "Swing Length", "tracking", "ft", "ft", "Tracked swings"),
    ("squared_up_pct", "Squared-Up%", "tracking", "pct", "pp", "Tracked swings"),
    ("blast_pct", "Blast%", "tracking", "pct", "pp", "Tracked swings"),
    ("avg_miss_distance", "Avg Miss Distance", "timing", "in", "in", "Tracked whiffs"),
]


def get_batter_period_comparison(
    *, batter_id: int, left_year: int, right_year: int, left_start: str, left_end: str,
    right_start: str, right_end: str, batter_side: str | None = None,
    pitcher_hand: str | None = None, pitch_family: str | None = None,
    count: str | None = None, pitch: str | None = None,
    pitch_result: str | None = None,
    in_play_result: str | None = None,
    pa_result: str | None = None,
) -> BatterPeriodComparisonResponse:
    left_all = load_batter_period_rows(left_year, batter_id)
    right_all = left_all.copy() if right_year == left_year else load_batter_period_rows(right_year, batter_id)
    filter_args = dict(batter_side=batter_side, pitcher_hand=pitcher_hand, pitch_family=pitch_family, count=count, pitch=pitch, pitch_result=pitch_result, in_play_result=in_play_result, pa_result=pa_result)
    left = apply_batter_period_filters(left_all, start_date=left_start, end_date=left_end, **filter_args)
    right = apply_batter_period_filters(right_all, start_date=right_start, end_date=right_end, **filter_args)
    left_stats = compute_batter_period_metrics(left)
    right_stats = compute_batter_period_metrics(right)
    left_stats.update(compute_tracking_period_metrics(left, _competitive_cutoff(left_all)))
    right_stats.update(compute_tracking_period_metrics(right, _competitive_cutoff(right_all)))
    metrics = []
    for key, label, group, unit, delta_unit, denominator_label in METRIC_SPECS:
        left_value, left_denominator = left_stats[key]
        right_value, right_denominator = right_stats[key]
        delta = None if left_value is None or right_value is None else float(right_value) - float(left_value)
        metrics.append(BatterPeriodMetric(
            key=key, label=label, group=group, unit=unit, delta_unit=delta_unit,
            period_a=left_value, period_b=right_value, delta=delta,
            denominator_label=denominator_label,
            period_a_denominator=left_denominator, period_b_denominator=right_denominator,
        ))

    percentile_cards = {
        "left": build_period_percentile_cards(left_year, left_stats),
        "right": build_period_percentile_cards(right_year, right_stats),
    }

    competitive_cutoffs = {
        left_year: _competitive_cutoff(left_all),
        right_year: _competitive_cutoff(right_all),
    }
    left_points = _heatmap_points(left, competitive_cutoffs[left_year])
    right_points = _heatmap_points(right, competitive_cutoffs[right_year])
    bat_speeds = [
        float(point["bat_speed"]) for point in [*left_points, *right_points]
        if point.get("bat_speed") is not None
    ]
    warnings = []
    if left.empty:
        warnings.append("Period A has no pitches for the active filters.")
    if right.empty:
        warnings.append("Period B has no pitches for the active filters.")
    if left_year == 2023 or right_year == 2023:
        warnings.append("2023 Bat Tracking begins after the All-Star break; denominators reflect partial-season coverage.")
    if left_year != 2026 or right_year != 2026:
        warnings.append("Pitch-level Miss Distance is available only for 2026; other years remain unavailable for arbitrary date windows.")
    options = list_batter_options(right_year)
    batter = next((option for option in options if int(option["value"]) == batter_id), None)
    all_rows = pd.concat([left_all, right_all], ignore_index=True)
    dates = pd.to_datetime(all_rows.get("game_date"), errors="coerce").dropna() if not all_rows.empty else pd.Series(dtype="datetime64[ns]")
    return BatterPeriodComparisonResponse(
        meta=ResponseMeta(year=right_year, data_updated_at=dates.max().to_pydatetime() if not dates.empty else None, warnings=warnings),
        batter=batter,
        periods={
            "left": BatterPeriodWindow(label="Period A", year=left_year, start_date=left_start, end_date=left_end, pitches=len(left), team=_period_team(left)),
            "right": BatterPeriodWindow(label="Period B", year=right_year, start_date=right_start, end_date=right_end, pitches=len(right), team=_period_team(right)),
        },
        filters=_filter_options(pd.concat([left_all, right_all], ignore_index=True)),
        metrics=metrics,
        percentile_cards=percentile_cards,
        discipline={
            "left": {"panel_groups": build_discipline_panel_groups(left, _discipline_location_rows), "total": len(left)},
            "right": {"panel_groups": build_discipline_panel_groups(right, _discipline_location_rows), "total": len(right)},
        },
        heatmaps={"left": left_points, "right": right_points},
        bat_speed_domain=[round(min(bat_speeds), 1), round(max(bat_speeds), 1)] if bat_speeds else None,
    )


def build_period_percentile_cards(year: int, stats: dict[str, tuple[float | int | None, int]]) -> list[dict[str, Any]]:
    qualified = []
    for row in list_batter_leaderboard(year):
        plate_appearances = pd.to_numeric(row.get("plate_appearances"), errors="coerce")
        if pd.notna(plate_appearances) and float(plate_appearances) >= 50:
            qualified.append(row)
    cards: list[dict[str, Any]] = []
    for metric_key, label, unit, higher_is_better, pool_key, period_scale in PERIOD_PERCENTILE_SPECS:
        raw_value = stats.get(metric_key, (None, 0))[0]
        value = None if raw_value is None else float(raw_value) * period_scale
        population = pd.to_numeric(pd.Series([row.get(pool_key) for row in qualified]), errors="coerce").dropna()
        percentile = None
        if value is not None and np.isfinite(value) and not population.empty:
            favorable = population.le(value).mean() if higher_is_better else population.ge(value).mean()
            percentile = round(float(np.clip(favorable * 100, 1, 100)), 0)
        cards.append({
            "key": metric_key,
            "label": label,
            "value": value,
            "formatted_value": _format_percentile_value(value, unit),
            "percentile": percentile,
            "higher_is_better": higher_is_better,
        })
    return cards


def _format_percentile_value(value: float | None, unit: str) -> str:
    if value is None or not np.isfinite(value):
        return "—"
    if unit == "percent":
        return f"{value * 100:.1f}%"
    if unit == "rate":
        return f"{value:.3f}".lstrip("0")
    return f"{value:.1f}"


def _period_team(rows: pd.DataFrame) -> str | None:
    if rows.empty:
        return None
    for column in ("batter_team", "offense_team"):
        values = rows.get(column, pd.Series(dtype="object")).fillna("").astype(str).str.strip()
        values = values[values.ne("")]
        if not values.empty:
            return str(values.mode().iloc[0])
    return None


def _discipline_location_rows(rows: pd.DataFrame) -> list[dict[str, Any]]:
    if rows.empty:
        return []
    columns = [
        column for column in (
            "game_date", "game_pk", "at_bat_number", "pitch_number", "plate_x", "plate_z",
            "pitch_name", "pitch_type", "description", "events", "count", "release_speed",
            "launch_speed", "bat_speed", "play_id", "video_url", "pitch_stuff_plus", "location_plus_pitch",
        ) if column in rows.columns
    ]
    located = rows.dropna(subset=["plate_x", "plate_z"])[columns].copy()
    return located.astype(object).where(pd.notna(located), None).to_dict("records")


def compute_tracking_period_metrics(rows: pd.DataFrame, cutoff: float | None) -> dict[str, tuple[float | None, int]]:
    if rows.empty:
        return {key: (None, 0) for key in ("avg_bat_speed", "fast_swing_pct", "competitive_pct", "avg_swing_length", "squared_up_pct", "blast_pct", "avg_miss_distance")}
    bat_speed = pd.to_numeric(rows["bat_speed"], errors="coerce")
    exit_velocity = pd.to_numeric(rows["launch_speed"], errors="coerce")
    tracked = rows["is_swing"] & ~rows["description"].isin(BUNT_EVENTS) & bat_speed.notna()
    competitive = tracked.copy()
    if cutoff is not None:
        competitive &= bat_speed.ge(cutoff) | (bat_speed.ge(60) & exit_velocity.ge(90))
    tracked_count = int(tracked.sum())
    competitive_count = int(competitive.sum())
    swing_length = pd.to_numeric(rows["swing_length"], errors="coerce")
    length_mask = tracked & swing_length.notna()
    miss_distance = pd.to_numeric(rows["miss_distance"], errors="coerce")
    miss_mask = rows["is_whiff"] & miss_distance.notna() & ~rows["description"].isin(BUNT_EVENTS)
    return {
        "avg_bat_speed": (_finite_or_none(bat_speed[competitive].mean()), competitive_count),
        "fast_swing_pct": (_safe_rate(int((competitive & bat_speed.ge(75)).sum()), competitive_count), competitive_count),
        "competitive_pct": (_safe_rate(competitive_count, tracked_count), tracked_count),
        "avg_swing_length": (_finite_or_none(swing_length[length_mask].mean()), int(length_mask.sum())),
        "squared_up_pct": (None, 0),
        "blast_pct": (None, 0),
        "avg_miss_distance": (_finite_or_none(miss_distance[miss_mask].mean()), int(miss_mask.sum())),
    }


def _terminal_pa_rows(rows: pd.DataFrame) -> pd.DataFrame:
    terminal = rows[rows["events"].ne("") & rows["events"].ne("truncated_pa")].copy()
    if terminal.empty:
        return terminal
    return terminal.sort_values(["game_pk", "at_bat_number", "pitch_number"]).groupby(
        ["game_pk", "at_bat_number"], as_index=False
    ).tail(1)


def _heatmap_points(rows: pd.DataFrame, cutoff: float | None) -> list[dict[str, Any]]:
    located = rows.dropna(subset=["plate_x", "plate_z"]).copy()
    if located.empty:
        return []
    bat_speed = pd.to_numeric(located["bat_speed"], errors="coerce")
    exit_velocity = pd.to_numeric(located["launch_speed"], errors="coerce")
    competitive = located["is_swing"] & ~located["description"].isin(BUNT_EVENTS) & bat_speed.notna()
    if cutoff is not None:
        competitive &= bat_speed.ge(cutoff) | (bat_speed.ge(60) & exit_velocity.ge(90))
    located["bat_speed"] = bat_speed.where(competitive)
    columns = [
        "game_date", "game_pk", "at_bat_number", "pitch_number", "pitch_name",
        "description", "events", "plate_x", "plate_z", "bat_speed", "is_swing",
    ]
    return located[columns].astype(object).where(pd.notna(located[columns]), None).to_dict("records")


def _competitive_cutoff(rows: pd.DataFrame) -> float | None:
    if rows.empty:
        return None
    eligible = rows["is_swing"] & ~rows["description"].isin(BUNT_EVENTS)
    tracked = pd.to_numeric(rows.loc[eligible, "bat_speed"], errors="coerce").dropna()
    return float(tracked.quantile(0.10)) if not tracked.empty else None


def _filter_options(rows: pd.DataFrame) -> dict[str, list[str]]:
    def values(column: str) -> list[str]:
        return sorted(value for value in rows.get(column, pd.Series(dtype="object")).dropna().astype(str).unique() if value and value != "-")
    return {
        "batter_side": ["All", *values("stand")],
        "pitcher_hand": ["All", *values("p_throws")],
        "pitch_family": ["All", "Fastball", "Breaking", "Offspeed", "Other"],
        "count": ["All", *values("count")],
        "pitch": ["All", *values("pitch_name")],
        "pitch_result": ["All", "Swing", "Whiff", "In Play", *values("description")],
        "in_play_result": ["All", *values("bb_type")],
        "pa_result": ["All", "Hit", "Out", "home_run", "Strikeout"],
    }


def _filter_values(value: str | None) -> list[str]:
    if not value or value == "All":
        return []
    return [item.strip() for item in value.split(",") if item.strip() and item.strip() != "All"]


def _weighted_woba(values: pd.Series, denominators: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce")
    denom = pd.to_numeric(denominators, errors="coerce")
    valid = denom.fillna(0).gt(0)
    if not valid.any():
        return None
    return _finite_or_none(numeric[valid].fillna(0).sum() / denom[valid].sum())


def _safe_rate(numerator: int, denominator: int, *, scale: int = 100) -> float | None:
    return numerator / denominator * scale if denominator else None


def _finite_or_none(value: Any) -> float | None:
    return float(value) if value is not None and pd.notna(value) and np.isfinite(value) else None


def _metric_keys() -> list[str]:
    return [spec[0] for spec in METRIC_SPECS]
