"""Compact seasonal batter rates for the shared In game catcher view.

Reuse Discipline event flags, without loading video/Plus caches or changing replay.
Cells normalize each pitch's zone height and project onto the current batter zone.
"""
from __future__ import annotations

from functools import lru_cache

import duckdb
import numpy as np
import pandas as pd

from app.api.schemas.batter_zone_rates import BatterZoneRatesResponse
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.batter_service import _count_plate_appearances
from app.services.discipline_service import add_discipline_flags, HIT_EVENTS, IN_PLAY_EVENTS, NON_AB_EVENTS

COLUMNS = ("game_pk", "at_bat_number", "pitch_number", "description", "events", "p_throws", "plate_x", "plate_z", "sz_bot", "sz_top", "zone", "launch_speed", "woba_value", "woba_denom")
METRICS = [
    ("swing", "Swing%", "swings / pitches"),
    ("contact", "Contact%", "contacts / swings"),
    ("whiff", "Whiff%", "whiffs / swings"),
    ("swstr", "SwStr%", "swinging strikes / pitches"),
    ("called_strike", "Called Strike%", "called strikes / pitches"),
    ("strike", "Strike%", "strikes / pitches"),
    ("csw", "CSW%", "called strikes or whiffs / pitches"),
    ("z_swing", "Z-Swing%", "in-zone swings / in-zone pitches"),
    ("z_contact", "Z-Contact%", "in-zone contacts / in-zone swings"),
    ("o_swing", "O-Swing%", "outside swings / outside pitches"),
    ("o_contact", "O-Contact%", "outside contacts / outside swings"),
    ("foul", "Foul%", "fouls / pitches"),
    ("in_play", "In-play%", "balls in play / pitches"),
    ("avg", "AVG", "hits / at-bats; assigned to the PA-ending pitch"),
    ("woba", "wOBA", "sum of recorded wOBA value / valid recorded wOBA denominator; PA-ending pitch"),
    ("hard_hit", "HardHit%", "95+ mph fair batted balls / fair batted balls with tracked exit velocity"),
]


def read_rows(path: str, batter_id: int | None) -> pd.DataFrame | None:
    with duckdb.connect(path, read_only=True) as conn:
        table = resolve_pitch_table({r[0] for r in conn.execute("SHOW TABLES").fetchall()})
        if not table:
            return None
        columns = {r[0] for r in conn.execute(f"DESCRIBE {table}").fetchall()}
        if not {"batter", "game_type", "game_pk", "at_bat_number", "events"} <= columns:
            return None
        fields = ", ".join(f'"{c}"' if c in columns else f'NULL AS "{c}"' for c in COLUMNS)
        if batter_id is None:
            return conn.execute(f"SELECT batter, {fields} FROM {table} WHERE game_type = 'R'").fetchdf()
        return conn.execute(f"SELECT {fields} FROM {table} WHERE game_type = 'R' AND batter = ?", [batter_id]).fetchdf()


def aggregate_zone_rates(rows: pd.DataFrame | None, year: int, batter_id: int, hand: str) -> BatterZoneRatesResponse:
    base = dict(year=year, batter_id=batter_id, pitcher_hand=hand, season_pa=0, eligible=False,
                split_pitches=0, located_pitches=0, missing_location_pitches=0,
                zone_height_fallback_pitches=0,
                metrics=[dict(key=k, label=label, denominator=denom, format="decimal" if k in {"avg", "woba"} else "percent", direction=metric_direction(k)) for k, label, denom in METRICS], cells=[])
    if rows is None or rows.empty:
        return BatterZoneRatesResponse(**base, status="unavailable" if rows is None else "no_data")
    rows = rows.copy().reset_index(drop=True)
    for column in COLUMNS:
        if column not in rows:
            rows[column] = None
    rows["events"] = rows["events"].fillna("").astype(str).str.strip().str.lower()
    base["season_pa"] = _count_plate_appearances(rows)
    base["eligible"] = base["season_pa"] > 30
    if not base["eligible"]:
        return BatterZoneRatesResponse(**base, status="insufficient_pa")
    # Exactly one completed PA outcome, chosen before hand/location filtering.
    terminal = rows[rows["events"].ne("") & rows["events"].ne("truncated_pa")].sort_values("pitch_number", kind="stable").drop_duplicates(["game_pk", "at_bat_number"], keep="last").index
    rows["_pa_terminal"] = rows.index.isin(terminal)
    if hand != "All":
        rows = rows[rows["p_throws"].fillna("").astype(str).str.strip().str.upper().eq(hand)].copy()
    base["split_pitches"] = len(rows)
    for column in ("plate_x", "plate_z", "sz_bot", "sz_top", "launch_speed", "woba_value", "woba_denom"):
        rows[column] = pd.to_numeric(rows[column], errors="coerce").astype(float)
    located = np.isfinite(rows["plate_x"]) & np.isfinite(rows["plate_z"])
    base["missing_location_pitches"] = int((~located).sum())
    rows = rows[located].copy()
    base["located_pitches"] = len(rows)
    height_valid = np.isfinite(rows["sz_bot"]) & np.isfinite(rows["sz_top"]) & rows["sz_top"].gt(rows["sz_bot"])
    base["zone_height_fallback_pitches"] = int((~height_valid).sum())
    bottom = rows["sz_bot"].where(height_valid, 1.5)
    top = rows["sz_top"].where(height_valid, 3.5)
    rows["u"] = (rows["plate_x"] + 17 / 24) / (17 / 12)
    rows["v"] = (rows["plate_z"] - bottom) / (top - bottom)
    rows = add_discipline_flags(rows)
    cells = []
    # Stable catcher-physical coordinates: x increases with plate_x, v upward.
    for r in range(3):
        for c in range(3):
            cells.append((f"zone-{r}-{c}", f"Zone row {3-r}, col {c+1}", "zone", (c/3, r/3, (c+1)/3, (r+1)/3)))
    for r in (-1, 0, 1):
        for c in (-1, 0, 1):
            if not (r or c):
                continue
            xs = (-.5, 0) if c == -1 else (1, 1.5) if c == 1 else (0, 1)
            ys = (-.5, 0) if r == -1 else (1, 1.5) if r == 1 else (0, 1)
            label = "Outside " + ("high " if r == 1 else "low " if r == -1 else "") + ("negative-X" if c == -1 else "positive-X" if c == 1 else "center")
            cells.append((f"outside-{r}-{c}", label, "outside", (xs[0], ys[0], xs[1], ys[1])))
    inside = rows["u"].between(0, 1) & rows["v"].between(0, 1)
    for key, label, region, bounds in cells:
        x0, y0, x1, y1 = bounds
        if region == "zone":
            mask = inside & rows["u"].ge(x0) & (rows["u"].le(x1) if x1 == 1 else rows["u"].lt(x1)) & rows["v"].ge(y0) & (rows["v"].le(y1) if y1 == 1 else rows["v"].lt(y1))
        else:
            mask = ~inside
            mask &= rows["u"].lt(0) if x1 == 0 else rows["u"].gt(1) if x0 == 1 else rows["u"].between(0, 1)
            mask &= rows["v"].lt(0) if y1 == 0 else rows["v"].gt(1) if y0 == 1 else rows["v"].between(0, 1)
        group = rows[mask]
        n, swings = len(group), int(group["_is_swing"].sum())
        count = lambda col: int(group[col].sum())
        finished = group[group["_pa_terminal"]]
        at_bats = finished[~finished["_events_norm"].isin(NON_AB_EVENTS)]
        woba = finished[np.isfinite(finished["woba_value"]) & np.isfinite(finished["woba_denom"]) & finished["woba_denom"].gt(0)]
        tracked = finished[finished["_description_norm"].isin(IN_PLAY_EVENTS) & np.isfinite(finished["launch_speed"]) & finished["launch_speed"].gt(0)]
        outcomes = {
            "avg": (int(at_bats["_events_norm"].isin(HIT_EVENTS).sum()), len(at_bats)),
            "woba": (float(woba["woba_value"].sum()), float(woba["woba_denom"].sum())),
            "hard_hit": (int(tracked["launch_speed"].ge(95).sum()), len(tracked)),
        }
        rates = {}
        for metric, _, _ in METRICS:
            if metric in outcomes:
                numerator, denominator = outcomes[metric]
                scale = 1 if metric in {"avg", "woba"} else 100
                rates[metric] = dict(numerator=numerator, denominator=denominator, value=scale*numerator/denominator if denominator else None)
                continue
            applicable = not (metric.startswith("z_") and region != "zone" or metric.startswith("o_") and region != "outside")
            denominator = swings if metric in {"contact", "whiff", "z_contact", "o_contact"} else n
            numerator = (count("_is_swing") if metric in {"swing", "z_swing", "o_swing"} else
                         count("_is_contact") if metric in {"contact", "z_contact", "o_contact"} else
                         int((group["_is_called_strike"] | group["_is_whiff"]).sum()) if metric == "csw" else
                         int(group["_description_norm"].isin({"foul", "foul_tip", "foul_bunt"}).sum()) if metric == "foul" else
                         int(group["_description_norm"].isin({"hit_into_play", "hit_into_play_no_out", "hit_into_play_score"}).sum()) if metric == "in_play" else
                         count({"whiff":"_is_whiff", "swstr":"_is_swstr", "called_strike":"_is_called_strike", "strike":"_is_strike"}[metric]))
            numerator, denominator = (numerator, denominator) if applicable else (0, 0)
            rates[metric] = dict(numerator=numerator, denominator=denominator, value=100*numerator/denominator if denominator else None)
        base["cells"].append(dict(id=key, label=label, region=region, bounds=bounds, pitches=n, rates=rates))
    return BatterZoneRatesResponse(**base, status="ready" if len(rows) else "no_data")


@lru_cache(maxsize=128)
def _cached(year: int, batter_id: int, hand: str, path: str, mtime: int, size: int) -> BatterZoneRatesResponse:
    return aggregate_zone_rates(read_rows(path, batter_id), year, batter_id, hand)


def metric_direction(metric: str) -> str:
    if metric in {"whiff", "swstr", "called_strike", "strike", "csw", "o_swing"}:
        return "lower"
    if metric in {"avg", "woba", "hard_hit", "contact", "z_contact", "o_contact"}:
        return "higher"
    return "frequency"


def get_batter_zone_rates(year: int, batter_id: int, hand: str) -> BatterZoneRatesResponse:
    path = get_season_duckdb_path(year, settings.data_dir)
    if not path.exists():
        return aggregate_zone_rates(None, year, batter_id, hand)
    stat = path.stat()
    wal = path.with_suffix(path.suffix + ".wal")
    wal_stat = wal.stat() if wal.exists() else None
    result = _cached(year, batter_id, hand, str(path), max(stat.st_mtime_ns, wal_stat.st_mtime_ns if wal_stat else 0), stat.st_size + (wal_stat.st_size if wal_stat else 0))
    from app.services.batter_zone_baseline_service import apply_benchmark
    return apply_benchmark(result, path)
