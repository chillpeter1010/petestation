from __future__ import annotations

from pathlib import Path
from time import sleep

import duckdb
import pandas as pd


def get_season_duckdb_path(year: int, data_dir: Path) -> Path:
    return data_dir / f"MLB{int(year)}" / f"mlb_{int(year)}.duckdb"


def connect_duckdb_write_with_retry(
    db_path: Path,
    attempts: int = 20,
    retry_delay_seconds: float = 0.5,
) -> duckdb.DuckDBPyConnection:
    """Open a writer after short-lived Windows DuckDB readers release the file."""
    total_attempts = max(1, attempts)
    for attempt in range(total_attempts):
        try:
            return duckdb.connect(str(db_path))
        except duckdb.Error as exc:
            message = str(exc).lower()
            lock_error = "cannot open file" in message or "conflicting lock" in message
            if not lock_error or attempt == total_attempts - 1:
                raise
            sleep(max(0.0, retry_delay_seconds))
    raise RuntimeError(f"Unable to open DuckDB writer: {db_path}")


def available_db_years(data_dir: Path) -> list[int]:
    years: list[int] = []
    for path in data_dir.glob("MLB*/mlb_*.duckdb"):
        parts = path.stem.split("_")
        if parts and parts[-1].isdigit():
            years.append(int(parts[-1]))
    return sorted(set(years), reverse=True)


def load_pitcher_master_and_appearances(year: int, data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    db_path = get_season_duckdb_path(year, data_dir)
    if not db_path.exists():
        return pd.DataFrame(), pd.DataFrame()

    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        if "player_master" not in tables:
            return pd.DataFrame(), pd.DataFrame()

        source_table = "pitches_enriched" if "pitches_enriched" in tables else ("pitches" if "pitches" in tables else "")
        player_master = conn.execute("SELECT * FROM player_master").fetchdf()
        if not source_table:
            return player_master, pd.DataFrame()

        appearance_stats = conn.execute(
            f"""
            WITH pitcher_games AS (
                SELECT
                    pitcher AS player_id,
                    game_pk,
                    pitcher_team AS team,
                    MIN(CAST(at_bat_number AS BIGINT) * 1000 + CAST(pitch_number AS BIGINT)) AS first_pitch_seq
                FROM {source_table}
                WHERE game_type = 'R'
                  AND pitcher IS NOT NULL
                  AND game_pk IS NOT NULL
                  AND at_bat_number IS NOT NULL
                  AND pitch_number IS NOT NULL
                  AND pitcher_team IS NOT NULL
                GROUP BY 1, 2, 3
            ),
            team_games AS (
                SELECT
                    game_pk,
                    pitcher_team AS team,
                    MIN(CAST(at_bat_number AS BIGINT) * 1000 + CAST(pitch_number AS BIGINT)) AS team_first_pitch_seq
                FROM {source_table}
                WHERE game_type = 'R'
                  AND game_pk IS NOT NULL
                  AND at_bat_number IS NOT NULL
                  AND pitch_number IS NOT NULL
                  AND pitcher_team IS NOT NULL
                GROUP BY 1, 2
            )
            SELECT
                pg.player_id,
                COUNT(DISTINCT pg.game_pk) AS G,
                COUNT(DISTINCT CASE WHEN pg.first_pitch_seq = tg.team_first_pitch_seq THEN pg.game_pk END) AS GS,
                COUNT(DISTINCT CASE WHEN pg.first_pitch_seq <> tg.team_first_pitch_seq THEN pg.game_pk END) AS GR
            FROM pitcher_games pg
            JOIN team_games tg
              ON pg.game_pk = tg.game_pk
             AND pg.team = tg.team
            GROUP BY 1
            ORDER BY 1
            """
        ).fetchdf()

    return player_master, appearance_stats


def load_pitcher_latest_teams(year: int, data_dir: Path) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, data_dir)
    if not db_path.exists():
        return pd.DataFrame(columns=["player_id", "team"])

    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = resolve_pitch_table(tables)
        if not source_table:
            return pd.DataFrame(columns=["player_id", "team"])

        teams = conn.execute(
            f"""
            WITH pitcher_team_games AS (
                SELECT
                    pitcher AS player_id,
                    pitcher_team AS team,
                    MAX(game_date) AS last_game_date,
                    COUNT(*) AS pitches
                FROM {source_table}
                WHERE game_type = 'R'
                  AND pitcher IS NOT NULL
                  AND pitcher_team IS NOT NULL
                  AND TRIM(CAST(pitcher_team AS VARCHAR)) <> ''
                GROUP BY 1, 2
            ),
            ranked AS (
                SELECT
                    player_id,
                    team,
                    ROW_NUMBER() OVER (
                        PARTITION BY player_id
                        ORDER BY last_game_date DESC, pitches DESC, team
                    ) AS rn
                FROM pitcher_team_games
            )
            SELECT player_id, team
            FROM ranked
            WHERE rn = 1
            ORDER BY player_id
            """
        ).fetchdf()

    if teams.empty:
        return pd.DataFrame(columns=["player_id", "team"])
    teams["player_id"] = pd.to_numeric(teams["player_id"], errors="coerce")
    teams = teams.dropna(subset=["player_id"]).copy()
    teams["player_id"] = teams["player_id"].astype(int)
    teams["team"] = teams["team"].astype(str)
    return teams.reset_index(drop=True)


def resolve_pitch_table(tables: set[str]) -> str:
    return "pitches_enriched" if "pitches_enriched" in tables else ("pitches" if "pitches" in tables else "")


def load_pitcher_cached_season(
    year: int,
    pitcher_id: int,
    data_dir: Path,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, data_dir)
    if not db_path.exists():
        return pd.DataFrame()

    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = resolve_pitch_table(tables)
        if not source_table:
            return pd.DataFrame()

        where_clauses = ["game_type = 'R'", "pitcher = ?"]
        params: list[object] = [int(pitcher_id)]
        if start_date:
            where_clauses.append("game_date >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("game_date <= ?")
            params.append(end_date)

        cached = conn.execute(
            f"""
            SELECT *
            FROM {source_table}
            WHERE {" AND ".join(where_clauses)}
            ORDER BY game_date, game_pk, at_bat_number, pitch_number
            """,
            params,
        ).fetchdf()

    return cached.reset_index(drop=True)


def load_pitcher_season_date_range(year: int, pitcher_id: int, data_dir: Path) -> dict[str, object]:
    db_path = get_season_duckdb_path(year, data_dir)
    if not db_path.exists():
        return {"start_date": None, "end_date": None, "pitches": 0}

    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = resolve_pitch_table(tables)
        if not source_table:
            return {"start_date": None, "end_date": None, "pitches": 0}

        result = conn.execute(
            f"""
            SELECT
                MIN(game_date) AS start_date,
                MAX(game_date) AS end_date,
                COUNT(*) AS pitches
            FROM {source_table}
            WHERE game_type = 'R'
              AND pitcher = ?
              AND game_date IS NOT NULL
            """,
            [int(pitcher_id)],
        ).fetchone()

    if not result:
        return {"start_date": None, "end_date": None, "pitches": 0}
    start_date, end_date, pitches = result
    return {
        "start_date": str(start_date)[:10] if start_date is not None else None,
        "end_date": str(end_date)[:10] if end_date is not None else None,
        "pitches": int(pitches or 0),
    }


def load_league_pitch_movement(year: int, data_dir: Path) -> pd.DataFrame:
    db_path = get_season_duckdb_path(year, data_dir)
    if not db_path.exists():
        return pd.DataFrame()

    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = resolve_pitch_table(tables)
        if not source_table:
            return pd.DataFrame()

        available = {
            row[1]
            for row in conn.execute(f"PRAGMA table_info('{source_table}')").fetchall()
        }
        required = {"pitch_name", "pfx_x", "pfx_z", "p_throws"}
        if not required.issubset(available):
            return pd.DataFrame()

        columns = ["pitch_name", "pfx_x", "pfx_z", "p_throws"]
        if "release_speed" in available:
            columns.append("release_speed")

        cached = conn.execute(
            f"""
            SELECT {", ".join(columns)}
            FROM {source_table}
            WHERE game_type = 'R'
              AND pitch_name IS NOT NULL
              AND pfx_x IS NOT NULL
              AND pfx_z IS NOT NULL
              AND p_throws IS NOT NULL
            """
        ).fetchdf()

    return cached.reset_index(drop=True)
