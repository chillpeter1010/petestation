from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from app.api.schemas.batter_swing_timing import SwingTimingLeaderboardRow, SwingTimingPitchProfile
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path
from app.services.batter_service import list_batter_leaderboard


WHIFF_DESCRIPTIONS = {"swinging_strike", "swinging_strike_blocked", "swinging_pitchout"}
BUNT_DESCRIPTIONS = {"foul_bunt", "missed_bunt", "bunt_foul_tip"}


def filtered_batting_metrics(
    year: int, pitch_codes: set[str] | None = None, pitcher_hand: str = "All",
    batter_side: str = "All", batter_team: str = "All", pitcher_team: str = "All",
    data_dir: Path | None = None,
) -> dict[int, dict]:
    """Tracking uses swings; K/BB use terminal PAs, including untracked takes."""
    path = get_season_duckdb_path(year, Path(data_dir or settings.data_dir))
    if not path.exists():
        return {}
    stat = path.stat()
    wal = path.with_suffix(path.suffix + ".wal")
    wal_stamp = wal.stat().st_mtime_ns if wal.exists() else 0
    return _cached_filtered_batting_metrics(
        str(path.resolve()), stat.st_mtime_ns, stat.st_size, wal_stamp,
        tuple(sorted(pitch_codes or ())), pitcher_hand, batter_side, batter_team, pitcher_team,
    )


@lru_cache(maxsize=32)
def _cached_filtered_batting_metrics(
    path: str, modified_at: int, size: int, wal_stamp: int, pitch_codes: tuple[str, ...],
    pitcher_hand: str, batter_side: str, batter_team: str, pitcher_team: str,
) -> dict[int, dict]:
    with duckdb.connect(path, read_only=True) as conn:
        table = _pitch_table(conn)
        columns = _columns(conn, table)
        required = {"game_type", "game_pk", "at_bat_number", "pitch_number", "events", "description", "pitch_type"}
        if not table or not required.issubset(columns):
            return {}
        batter_column = "batter_id" if "batter_id" in columns else "batter"
        optional = ["bat_speed", "attack_angle", "launch_speed", "p_throws", "stand", "batter_team", "pitcher_team"]
        fields = ", ".join(column if column in columns else f"NULL AS {column}" for column in optional)
        conditions, params = [], []
        if pitch_codes:
            conditions.append(f"pitch_type IN ({','.join('?' for _ in pitch_codes)})")
            params.extend(pitch_codes)
        for column, value in (("p_throws", pitcher_hand), ("stand", batter_side), ("batter_team", batter_team), ("pitcher_team", pitcher_team)):
            if value != "All":
                conditions.append(f"{column} = ?")
                params.append(value)
        where = " AND ".join(conditions) or "TRUE"
        frame = conn.execute(f"""
            WITH season AS (
                SELECT CAST({batter_column} AS BIGINT) AS batter_id, game_pk, at_bat_number, pitch_number,
                       pitch_type, LOWER(TRIM(COALESCE(description, ''))) AS description,
                       LOWER(TRIM(COALESCE(events, ''))) AS events, {fields}
                FROM {table} WHERE game_type = 'R'
                QUALIFY ROW_NUMBER() OVER (PARTITION BY game_pk, at_bat_number, pitch_number ORDER BY {batter_column}) = 1
            ), swings AS (
                SELECT * FROM season WHERE description IN (
                    'swinging_strike', 'swinging_strike_blocked', 'swinging_pitchout',
                    'foul', 'foul_tip', 'hit_into_play', 'hit_into_play_no_out', 'hit_into_play_score'
                )
            ), baseline AS (
                SELECT batter_id, QUANTILE_CONT(bat_speed, 0.10) AS p10 FROM swings GROUP BY batter_id
            ), tracked AS (
                SELECT swings.* FROM swings WHERE {where}
            ), tracking AS (
                SELECT t.batter_id,
                       AVG(bat_speed) FILTER (WHERE bat_speed >= p10 OR (bat_speed >= 60 AND launch_speed >= 90)) AS avg_bat_speed,
                       COUNT(bat_speed) FILTER (WHERE bat_speed >= p10 OR (bat_speed >= 60 AND launch_speed >= 90)) AS bat_speed_swings,
                       100.0 * COUNT(*) FILTER (WHERE attack_angle BETWEEN 5 AND 20) / NULLIF(COUNT(attack_angle), 0) AS ideal_attack_angle_pct,
                       COUNT(attack_angle) AS attack_angle_swings
                FROM tracked t LEFT JOIN baseline b USING (batter_id) GROUP BY t.batter_id
            ), terminal AS (
                SELECT * FROM season WHERE events NOT IN ('', 'truncated_pa')
                QUALIFY ROW_NUMBER() OVER (PARTITION BY game_pk, at_bat_number ORDER BY pitch_number DESC) = 1
            ), outcomes AS (
                SELECT batter_id, COUNT(*) AS context_pa,
                       100.0 * COUNT(*) FILTER (WHERE events IN ('strikeout', 'strikeout_double_play')) / COUNT(*) AS k_pct,
                       100.0 * COUNT(*) FILTER (WHERE events IN ('walk', 'intent_walk')) / COUNT(*) AS bb_pct
                FROM terminal WHERE {where} GROUP BY batter_id
            )
            SELECT COALESCE(t.batter_id, o.batter_id) AS batter_id, t.* EXCLUDE (batter_id),
                   o.* EXCLUDE (batter_id), k_pct - bb_pct AS k_bb_pct
            FROM tracking t FULL OUTER JOIN outcomes o USING (batter_id)
        """, params + params).fetchdf()
    count_fields = {"context_pa", "bat_speed_swings", "attack_angle_swings"}
    return {
        int(row["batter_id"]): {
            key: (int(value) if pd.notna(value) else 0) if key in count_fields else
                 (round(float(value), 3) if pd.notna(value) and np.isfinite(value) else None)
            for key, value in row.items() if key != "batter_id"
        } for row in frame.to_dict("records")
    }


def available_pitcher_teams(year: int, data_dir: Path | None = None) -> list[str]:
    path = get_season_duckdb_path(year, Path(data_dir or settings.data_dir))
    if not path.exists():
        return []
    with duckdb.connect(str(path), read_only=True) as conn:
        table = _pitch_table(conn)
        if not table or "pitcher_team" not in _columns(conn, table):
            return []
        rows = conn.execute(
            f"SELECT DISTINCT TRIM(CAST(pitcher_team AS VARCHAR)) FROM {table} "
            "WHERE pitcher_team IS NOT NULL AND TRIM(CAST(pitcher_team AS VARCHAR)) <> '' ORDER BY 1"
        ).fetchall()
    return [str(row[0]) for row in rows]


def build_matchup_rows(
    year: int,
    pitch_codes: set[str] | None = None,
    pitcher_hand: str = "All",
    batter_side: str = "All",
    batter_team: str = "All",
    pitcher_team: str = "All",
    batter_id: int | None = None,
    data_dir: Path | None = None,
) -> tuple[list[SwingTimingLeaderboardRow], SwingTimingLeaderboardRow | None, int, list[str]]:
    frame, warnings = _load_swings(
        year=year,
        pitch_codes=pitch_codes,
        pitcher_hand=pitcher_hand,
        batter_side=batter_side,
        batter_team=batter_team,
        pitcher_team=pitcher_team,
        batter_id=batter_id,
        data_dir=data_dir,
    )
    if frame.empty:
        return [], None, 0, warnings
    baselines = _season_bat_speed_baselines(year, str(Path(data_dir or settings.data_dir).resolve()))
    identities = _identity_map(year)
    rows = [
        _aggregate_event_group(group, int(player_id), identities.get(int(player_id)), baselines.get(int(player_id)))
        for player_id, group in frame.groupby("batter_id", sort=False)
    ]
    league = _aggregate_event_group(frame, 0, ("MLB", "MLB", None), None)
    return sorted(rows, key=lambda row: (-row.n_swings, row.name)), league, int(len(frame)), warnings


def build_matchup_pitch_profiles(
    year: int,
    batter_id: int,
    pitch_codes: set[str] | None = None,
    pitcher_hand: str = "All",
    batter_side: str = "All",
    pitcher_team: str = "All",
    data_dir: Path | None = None,
) -> tuple[list[SwingTimingPitchProfile], list[str]]:
    frame, warnings = _load_swings(
        year=year,
        pitch_codes=pitch_codes,
        pitcher_hand=pitcher_hand,
        batter_side=batter_side,
        batter_team="All",
        pitcher_team=pitcher_team,
        batter_id=batter_id,
        data_dir=data_dir,
    )
    if frame.empty:
        return [], warnings
    baseline = _season_bat_speed_baselines(year, str(Path(data_dir or settings.data_dir).resolve())).get(int(batter_id))
    profiles = []
    for pitch_type, group in frame.groupby("pitch_type", sort=False):
        row = _aggregate_event_group(group, int(batter_id), None, baseline)
        profiles.append(SwingTimingPitchProfile(
            pitch_type=str(pitch_type),
            pitch_label=str(group["pitch_name"].dropna().iloc[0]) if group["pitch_name"].notna().any() else str(pitch_type),
            n_swings=row.n_swings,
            miss_distance=row.miss_distance,
            whiff_pct=row.whiff_pct,
            competitive_pct=row.competitive_pct,
            avg_bat_speed=row.avg_bat_speed,
            season_bat_speed=row.season_bat_speed,
            bat_speed_delta=row.bat_speed_delta,
            fast_swing_pct=row.fast_swing_pct,
            avg_swing_length=row.avg_swing_length,
            avg_attack_angle=row.avg_attack_angle,
            avg_attack_direction=row.avg_attack_direction,
            avg_swing_path_tilt=row.avg_swing_path_tilt,
        ))
    return sorted(profiles, key=lambda row: -row.n_swings), warnings


def _load_swings(
    year: int,
    pitch_codes: set[str] | None,
    pitcher_hand: str,
    batter_side: str,
    batter_team: str,
    pitcher_team: str,
    batter_id: int | None,
    data_dir: Path | None,
) -> tuple[pd.DataFrame, list[str]]:
    path = get_season_duckdb_path(year, Path(data_dir or settings.data_dir))
    if not path.exists():
        return pd.DataFrame(), [f"No pitch-level cache is available for {year}."]
    with duckdb.connect(str(path), read_only=True) as conn:
        table = _pitch_table(conn)
        columns = _columns(conn, table)
        required = {"bat_speed", "pitch_type", "description", "pitcher_team", "batter_team"}
        if not table or not required.issubset(columns):
            return pd.DataFrame(), [f"The {year} pitch cache does not contain the required Bat Tracking fields."]
        batter_column = "batter_id" if "batter_id" in columns else "batter"
        optional = ["miss_distance", "swing_length", "attack_angle", "attack_direction", "swing_path_tilt", "launch_speed", "pitch_name"]
        select_optional = [f"{column}" if column in columns else f"NULL AS {column}" for column in optional]
        conditions = ["bat_speed IS NOT NULL", f"description NOT IN ({','.join('?' for _ in BUNT_DESCRIPTIONS)})"]
        params: list[object] = list(BUNT_DESCRIPTIONS)
        if pitch_codes:
            conditions.append(f"pitch_type IN ({','.join('?' for _ in pitch_codes)})")
            params.extend(sorted(pitch_codes))
        for column, value in (("p_throws", pitcher_hand), ("stand", batter_side), ("batter_team", batter_team), ("pitcher_team", pitcher_team)):
            if value in {"L", "R"} or (column.endswith("team") and value != "All"):
                conditions.append(f"{column} = ?")
                params.append(value)
        if batter_id is not None:
            conditions.append(f"{batter_column} = ?")
            params.append(int(batter_id))
        query = f"""
            SELECT CAST({batter_column} AS BIGINT) AS batter_id, pitch_type, description,
                   pitcher_team, batter_team, bat_speed, {', '.join(select_optional)}
            FROM {table}
            WHERE {' AND '.join(conditions)}
        """
        frame = conn.execute(query, params).fetchdf()
    warnings = []
    if "miss_distance" not in columns:
        warnings.append(f"Pitch-level Miss Distance is not present in the local {year} cache; other event metrics remain available.")
    return frame, warnings


@lru_cache(maxsize=8)
def _season_bat_speed_baselines(year: int, data_root: str) -> dict[int, tuple[float, float]]:
    path = get_season_duckdb_path(year, Path(data_root))
    if not path.exists():
        return {}
    with duckdb.connect(str(path), read_only=True) as conn:
        table = _pitch_table(conn)
        columns = _columns(conn, table)
        if not table or "bat_speed" not in columns:
            return {}
        batter_column = "batter_id" if "batter_id" in columns else "batter"
        rows = conn.execute(f"""
            WITH tracked AS (
                SELECT CAST({batter_column} AS BIGINT) AS batter_id, bat_speed, launch_speed,
                       QUANTILE_CONT(bat_speed, 0.10) OVER (PARTITION BY {batter_column}) AS p10_speed
                FROM {table}
                WHERE bat_speed IS NOT NULL
                  AND description NOT IN ('foul_bunt', 'missed_bunt', 'bunt_foul_tip')
            )
            SELECT batter_id, p10_speed,
                   AVG(bat_speed) FILTER (WHERE bat_speed >= p10_speed OR (bat_speed >= 60 AND launch_speed >= 90)) AS competitive_avg
            FROM tracked GROUP BY batter_id, p10_speed
        """).fetchall()
    return {int(player_id): (float(p10), float(avg_speed)) for player_id, p10, avg_speed in rows if p10 is not None and avg_speed is not None}


def _aggregate_event_group(
    group: pd.DataFrame,
    batter_id: int,
    identity: tuple[str, str, int | None] | None,
    baseline: tuple[float, float] | None,
) -> SwingTimingLeaderboardRow:
    speeds = pd.to_numeric(group["bat_speed"], errors="coerce")
    p10_speed = baseline[0] if baseline else float(speeds.quantile(0.10))
    season_speed = baseline[1] if baseline else None
    launch_speed = pd.to_numeric(group["launch_speed"], errors="coerce")
    competitive = speeds.ge(p10_speed) | (speeds.ge(60) & launch_speed.ge(90))
    competitive_speed = float(speeds[competitive].mean()) if competitive.any() else None
    whiff = group["description"].isin(WHIFF_DESCRIPTIONS)
    raw_team = str(group["batter_team"].dropna().mode().iloc[0]) if group["batter_team"].notna().any() else "-"
    return SwingTimingLeaderboardRow(
        batter_id=batter_id,
        name=identity[0] if identity else ("MLB" if batter_id == 0 else f"Batter {batter_id}"),
        team=identity[1] if identity and identity[1] not in {"", "-"} else raw_team,
        plate_appearances=identity[2] if identity else None,
        n_swings=int(len(group)),
        pitch_types=sorted(group["pitch_type"].dropna().astype(str).unique().tolist()),
        miss_distance=_mean(group, "miss_distance", mask=whiff),
        whiff_pct=round(float(whiff.mean() * 100), 3),
        competitive_pct=round(float(competitive.mean() * 100), 3),
        avg_bat_speed=round(competitive_speed, 3) if competitive_speed is not None and np.isfinite(competitive_speed) else None,
        season_bat_speed=round(season_speed, 3) if season_speed is not None else None,
        bat_speed_delta=round(competitive_speed - season_speed, 3) if competitive_speed is not None and season_speed is not None else None,
        fast_swing_pct=round(float(speeds.ge(75).mean() * 100), 3),
        avg_swing_length=_mean(group, "swing_length"),
        avg_attack_angle=_mean(group, "attack_angle"),
        avg_attack_direction=_mean(group, "attack_direction"),
        avg_swing_path_tilt=_mean(group, "swing_path_tilt"),
        sample_status="Stable" if len(group) >= 100 else "Developing",
    )


def _mean(group: pd.DataFrame, column: str, mask: pd.Series | None = None) -> float | None:
    if column not in group:
        return None
    values = pd.to_numeric(group[column], errors="coerce")
    if mask is not None:
        values = values[mask]
    value = float(values.mean()) if values.notna().any() else np.nan
    return round(value, 3) if np.isfinite(value) else None


def _identity_map(year: int) -> dict[int, tuple[str, str, int | None]]:
    return {
        int(row["player_id"]): (
            str(row.get("name") or ""),
            str(row.get("team") or "-"),
            int(row["plate_appearances"]) if pd.notna(row.get("plate_appearances")) else None,
        )
        for row in list_batter_leaderboard(year)
        if row.get("player_id")
    }


def _pitch_table(conn: duckdb.DuckDBPyConnection) -> str:
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    return "pitches_enriched" if "pitches_enriched" in tables else ("pitches" if "pitches" in tables else "")


def _columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {row[0] for row in conn.execute(f"DESCRIBE {table}").fetchall()} if table else set()
