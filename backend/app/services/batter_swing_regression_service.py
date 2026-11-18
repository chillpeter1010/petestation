"""On-demand Swing Timing axes using the existing Stuff Attack calculations."""
from functools import lru_cache
from pathlib import Path

import duckdb
import pandas as pd

from app.api.schemas.batter_swing_timing import SwingTimingResponse
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path
from app.services.batter_stuff_attack_service import (
    AXIS_OPTIONS, SWING_DESCRIPTIONS, _add_metric_flags,
)
from app.services.batter_swing_matchup_service import _pitch_table, _columns

TIMING_AXES = [
    ("age", "Age", "years"), ("plate_appearances", "Season PA", "PA"),
    ("n_swings", "Filtered Swings", "swings"), ("context_pa", "Filtered Terminal PA", "PA"),
    ("k_pct", "K%", "%"), ("bb_pct", "BB%", "%"), ("k_bb_pct", "K−BB%", "%"),
    ("flawed_pct", "Flawed Swing%", "%"), ("perfect_pct", "Perfect Contact%", "%"),
    ("competitive_pct", "Competitive%", "%"),
    ("tied_up_pct", "Tied Up%", "%"), ("avg_tied_up_distance", "Avg Tied-up Distance", "in"),
    ("centered_pct", "Centered%", "%"), ("flail_pct", "Flail%", "%"),
    ("avg_flail_distance", "Avg Flail Distance", "in"),
    ("late_pct", "Late%", "%"), ("avg_late_ms", "Avg Late", "ms"),
    ("on_time_pct", "On Time%", "%"), ("early_pct", "Early%", "%"),
    ("avg_early_ms", "Avg Early", "ms"), ("over_pct", "Over%", "%"),
    ("avg_over_distance", "Avg Over Distance", "in"), ("lined_up_pct", "Lined Up%", "%"),
    ("under_pct", "Under%", "%"), ("avg_under_distance", "Avg Under Distance", "in"),
]


def add_swing_timing_regression(response: SwingTimingResponse, data_dir: Path | None = None) -> SwingTimingResponse:
    from app.services.batter_swing_timing_service import _selected_pitch_codes
    codes = tuple(sorted(_selected_pitch_codes(response.pitch_group, response.pitch_type) or ()))
    path = get_season_duckdb_path(response.year, Path(data_dir or settings.data_dir))
    values = {}
    if path.exists():
        stat = path.stat()
        wal = path.with_suffix(path.suffix + ".wal")
        values = _cached_regression_axes(str(path.resolve()), stat.st_mtime_ns, stat.st_size,
            wal.stat().st_mtime_ns if wal.exists() else 0, codes, response.pitcher_hand,
            response.batter_side, response.batter_team, response.pitcher_team)
    rows = []
    for row in response.leaderboard:
        axes, samples = values.get(row.batter_id, ({}, {}))
        axes, samples = dict(axes), dict(samples)
        # Overlapping axes use the exact values already shown in this leaderboard.
        for key in ("avg_bat_speed", "ideal_attack_angle_pct", "whiff_pct", *[key for key, _, _ in TIMING_AXES]):
            axes[key] = getattr(row, key)
            samples[key] = row.context_pa if key in {"k_pct", "bb_pct", "k_bb_pct"} else row.n_swings
        for key, _, unit in TIMING_AXES:
            if unit in {"in", "ms"} and axes[key] is not None:
                axes[key] = abs(axes[key])
        samples["avg_bat_speed"] = row.bat_speed_swings
        samples["ideal_attack_angle_pct"] = row.attack_angle_swings
        axes["avg_miss_distance"] = row.miss_distance
        rows.append(row.model_copy(update={"axis_metrics": axes, "axis_samples": samples}))
    options = [dict(option) for option in AXIS_OPTIONS]
    options.extend({"key": key, "label": label, "unit": unit, "population": "Season context" if key in {"age", "plate_appearances"} else "Filtered terminal PA" if key in {"k_pct", "bb_pct", "k_bb_pct", "context_pa"} else "Filtered swings" if key == "n_swings" else "Swing Timing summary",
                    "description": "Same filtered value as the Swing Timing leaderboard; missing values are excluded."}
                   for key, label, unit in TIMING_AXES)
    return response.model_copy(update={"leaderboard": rows,
        "filters": response.filters.model_copy(update={"axis_options": options})})


@lru_cache(maxsize=16)
def _cached_regression_axes(path: str, modified_at: int, size: int, wal_stamp: int,
    codes: tuple[str, ...], hand: str, side: str, hitter_team: str, pitcher_team: str) -> dict:
    with duckdb.connect(path, read_only=True) as conn:
        table = _pitch_table(conn)
        columns = _columns(conn, table)
        if not {"game_type", "description", "pitch_type", "game_pk", "at_bat_number", "pitch_number"}.issubset(columns):
            return {}
        batter = "batter_id" if "batter_id" in columns else "batter"
        fields = ["description", "pitch_type", "p_throws", "stand", "batter_team", "pitcher_team",
                  "balls", "strikes", "plate_x", "plate_z", "sz_top", "sz_bot", "launch_speed",
                  "launch_speed_angle", "estimated_woba_using_speedangle", "delta_run_exp", "bat_speed",
                  "swing_length", "attack_angle", "attack_direction", "swing_path_tilt", "miss_distance", "launch_angle"]
        select = ", ".join(key if key in columns else f"NULL AS {key}" for key in fields)
        clauses, params = [], []
        if codes:
            clauses.append(f"pitch_type IN ({','.join('?' for _ in codes)})")
            params.extend(codes)
        for key, value in (("p_throws", hand), ("stand", side), ("batter_team", hitter_team), ("pitcher_team", pitcher_team)):
            if value != "All":
                clauses.append(f"{key} = ?")
                params.append(value)
        swing_list = ",".join("'" + item + "'" for item in sorted(SWING_DESCRIPTIONS))
        frame = conn.execute(f"""
            WITH season AS (
                SELECT CAST({batter} AS BIGINT) AS batter, {select}
                FROM {table} WHERE game_type = 'R'
                QUALIFY ROW_NUMBER() OVER (PARTITION BY game_pk, at_bat_number, pitch_number ORDER BY {batter}) = 1
            ), baseline AS (
                SELECT *, QUANTILE_CONT(CASE WHEN description IN ({swing_list}) THEN bat_speed END, 0.1)
                    OVER (PARTITION BY batter) AS _p10 FROM season
            ) SELECT * FROM baseline WHERE {' AND '.join(clauses) or 'TRUE'}
        """, params).fetchdf()
    if frame.empty:
        return {}
    frame = frame[frame.batter.notna()].copy()
    if frame.empty:
        return {}
    frame["_competitive_swing"] = frame.description.isin(SWING_DESCRIPTIONS) & frame.bat_speed.notna() & (
        frame.bat_speed.ge(frame._p10) | (frame.bat_speed.ge(60) & frame.launch_speed.ge(90)))
    prepared = _add_metric_flags(frame)
    rows = _grouped_axes(prepared)
    # Source-field absence must not become a fabricated 0% Hard-Hit/Barrel rate.
    for axes, _ in rows.values():
        if "launch_speed" not in columns:
            axes["hard_hit_pct"] = None
        if "launch_speed_angle" not in columns:
            axes["barrel_pct"] = None
    return rows


def _grouped_axes(data: pd.DataFrame) -> dict:
    """Same Stuff Attack formulas, aggregated together instead of per-player scans."""
    swing, bbe, competitive = data._swing, data._bbe, data._competitive_swing
    signals = {
        "swing_pct": data._swing.astype(float),
        "chase_pct": data._swing.astype(float).where(~data._zone),
        "contact_pct": data._contact.astype(float).where(swing),
        "whiff_pct": data._whiff.astype(float).where(swing),
        "rv_per_100_swings": data._rv.where(swing),
        "avg_bat_speed": data.bat_speed.where(competitive),
        "fast_swing_pct": data._fast_swing.astype(float).where(competitive),
        "avg_swing_length": data.swing_length.where(swing),
        "avg_attack_angle": data.attack_angle.where(swing),
        "ideal_attack_angle_pct": pd.to_numeric(data._ideal_attack_angle, errors="coerce").where(swing),
        "avg_swing_path_tilt": data.swing_path_tilt.where(swing),
        "avg_exit_velocity": data.launch_speed.where(bbe),
        "hard_hit_pct": data._hard_hit.astype(float).where(bbe),
        "barrel_pct": data._barrel.astype(float).where(bbe),
        "xwoba_contact": data._xwoba_contact.where(bbe),
        "avg_launch_angle": data.launch_angle.where(bbe),
        "avg_miss_distance": data._miss_distance.where(data._whiff),
        "_expected_swing": data._expected_swing,
        "_expected_contact": data._expected_contact.where(swing),
        "_expected_rv": data._expected_swing_rv.where(swing),
    }
    grouped = pd.DataFrame(signals).groupby(data.batter)
    means, counts = grouped.mean(), grouped.count()
    for key, raw, expected in (("adjusted_swing_pct", "swing_pct", "_expected_swing"),
        ("adjusted_contact_pct", "contact_pct", "_expected_contact"),
        ("adjusted_rv_per_100_swings", "rv_per_100_swings", "_expected_rv")):
        means[key] = means[raw] - means[expected] + signals[raw].mean()
        counts[key] = counts[raw]
    output = {}
    for player_id, values in means.iterrows():
        axes = {}
        for option in AXIS_OPTIONS:
            key = option["key"]
            multiplier = 100 if option["unit"] in {"%", "RV"} else 1
            axes[key] = round(float(values[key]) * multiplier, 3) if pd.notna(values[key]) else None
        output[int(player_id)] = (axes, {key: int(counts.loc[player_id, key]) for key in axes})
    return output
