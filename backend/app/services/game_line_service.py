from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import duckdb
import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import connect_duckdb_write_with_retry, get_season_duckdb_path, resolve_pitch_table
from app.services.video_service import fetch_json


PITCHING_FIELD_MAP = {
    "ip": "inningsPitched",
    "hits": "hits",
    "runs": "runs",
    "earned_runs": "earnedRuns",
    "walks": "baseOnBalls",
    "strikeouts": "strikeOuts",
    "pitches": "pitchesThrown",
    "batters_faced": "battersFaced",
}
GAME_LINE_COLUMNS = [
    "game_pk",
    "game_date",
    "team",
    "home_away",
    "pitcher_id",
    "pitcher_name",
    *PITCHING_FIELD_MAP.keys(),
]


def fetch_game_boxscore(game_pk: int) -> dict[str, Any]:
    return fetch_json(f"https://statsapi.mlb.com/api/v1/game/{int(game_pk)}/boxscore")


def normalize_pitcher_game_lines(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=GAME_LINE_COLUMNS)
    working = df.copy()
    for column in GAME_LINE_COLUMNS:
        if column not in working.columns:
            working[column] = pd.NA
    for column in ["game_pk", "pitcher_id"]:
        working[column] = pd.to_numeric(working[column], errors="coerce").astype("Int64")
    for column in ["hits", "runs", "earned_runs", "walks", "strikeouts", "pitches", "batters_faced"]:
        working[column] = pd.to_numeric(working[column], errors="coerce").astype("Int64")
    for column in ["game_date", "team", "home_away", "pitcher_name", "ip"]:
        working[column] = working[column].astype("string")
    working = working.dropna(subset=["game_pk", "pitcher_id"])
    working = working.drop_duplicates(subset=["game_pk", "pitcher_id"], keep="last")
    return working[GAME_LINE_COLUMNS].sort_values(["game_date", "game_pk", "team", "pitcher_name"]).reset_index(drop=True)


def load_pitcher_game_lines(year: int, data_dir=settings.data_dir) -> pd.DataFrame:
    """Load the freshest union of the durable CSV and embedded DuckDB cache."""
    csv_path = data_dir / f"MLB{int(year)}" / f"mlb_{int(year)}_pitcher_game_lines.csv.gz"
    csv_lines = pd.read_csv(csv_path, compression="gzip") if csv_path.exists() else pd.DataFrame()
    db_path = get_season_duckdb_path(year, data_dir)
    db_lines = pd.DataFrame()
    if db_path.exists():
        try:
            with duckdb.connect(str(db_path), read_only=True) as conn:
                tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
                if "pitcher_game_lines" in tables:
                    db_lines = conn.execute("SELECT * FROM pitcher_game_lines").fetchdf()
        except duckdb.Error:
            pass
    if csv_lines.empty:
        return normalize_pitcher_game_lines(db_lines)
    if db_lines.empty:
        return normalize_pitcher_game_lines(csv_lines)
    return normalize_pitcher_game_lines(pd.concat([db_lines, csv_lines], ignore_index=True))


def parse_all_pitcher_game_lines(
    payload: dict[str, Any], game_pk: int | None = None, game_date: str | None = None
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for side in ["home", "away"]:
        team_payload = ((payload.get("teams") or {}).get(side) or {})
        team = ((team_payload.get("team") or {}).get("abbreviation") or "").strip()
        players = team_payload.get("players") or {}
        for player in players.values():
            pitching = ((player.get("stats") or {}).get("pitching") or {})
            if not pitching:
                continue
            pitcher_id = (player.get("person") or {}).get("id")
            if pitcher_id is None:
                continue
            if not any(pitching.get(source_key) is not None for source_key in PITCHING_FIELD_MAP.values()):
                continue
            row: dict[str, Any] = {
                "game_pk": int(game_pk) if game_pk is not None else None,
                "game_date": game_date,
                "team": team,
                "home_away": side,
                "pitcher_id": int(pitcher_id),
                "pitcher_name": (player.get("person") or {}).get("fullName"),
            }
            for output_key, source_key in PITCHING_FIELD_MAP.items():
                row[output_key] = pitching.get(source_key)
            rows.append(row)
    return normalize_pitcher_game_lines(pd.DataFrame(rows, columns=GAME_LINE_COLUMNS))


def parse_pitcher_game_line(payload: dict[str, Any], pitcher_id: int) -> dict[str, Any] | None:
    player_key = f"ID{int(pitcher_id)}"
    for side in ["home", "away"]:
        team_payload = ((payload.get("teams") or {}).get(side) or {})
        player = (team_payload.get("players") or {}).get(player_key)
        if not player:
            continue
        pitching = ((player.get("stats") or {}).get("pitching") or {})
        if not pitching:
            return None
        line: dict[str, Any] = {
            "pitcher_id": int(pitcher_id),
            "pitcher_name": (player.get("person") or {}).get("fullName"),
            "team": ((team_payload.get("team") or {}).get("abbreviation") or "").strip(),
            "home_away": side,
        }
        for output_key, source_key in PITCHING_FIELD_MAP.items():
            line[output_key] = pitching.get(source_key)
        return line
    return None


def load_cached_pitcher_game_line(
    year: int, game_pk: int, pitcher_id: int, data_dir=settings.data_dir
) -> dict[str, Any] | None:
    db_path = get_season_duckdb_path(year, data_dir)
    if not db_path.exists():
        return None
    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        if "pitcher_game_lines" not in tables:
            return None
        row = conn.execute(
            """
            SELECT *
            FROM pitcher_game_lines
            WHERE game_pk = ? AND pitcher_id = ?
            LIMIT 1
            """,
            [int(game_pk), int(pitcher_id)],
        ).fetchdf()
    if row.empty:
        return None
    return row.iloc[0].to_dict()


def load_official_pitcher_game_line(
    game_pk: int,
    pitcher_id: int,
    year: int | None = None,
    data_dir=settings.data_dir,
) -> dict[str, Any] | None:
    if year is not None:
        cached = load_cached_pitcher_game_line(year=year, game_pk=game_pk, pitcher_id=pitcher_id, data_dir=data_dir)
        if cached:
            return cached
    return parse_pitcher_game_line(fetch_game_boxscore(game_pk), pitcher_id)


def clean_pitcher_game_line(line: dict[str, Any] | None) -> dict[str, Any]:
    if not line:
        return {}

    cleaned = dict(line)
    for key in ["hits", "runs", "earned_runs", "walks", "strikeouts", "pitches", "batters_faced"]:
        value = pd.to_numeric(pd.Series([cleaned.get(key)]), errors="coerce").iloc[0]
        cleaned[key] = int(value) if pd.notna(value) else None
    if cleaned.get("ip") is not None and pd.notna(cleaned.get("ip")):
        cleaned["ip"] = str(cleaned["ip"])
    return cleaned


def persist_pitcher_game_lines(year: int, data_dir, lines: pd.DataFrame, all_game_pks: list[int], failures: list[int]) -> dict[str, Any]:
    target_dir = data_dir / f"MLB{int(year)}"
    db_path = get_season_duckdb_path(year, data_dir)
    csv_path = target_dir / f"mlb_{int(year)}_pitcher_game_lines.csv.gz"
    meta_path = target_dir / f"mlb_{int(year)}_pitcher_game_lines_meta.json"
    target_dir.mkdir(parents=True, exist_ok=True)

    lines = normalize_pitcher_game_lines(lines)
    lines.to_csv(csv_path, index=False, compression="gzip")
    with connect_duckdb_write_with_retry(db_path) as conn:
        conn.register("pitcher_game_lines_df", lines)
        conn.execute("CREATE OR REPLACE TABLE pitcher_game_lines AS SELECT * FROM pitcher_game_lines_df")
        conn.unregister("pitcher_game_lines_df")
        try:
            conn.execute("CREATE INDEX idx_pitcher_game_lines_game_pitcher ON pitcher_game_lines(game_pk, pitcher_id)")
        except Exception:
            pass

    meta = {
        "season_year": int(year),
        "all_games": len(all_game_pks),
        "completed_games": int(lines["game_pk"].nunique()) if not lines.empty else 0,
        "pitcher_game_line_rows": int(len(lines)),
        "failed_games": sorted(set(int(game_pk) for game_pk in failures)),
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "csv_path": str(csv_path),
        "duckdb_path": str(db_path),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def backfill_pitcher_game_lines(
    year: int = 2026,
    max_games: int | None = None,
    batch_size: int = 50,
    data_dir=settings.data_dir,
) -> dict[str, Any]:
    db_path = get_season_duckdb_path(year, data_dir)
    if not db_path.exists():
        raise RuntimeError(f"DuckDB not found: {db_path}")

    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = resolve_pitch_table(tables)
        if not source_table:
            raise RuntimeError(f"No pitch table found in {db_path}")
        games_df = conn.execute(
            f"""
            SELECT game_pk, MIN(CAST(game_date AS DATE)) AS game_date
            FROM {source_table}
            WHERE game_type = 'R' AND game_pk IS NOT NULL
            GROUP BY 1
            ORDER BY 2, 1
            """
        ).fetchdf()
        cached = conn.execute("SELECT * FROM pitcher_game_lines").fetchdf() if "pitcher_game_lines" in tables else pd.DataFrame()

    csv_path = data_dir / f"MLB{int(year)}" / f"mlb_{int(year)}_pitcher_game_lines.csv.gz"
    if csv_path.exists():
        cached = pd.concat([cached, pd.read_csv(csv_path, compression="gzip")], ignore_index=True)

    all_game_pks = pd.to_numeric(games_df["game_pk"], errors="coerce").dropna().astype(int).tolist()
    game_dates = dict(zip(games_df["game_pk"].astype(int), games_df["game_date"].astype(str), strict=False))
    lines = normalize_pitcher_game_lines(cached)
    cached_game_pks = set(lines["game_pk"].dropna().astype(int).unique().tolist()) if not lines.empty else set()
    missing_game_pks = [game_pk for game_pk in all_game_pks if game_pk not in cached_game_pks]
    if max_games is not None:
        missing_game_pks = missing_game_pks[: max(max_games, 0)]

    failures: list[int] = []
    pending_frames: list[pd.DataFrame] = []
    for idx, game_pk in enumerate(missing_game_pks, start=1):
        try:
            payload = fetch_game_boxscore(int(game_pk))
            game_lines = parse_all_pitcher_game_lines(payload, game_pk=int(game_pk), game_date=game_dates.get(int(game_pk)))
            if not game_lines.empty:
                pending_frames.append(game_lines)
        except Exception:
            failures.append(int(game_pk))

        if idx % max(batch_size, 1) == 0:
            if pending_frames:
                lines = normalize_pitcher_game_lines(pd.concat([lines, *pending_frames], ignore_index=True))
                pending_frames = []
            persist_pitcher_game_lines(year=year, data_dir=data_dir, lines=lines, all_game_pks=all_game_pks, failures=failures)

    if pending_frames:
        lines = normalize_pitcher_game_lines(pd.concat([lines, *pending_frames], ignore_index=True))
    return persist_pitcher_game_lines(year=year, data_dir=data_dir, lines=lines, all_game_pks=all_game_pks, failures=failures)


def get_pitcher_game_line_status(year: int = 2026, data_dir=settings.data_dir) -> dict[str, Any]:
    db_path = get_season_duckdb_path(year, data_dir)
    target_dir = data_dir / f"MLB{int(year)}"
    meta_path = target_dir / f"mlb_{int(year)}_pitcher_game_lines_meta.json"
    status: dict[str, Any] = {
        "year": int(year),
        "duckdb_path": str(db_path),
        "exists": db_path.exists(),
        "meta_path": str(meta_path),
        "meta": None,
    }
    if meta_path.exists():
        try:
            status["meta"] = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            status["meta"] = {"error": "invalid_json"}
    if not db_path.exists():
        return status
    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = resolve_pitch_table(tables)
        status["has_pitcher_game_lines"] = "pitcher_game_lines" in tables
        if source_table:
            source_games = conn.execute(
                f"""
                SELECT COUNT(DISTINCT game_pk), MAX(CAST(game_date AS DATE))
                FROM {source_table}
                WHERE game_type = 'R' AND game_pk IS NOT NULL
                """
            ).fetchone()
            status["source_games"] = int(source_games[0] or 0)
            status["latest_source_game_date"] = str(source_games[1])[:10] if source_games[1] is not None else None
        if "pitcher_game_lines" in tables:
            cached = conn.execute(
                """
                SELECT COUNT(*), COUNT(DISTINCT game_pk), COUNT(DISTINCT pitcher_id)
                FROM pitcher_game_lines
                """
            ).fetchone()
            status["line_rows"] = int(cached[0] or 0)
            status["line_games"] = int(cached[1] or 0)
            status["line_pitchers"] = int(cached[2] or 0)
    return status
