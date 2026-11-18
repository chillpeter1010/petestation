"""Prior-date empirical batter context, never inferred intent or body motion.

No current pitch type, location or outcome is an input. Same-day games are
excluded; missing predecessor identities never become first-pitch observations.
"""
from datetime import date
from functools import lru_cache

import duckdb
import numpy as np
import pandas as pd

from app.api.schemas.batter_zone_rates import BatterZoneRatesResponse
from app.api.schemas.pitch_scout import PitchScoutResponse
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.batter_service import _count_plate_appearances
from app.services.batter_zone_rates_service import COLUMNS, METRICS, metric_direction
from app.services.discipline_service import add_discipline_flags, IN_PLAY_EVENTS, SWING_EVENTS, BALL_EVENTS, CALLED_STRIKE_EVENTS

FIELDS = (*COLUMNS, "game_date", "pitcher", "stand", "balls", "strikes", "pitch_type")
METRIC_KEYS = {"swing", "hard_hit", "whiff", "contact", "called_strike"}
MIN_CONTEXT = 30


def family(value):
    if value in {"FF", "FA", "SI", "FT", "FC"}:
        return "Fastball"
    if value in {"SL", "ST", "SV", "CU", "KC", "CS"}:
        return "Breaking"
    if value in {"CH", "FS", "FO", "SC"}:
        return "Offspeed"
    return "Unknown"


@lru_cache(maxsize=32)
def read_history(path, stamp, size, batter_id):
    with duckdb.connect(path, read_only=True) as conn:
        table = resolve_pitch_table({r[0] for r in conn.execute("SHOW TABLES").fetchall()})
        if not table:
            return None
        columns = {r[0] for r in conn.execute(f"DESCRIBE {table}").fetchall()}
        if not {"batter", "game_type", "game_date", "pitch_number", "pitcher", "stand", "balls", "strikes"} <= columns:
            return None
        fields = ",".join(f'"{c}"' if c in columns else f'NULL AS "{c}"' for c in FIELDS)
        return conn.execute(f"SELECT {fields} FROM {table} WHERE game_type='R' AND batter=?", [batter_id]).fetchdf()


def broad_count(balls, strikes):
    return "Two strikes" if strikes == 2 else "Hitter ahead" if balls > strikes else "Pitcher ahead" if strikes > balls else "Even / shallow count"


def build_context(rows, year, batter_id, hand, stand, before, balls, strikes, previous_type, previous_result, source="fixture"):
    prior = rows.copy() if rows is not None else pd.DataFrame(columns=FIELDS)
    for col in FIELDS:
        if col not in prior:
            prior[col] = None
    prior = prior[pd.to_datetime(prior.game_date, errors="coerce").dt.date.lt(before)].copy()
    prior.events = prior.events.fillna("").astype(str)
    pa = _count_plate_appearances(prior) if len(prior) else 0
    # Exact adjacent predecessor, within batter/game/PA/pitcher, before filtering.
    prior = prior.sort_values(["game_pk", "at_bat_number", "pitch_number"]).reset_index(drop=True)
    prior = prior.drop_duplicates(["game_pk", "at_bat_number", "pitch_number"], keep=False)
    prev = prior.shift(1)
    adjacent = prior.game_pk.eq(prev.game_pk) & prior.at_bat_number.eq(prev.at_bat_number) & prior.pitcher.eq(prev.pitcher) & prior.pitch_number.eq(prev.pitch_number + 1)
    prior["_previous_type"] = prev.pitch_type.where(adjacent, "__missing__")
    prior["_previous_result"] = prev.description.where(adjacent, "__missing__")
    prior.loc[prior.pitch_number.eq(1), ["_previous_type", "_previous_result"]] = "__first__"
    prior = prior[prior.stand.eq(stand) & (prior.p_throws.eq(hand) if hand != "All" else True)].copy()
    prior = prior[~prior.pitch_type.isin(["PO", "IN"])].copy()
    # Automatic penalties / unknown descriptions are not observed swing/take decisions.
    prior = prior[prior.description.isin(SWING_EVENTS | BALL_EVENTS | CALLED_STRIKE_EVENTS)].copy()
    for col in ("balls", "strikes"):
        prior[col] = pd.to_numeric(prior[col], errors="coerce")
    prior = prior[prior.balls.between(0,3) & prior.strikes.between(0,2) & prior.balls.mod(1).eq(0) & prior.strikes.mod(1).eq(0)].copy()
    prior["_family"] = prior.pitch_type.map(family)
    exact = prior[prior.balls.eq(balls) & prior.strikes.eq(strikes)]
    tiers = []
    if previous_type not in {"__missing__", "__first__"} and family(previous_type) != "Unknown":
        tiers.append(("Exact count + previous type/result", exact[exact._previous_type.eq(previous_type) & exact._previous_result.eq(previous_result)]))
        tiers.append(("Exact count + previous family", exact[exact._previous_type.map(family).eq(family(previous_type))]))
    elif previous_type == "__first__":
        tiers.append(("First pitch", exact[exact._previous_type.eq("__first__")]))
    tiers.append(("Exact count", exact))
    group = broad_count(balls, strikes)
    broad = prior[[broad_count(b, s) == group for b, s in zip(prior.balls, prior.strikes)]] if len(prior) else prior
    tiers.append((group, broad))
    tier, sample = next(((name, frame) for name, frame in tiers if len(frame) >= MIN_CONTEXT), ("Insufficient history", prior.iloc[:0]))
    sample = add_discipline_flags(sample.copy())
    swings = int(sample._is_swing.sum())
    heatmap = dict(year=year, batter_id=batter_id, pitcher_hand=hand, season_pa=pa, eligible=pa > 30,
                   status="ready" if len(sample) and pa > 30 else "insufficient_pa", split_pitches=len(sample),
                   located_pitches=0, missing_location_pitches=0, zone_height_fallback_pitches=0,
                   metrics=[dict(key=k, label=l, denominator=d, direction=metric_direction(k)) for k,l,d in METRICS if k in METRIC_KEYS],
                   cells=[], benchmark_status="context_rates", scope=f"Before {before}; {stand}HB vs {hand}HP; {tier}; absolute rates, not league PR")
    located = sample.copy()
    for col in ("plate_x", "plate_z", "sz_bot", "sz_top", "launch_speed"):
        located[col] = pd.to_numeric(located[col], errors="coerce").astype(float)
    located = located[np.isfinite(located.plate_x) & np.isfinite(located.plate_z)].copy()
    valid_height = np.isfinite(located.sz_bot) & np.isfinite(located.sz_top) & located.sz_top.gt(located.sz_bot)
    located["u"] = (located.plate_x + 17/24) / (17/12)
    located["v"] = (located.plate_z - located.sz_bot.where(valid_height, 1.5)) / (located.sz_top.where(valid_height, 3.5) - located.sz_bot.where(valid_height, 1.5))
    heatmap.update(located_pitches=len(located), missing_location_pitches=len(sample)-len(located), zone_height_fallback_pitches=int((~valid_height).sum()))
    # Partition exactly once. Outer groups retain all locations, displayed as halo.
    located["_c"] = np.where(located.u.lt(0), -1, np.where(located.u.gt(1), 3, np.minimum(2, np.floor(located.u*3)))).astype(int)
    located["_r"] = np.where(located.v.lt(0), -1, np.where(located.v.gt(1), 3, np.minimum(2, np.floor(located.v*3)))).astype(int)
    targets = []
    for r in range(-1,4):
        for c in range(-1,4):
            inside = 0 <= r <= 2 and 0 <= c <= 2
            if not inside and (r in (0,1,2) and r != 0 or c in (0,1,2) and c != 0):
                continue
            rm = located._r.eq(r) if inside or r in (-1,3) else located._r.between(0,2)
            cm = located._c.eq(c) if inside or c in (-1,3) else located._c.between(0,2)
            cell = located[rm & cm]
            x0,x1 = (c/3,(c+1)/3) if inside else (-.5,0) if c==-1 else (1,1.5) if c==3 else (0,1)
            y0,y1 = (r/3,(r+1)/3) if inside else (-.5,0) if r==-1 else (1,1.5) if r==3 else (0,1)
            n, sw = len(cell), int(cell._is_swing.sum())
            tracked = cell[cell.events.ne("") & cell.events.ne("truncated_pa") & cell._description_norm.isin(IN_PLAY_EVENTS) & np.isfinite(cell.launch_speed) & cell.launch_speed.gt(0)]
            pairs = {"swing":(sw,n), "contact":(int(cell._is_contact.sum()),sw), "whiff":(int(cell._is_whiff.sum()),sw),
                     "called_strike":(int(cell._is_called_strike.sum()),n), "hard_hit":(int(tracked.launch_speed.ge(95).sum()),len(tracked))}
            rates = {k:dict(numerator=a, denominator=b, value=100*a/b if b else None) for k,(a,b) in pairs.items()}
            label = f"Zone row {3-r}, col {c+1}" if inside else f"Outside {r}:{c}"
            heatmap["cells"].append(dict(id=f"{'zone' if inside else 'outside'}-{r}-{c}", label=label, region="zone" if inside else "outside", bounds=(x0,y0,x1,y1), pitches=n, rates=rates))
            if sw >= 3:
                targets.append(dict(u=(x0+x1)/2, v=(y0+y1)/2, zone=label, swings=sw, located_swings=int(located._is_swing.sum())))
    ready = pa > 30 and len(sample) >= MIN_CONTEXT
    counts = sample[sample._is_swing]._family.value_counts()
    candidates = [dict(family=k, swings=int(v), share_pct=100*int(v)/swings) for k,v in counts.items() if k != "Unknown"][:3] if swings else []
    return PitchScoutResponse(before_date=before, status="ready" if ready else "unavailable" if rows is None else "insufficient_history",
        tier=tier, context_pitches=len(sample), swing_count=swings, swing_pct=100*swings/len(sample) if ready else None,
        take_pct=100*(len(sample)-swings)/len(sample) if ready else None, candidates=candidates if ready else [],
        target=max(targets,key=lambda t:t["swings"]) if ready and targets else None,
        heatmap=BatterZoneRatesResponse(**heatmap), source_version=source)


@lru_cache(maxsize=256)
def _context(path, stamp, size, year, batter_id, hand, stand, before, balls, strikes, previous_type, previous_result):
    return build_context(read_history(path,stamp,size,batter_id),year,batter_id,hand,stand,before,balls,strikes,previous_type,previous_result,f"context_v1:{stamp}:{size}")


def get_pitch_scout(year, batter_id, hand, stand, before, balls, strikes, previous_type, previous_result):
    path = get_season_duckdb_path(year, settings.data_dir)
    if not path.exists():
        return build_context(None,year,batter_id,hand,stand,before,balls,strikes,previous_type,previous_result)
    stat = path.stat()
    wal = path.with_suffix(path.suffix+".wal")
    w = wal.stat() if wal.exists() else None
    return _context(str(path),max(stat.st_mtime_ns,w.st_mtime_ns if w else 0),stat.st_size+(w.st_size if w else 0),year,batter_id,hand,stand,before,balls,strikes,previous_type,previous_result)
