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
from app.services.batter_service import list_batter_options
from app.services.batter_swing_timing_service import load_batter_timing_cache

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
PITCH_FAMILIES = {
    "FF": "Fastball", "SI": "Fastball", "FC": "Fastball",
    "SL": "Breaking", "ST": "Breaking", "CU": "Breaking", "KC": "Breaking", "SV": "Breaking",
    "CH": "Offspeed", "FS": "Offspeed", "FO": "Offspeed",
}


def get_batter_period_options(year: int) -> BatterPeriodOptionsResponse:
    return BatterPeriodOptionsResponse(
        meta=ResponseMeta(year=year),
        years=available_db_years(settings.data_dir),
        batters=list_batter_options(year),
    )


def get_batter_period_date_range(year: int, batter_id: int) -> dict[str, Any]:
    rows = load_batter_period_rows(year, batter_id)
    dates = pd.to_datetime(rows.get("game_date"), errors="coerce").dropna() if not rows.empty else pd.Series(dtype="datetime64[ns]")
    return {
        "year": year,
        "batter_id": batter_id,
        "start_date": dates.min().strftime("%Y-%m-%d") if not dates.empty else None,
        "end_date": dates.max().strftime("%Y-%m-%d") if not dates.empty else None,
        "pitches": int(len(rows)),
    }


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
    text_columns = ["events", "description", "stand", "p_throws", "pitch_type", "pitch_name"]
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
) -> BatterPeriodComparisonResponse:
    left_all = load_batter_period_rows(left_year, batter_id)
    right_all = left_all.copy() if right_year == left_year else load_batter_period_rows(right_year, batter_id)
    filter_args = dict(batter_side=batter_side, pitcher_hand=pitcher_hand, pitch_family=pitch_family, count=count, pitch=pitch, pitch_result=pitch_result)
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
            "left": BatterPeriodWindow(label="Period A", year=left_year, start_date=left_start, end_date=left_end, pitches=len(left)),
            "right": BatterPeriodWindow(label="Period B", year=right_year, start_date=right_start, end_date=right_end, pitches=len(right)),
        },
        filters=_filter_options(pd.concat([left_all, right_all], ignore_index=True)),
        metrics=metrics,
        heatmaps={"left": left_points, "right": right_points},
        bat_speed_domain=[round(min(bat_speeds), 1), round(max(bat_speeds), 1)] if bat_speeds else None,
        timing_reference={
            "left": _season_timing_reference(left_year, batter_id, pitcher_hand, batter_side),
            "right": _season_timing_reference(right_year, batter_id, pitcher_hand, batter_side),
        },
        source_audit={
            "exact_timing_distributions": {"status": "unavailable", "reason": "Local Savant caches contain season summaries, not date-filterable X/Y/Z bins or swing-level offsets."},
            "batting_stance": {"status": "unavailable", "reason": "No foot-position, stance depth, distance-off-plate, stance-angle, release, or stance-frame fields exist locally."},
            "intercept_geometry": {
                "status": "available",
                "meaning": "Swing intercept and attack geometry; not a batting-stance or foot-position measurement.",
                "left": _intercept_summary(left),
                "right": _intercept_summary(right),
            },
            "squared_up_and_blast": {"status": "unavailable", "reason": "The local pitch tables do not contain Statcast squared-up or blast classifications."},
        },
    )


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
    }


def _season_timing_reference(year: int, batter_id: int, pitcher_hand: str | None, batter_side: str | None) -> dict[str, Any]:
    frame = load_batter_timing_cache(year, pitcher_hand or "All")
    player = frame[frame["player_id"].eq(batter_id)].copy() if not frame.empty else pd.DataFrame()
    sides = _filter_values(batter_side)
    if sides and not player.empty:
        player = player[player["batter_side"].isin(sides)]
    if player.empty:
        return {"mode": "unavailable", "year": year, "n_swings": 0, "metrics": {}}
    swings = pd.to_numeric(player["n_swings"], errors="coerce").fillna(0)

    def weighted(column: str, weights: pd.Series = swings, scale: float = 1.0) -> float | None:
        values = pd.to_numeric(player.get(column), errors="coerce")
        valid = values.notna() & weights.gt(0)
        if not valid.any():
            return None
        return round(float(np.average(values[valid], weights=weights[valid])) * scale, 3)

    whiff_weights = swings * pd.to_numeric(player["whiff_rate"], errors="coerce").fillna(0).clip(lower=0)
    return {
        "mode": "season_summary_reference",
        "year": year,
        "n_swings": int(round(float(swings.sum()))),
        "metrics": {
            "avg_miss_distance": weighted("miss_distance", whiff_weights),
            "flawed_pct": weighted("flawed_percent", scale=100),
            "perfect_pct": weighted("perfect_percent", scale=100),
            "tied_up_pct": weighted("tied_up_percent", scale=100),
            "centered_pct": weighted("centered_percent", scale=100),
            "flail_pct": weighted("flailed_percent", scale=100),
            "late_pct": weighted("late_percent", scale=100),
            "on_time_pct": weighted("on_time_percent", scale=100),
            "early_pct": weighted("early_percent", scale=100),
            "over_pct": weighted("over_percent", scale=100),
            "lined_up_pct": weighted("lined_up_percent", scale=100),
            "under_pct": weighted("under_percent", scale=100),
        },
        "note": "Full-season Savant summary reference. It is not used in the arbitrary-period delta column.",
    }


def _intercept_summary(rows: pd.DataFrame) -> dict[str, Any]:
    tracked = rows[rows["is_swing"] & ~rows["description"].isin(BUNT_EVENTS)]
    return {
        "tracked_swings": int(pd.to_numeric(tracked["bat_speed"], errors="coerce").notna().sum()),
        "intercept_x_inches": _finite_or_none(pd.to_numeric(tracked["intercept_ball_minus_batter_pos_x_inches"], errors="coerce").mean()),
        "intercept_y_inches": _finite_or_none(pd.to_numeric(tracked["intercept_ball_minus_batter_pos_y_inches"], errors="coerce").mean()),
        "attack_angle_deg": _finite_or_none(pd.to_numeric(tracked["attack_angle"], errors="coerce").mean()),
        "attack_direction_deg": _finite_or_none(pd.to_numeric(tracked["attack_direction"], errors="coerce").mean()),
        "swing_path_tilt_deg": _finite_or_none(pd.to_numeric(tracked["swing_path_tilt"], errors="coerce").mean()),
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
