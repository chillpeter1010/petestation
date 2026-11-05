"""Compact regular-season exact-count splits for shared historical In game views."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import math
import duckdb
import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.discipline_service import add_discipline_flags, summarize_discipline_group, HIT_EVENTS, NON_AB_EVENTS, IN_PLAY_EVENTS


def _name(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.isdigit() or text.lower() in {"unknown", "unknown batter", "unknown pitcher", "nan", "none"} or text.lower().startswith(("batter ", "pitcher ", "player ")):
        return None
    return " ".join(reversed([p.strip() for p in text.split(",", 1)])) if "," in text else text


def _names(conn: duckdb.DuckDBPyConnection, ids: tuple[int, ...], tables: set[str]) -> dict[int, str]:
    names: dict[int, str] = {}
    for table in ("game_player_lookup", "player_master"):
        if table not in tables:
            continue
        columns = {r[0] for r in conn.execute(f"DESCRIBE {table}").fetchall()}
        if not {"player_id", "player_name"} <= columns:
            continue
        for player_id, name in conn.execute(f"SELECT player_id, player_name FROM {table} WHERE try_cast(player_id AS BIGINT) IN ({','.join('?' for _ in ids)})", list(ids)).fetchall():
            if resolved := _name(name):
                names[int(player_id)] = resolved
    return names


def resolve_replay_names(year: int, ids: tuple[int, ...]) -> dict[int, str]:
    path = get_season_duckdb_path(year, settings.data_dir)
    if not path.exists() or not ids:
        return {}
    with duckdb.connect(str(path), read_only=True) as conn:
        names = _names(conn, ids, {r[0] for r in conn.execute("SHOW TABLES").fetchall()})
    if len(names) < len(set(ids)):
        from app.services.batter_service import _load_batter_timing_name_map
        for player_id, name in _load_batter_timing_name_map(year).items():
            if player_id in ids and player_id not in names and (resolved := _name(name)):
                names[player_id] = resolved
    return names


def _number(value: object) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def _summary(frame: pd.DataFrame, total: int, pitch: str) -> dict:
    rates = summarize_discipline_group(frame, pitch)
    terminal = frame[frame["_terminal"]]
    ab = terminal[~terminal["_events_norm"].isin(NON_AB_EVENTS)]
    woba = terminal[terminal["woba_value"].notna() & terminal["woba_denom"].gt(0)]
    bbe = terminal[terminal["_description_norm"].isin(IN_PLAY_EVENTS) & terminal["launch_speed"].gt(0)]
    swings = int(frame["_is_swing"].sum())
    return {"pitch": pitch, "pitches": len(frame), "usage_pct": 100 * len(frame) / total if total else None,
            "velocity": _number(frame.loc[frame["release_speed"].gt(0), "release_speed"].mean()),
            "strike_pct": _number(rates["Strike%"]), "zone_pct": _number(rates["Zone%"]),
            "swing_pct": _number(rates["Swing%"]), "contact_pct": _number(rates["Contact%"]), "whiff_pct": _number(rates["Whiff%"]),
            "avg": float(ab["_events_norm"].isin(HIT_EVENTS).sum()) / len(ab) if len(ab) else None,
            "woba": float(woba["woba_value"].sum()) / float(woba["woba_denom"].sum()) if len(woba) else None,
            "hard_hit_pct": 100 * int(bbe["launch_speed"].ge(95).sum()) / len(bbe) if len(bbe) else None,
            "denominators": {"pitches": len(frame), "swings": swings, "ab": len(ab), "woba": float(woba["woba_denom"].sum()), "tracked_bbe": len(bbe)},
            "sample_status": "limited" if len(frame) < 30 else "available"}


def aggregate_matchup(rows: pd.DataFrame, *, year: int, pitcher_id: int, batter_id: int, batter_side: str, pitcher_hand: str, balls: int, strikes: int) -> dict:
    data = rows.copy().reset_index(drop=True)
    for key in ("pitcher", "batter", "game_pk", "at_bat_number", "pitch_number", "balls", "strikes", "release_speed", "launch_speed", "woba_value", "woba_denom"):
        data[key] = pd.to_numeric(data[key] if key in data else pd.Series(index=data.index, dtype=float), errors="coerce").replace([float("inf"),float("-inf")],float("nan"))
    for key in ("events", "description", "stand", "p_throws", "pitch_type", "pitch_name"):
        data[key] = data[key].fillna("").astype(str).str.strip() if key in data else ""
    events = data["events"].str.lower()
    terminal = data[events.ne("") & events.ne("truncated_pa")].sort_values("pitch_number", kind="stable").drop_duplicates(["game_pk", "at_bat_number"], keep="last").index
    data["_terminal"] = data.index.isin(terminal)
    data = add_discipline_flags(data)
    data = data[data["balls"].eq(balls) & data["strikes"].eq(strikes)]
    groups = {}
    for role, mask, known in (
        ("pitcher", data["pitcher"].eq(pitcher_id) & data["stand"].str.upper().eq(batter_side), batter_side in {"L", "R"}),
        ("batter", data["batter"].eq(batter_id) & data["p_throws"].str.upper().eq(pitcher_hand), pitcher_hand in {"L", "R"}),
    ):
        split = data[mask] if known else data.iloc[:0]
        pitch_rows = []
        for code, frame in split.groupby("pitch_type", sort=False, dropna=False):
            names = frame["pitch_name"].replace("", pd.NA).dropna()
            pitch_rows.append(_summary(frame, len(split), str(names.iloc[0]) if len(names) else str(code) or "Unknown"))
        groups[role] = {"status": "unknown_hand" if not known else "ready" if len(split) else "no_data", "summary": _summary(split, len(split), "All"), "pitches": sorted(pitch_rows, key=lambda r: -r["pitches"])}
    return {"contract_version": "in_game_count_matchup_v1", "year": year, "scope": "regular_season_exact_pre_pitch_count", "count": f"{balls}-{strikes}", "pitcher_id": pitcher_id, "batter_id": batter_id, "batter_side": batter_side, "pitcher_hand": pitcher_hand, **groups}


@lru_cache(maxsize=128)
def _cached(path: str, revision: tuple[int, int], year: int, pitcher_id: int, batter_id: int, side: str, hand: str, balls: int, strikes: int) -> dict:
    del revision
    columns = ("pitcher", "batter", "game_pk", "at_bat_number", "pitch_number", "balls", "strikes", "stand", "p_throws", "pitch_type", "pitch_name", "description", "events", "release_speed", "zone", "plate_x", "plate_z", "sz_bot", "sz_top", "launch_speed", "woba_value", "woba_denom")
    with duckdb.connect(path, read_only=True) as conn:
        table = resolve_pitch_table({r[0] for r in conn.execute("SHOW TABLES").fetchall()})
        available = {r[0] for r in conn.execute(f"DESCRIBE {table}").fetchall()} if table else set()
        if not {"pitcher", "batter", "game_type"} <= available:
            frame = pd.DataFrame()
        else:
            fields = ",".join(f'"{key}"' if key in available else f'NULL AS "{key}"' for key in columns)
            frame = conn.execute(f"SELECT {fields} FROM {table} WHERE game_type='R' AND (pitcher=? OR batter=?)", [pitcher_id, batter_id]).fetchdf()
    return {**aggregate_matchup(frame, year=year, pitcher_id=pitcher_id, batter_id=batter_id, batter_side=side, pitcher_hand=hand, balls=balls, strikes=strikes), "source_status":"available" if {"pitcher","batter","game_type"} <= available else "unavailable"}


def get_pitch_matchup(year: int, pitcher_id: int, batter_id: int, side: str, hand: str, balls: int, strikes: int) -> dict:
    path = get_season_duckdb_path(year, settings.data_dir)
    if path.exists():
        stat = path.stat(); wal = Path(str(path) + ".wal")
        wal_stat = wal.stat() if wal.exists() else None
        result = _cached(str(path), (max(stat.st_mtime_ns, wal_stat.st_mtime_ns if wal_stat else 0), stat.st_size + (wal_stat.st_size if wal_stat else 0)), year, pitcher_id, batter_id, side, hand, balls, strikes)
    else:
        result = {**aggregate_matchup(pd.DataFrame(), year=year, pitcher_id=pitcher_id, batter_id=batter_id, batter_side=side, pitcher_hand=hand, balls=balls, strikes=strikes),"source_status":"unavailable"}
    names = resolve_replay_names(year, (pitcher_id, batter_id))
    return {**result, "pitcher_name": names.get(pitcher_id), "batter_name": names.get(batter_id)}
