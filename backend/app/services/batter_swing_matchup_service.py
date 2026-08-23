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
