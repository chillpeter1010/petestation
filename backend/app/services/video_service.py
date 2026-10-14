from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import connect_duckdb_write_with_retry, get_season_duckdb_path, resolve_pitch_table


SPORTY_VIDEO_BASE = "https://baseballsavant.mlb.com/sporty-videos?playId="
SPORTY_MP4_PATTERN = re.compile(
    r'<source\s+src="(?P<url>https://[^"]+\.mp4[^"]*)"\s+type="video/mp4"',
    re.IGNORECASE,
)
SPORTY_TITLE_PATTERN = re.compile(r"<h3>(?P<title>.*?)</h3>", re.IGNORECASE | re.DOTALL)
VIDEO_LOOKUP_COLUMNS = ["game_pk", "at_bat_number", "pitch_number", "play_id", "video_url", "pitcher", "batter"]


def disable_proxies() -> None:
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
        os.environ[key] = ""


def fetch_json(url: str, timeout: int = 30) -> dict[str, Any]:
    disable_proxies()
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str, timeout: int = 30) -> str:
    disable_proxies()
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_game_playbyplay(game_pk: int) -> dict[str, Any]:
    return fetch_json(f"https://statsapi.mlb.com/api/v1/game/{int(game_pk)}/playByPlay")


def build_playbyplay_pitch_map(game_pk: int, payload: dict[str, Any] | None = None) -> pd.DataFrame:
    data = payload or fetch_game_playbyplay(game_pk)
    rows: list[dict[str, Any]] = []
    for play in data.get("allPlays", []) or []:
        at_bat_index = (play.get("about") or {}).get("atBatIndex")
        at_bat_number = int(at_bat_index) + 1 if at_bat_index is not None else None
        matchup = play.get("matchup") or {}
        pitcher = (matchup.get("pitcher") or {}).get("id")
        batter = (matchup.get("batter") or {}).get("id")
        for event in play.get("playEvents", []) or []:
            if not event.get("isPitch"):
                continue
            play_id = event.get("playId")
            rows.append(
                {
                    "game_pk": int(game_pk),
                    "at_bat_number": at_bat_number,
                    "pitch_number": event.get("pitchNumber"),
                    "play_id": play_id,
                    "video_url": f"{SPORTY_VIDEO_BASE}{play_id}" if play_id else None,
                    "pitcher": pitcher,
                    "batter": batter,
                }
            )
    return pd.DataFrame(rows, columns=VIDEO_LOOKUP_COLUMNS)


def fetch_sporty_video_metadata(play_id: str, timeout: int = 30) -> dict[str, Any]:
    sporty_url = f"{SPORTY_VIDEO_BASE}{play_id}"
    html = fetch_text(sporty_url, timeout=timeout)
    mp4_match = SPORTY_MP4_PATTERN.search(html)
    title_match = SPORTY_TITLE_PATTERN.search(html)
    title = re.sub(r"\s+", " ", title_match.group("title")).strip() if title_match else None
    return {
        "play_id": play_id,
        "video_url": sporty_url,
        "direct_video_url": mp4_match.group("url") if mp4_match else None,
        "title": title,
    }


def extract_game_player_rows(game_pk: int, payload: dict[str, Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for play in payload.get("allPlays", []) or []:
        matchup = play.get("matchup") or {}
        for role in ["pitcher", "batter"]:
            player = matchup.get(role) or {}
            if player.get("id") and player.get("fullName"):
                rows.append(
                    {
                        "game_pk": int(game_pk),
                        "player_id": int(player["id"]),
                        "player_name": str(player["fullName"]).strip(),
                        "role": role,
                    }
                )
    return rows


def normalize_pitch_lookup(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=VIDEO_LOOKUP_COLUMNS)
    working = df.copy()
    for col in ["game_pk", "at_bat_number", "pitch_number", "pitcher", "batter"]:
        if col in working.columns:
            working[col] = pd.to_numeric(working[col], errors="coerce").astype("Int64")
    working["play_id"] = working.get("play_id", pd.Series(index=working.index, dtype="object")).astype(str).replace("nan", pd.NA)
    working["video_url"] = working.get("video_url", pd.Series(index=working.index, dtype="object")).astype(str).replace("nan", pd.NA)
    working = working.dropna(subset=["game_pk", "at_bat_number", "pitch_number"])
    working = working.drop_duplicates(subset=["game_pk", "at_bat_number", "pitch_number"], keep="last")
    return working.sort_values(["game_pk", "at_bat_number", "pitch_number"]).reset_index(drop=True)


def normalize_game_player_lookup(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["game_pk", "player_id", "player_name", "role"])
    working = df.copy()
    for col in ["game_pk", "player_id"]:
        if col in working.columns:
            working[col] = pd.to_numeric(working[col], errors="coerce").astype("Int64")
    working["player_name"] = working.get("player_name", pd.Series(index=working.index, dtype="object")).astype(str).str.strip()
    working["role"] = working.get("role", pd.Series(index=working.index, dtype="object")).astype(str).str.strip().str.lower()
    working = working.dropna(subset=["game_pk", "player_id"])
    working = working.drop_duplicates(subset=["game_pk", "player_id", "role"], keep="last")
    return working.sort_values(["game_pk", "role", "player_name"]).reset_index(drop=True)


def sync_official_player_names(conn: duckdb.DuckDBPyConnection) -> int:
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    base_tables = {row[0] for row in conn.execute("SELECT table_name FROM duckdb_tables()").fetchall()}
    if "game_player_lookup" not in tables:
        return 0
    conn.execute(
        """
        CREATE OR REPLACE TEMP VIEW official_player_names AS
        SELECT player_id, arg_max(trim(player_name), game_pk) AS player_name
        FROM game_player_lookup
        WHERE player_id IS NOT NULL
          AND lower(trim(player_name)) NOT IN ('', 'unknown', 'unknown batter', 'unknown pitcher')
        GROUP BY player_id
        """
    )
    repaired = 0
    for table in ("player_master", "batters_only", "pitchers_only", "player_team_stints"):
        if table not in base_tables:
            continue
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()}
        if not {"player_id", "player_name"}.issubset(columns):
            continue
        invalid_name = """
            target.player_name IS NULL
            OR lower(trim(target.player_name)) IN ('', 'unknown', 'unknown batter', 'unknown pitcher')
            OR lower(trim(target.player_name)) LIKE 'batter %'
            OR lower(trim(target.player_name)) LIKE 'pitcher %'
        """
        repaired += int(
            conn.execute(
                f"""
                SELECT count(*)
                FROM {table} target
                JOIN official_player_names source USING (player_id)
                WHERE {invalid_name}
                """
            ).fetchone()[0]
        )
        name_source_update = ", name_source = 'game_player_lookup'" if "name_source" in columns else ""
        conn.execute(
            f"""
            UPDATE {table} AS target
            SET player_name = source.player_name{name_source_update}
            FROM official_player_names source
            WHERE target.player_id = source.player_id
              AND ({invalid_name})
            """
        )
    return repaired


def persist_video_lookup_outputs(
    year: int,
    data_dir: Path,
    pitch_lookup: pd.DataFrame,
    game_player_lookup: pd.DataFrame,
    all_game_pks: list[int],
    requested_games: int,
    failures: list[int],
) -> dict[str, object]:
    target_dir = data_dir / f"MLB{int(year)}"
    db_path = get_season_duckdb_path(year, data_dir)
    pitch_lookup_path = target_dir / f"mlb_{int(year)}_pitch_play_lookup.csv.gz"
    game_player_lookup_path = target_dir / f"mlb_{int(year)}_game_player_lookup.csv.gz"
    meta_path = target_dir / f"mlb_{int(year)}_play_lookup_meta.json"

    target_dir.mkdir(parents=True, exist_ok=True)
    pitch_lookup = normalize_pitch_lookup(pitch_lookup)
    game_player_lookup = normalize_game_player_lookup(game_player_lookup)
    pitch_lookup.to_csv(pitch_lookup_path, index=False, compression="gzip")
    game_player_lookup.to_csv(game_player_lookup_path, index=False, compression="gzip")

    repaired_player_names = 0
    with connect_duckdb_write_with_retry(db_path) as conn:
        conn.register("pitch_lookup_df", pitch_lookup)
        conn.execute("CREATE OR REPLACE TABLE pitch_play_lookup AS SELECT * FROM pitch_lookup_df")
        conn.unregister("pitch_lookup_df")
        conn.register("game_player_lookup_df", game_player_lookup)
        conn.execute("CREATE OR REPLACE TABLE game_player_lookup AS SELECT * FROM game_player_lookup_df")
        conn.unregister("game_player_lookup_df")
        repaired_player_names = sync_official_player_names(conn)

        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = "pitches" if "pitches" in tables else ""
        if source_table:
            conn.execute(
                f"""
                CREATE OR REPLACE VIEW pitches_enriched AS
                SELECT
                    p.*,
                    l.play_id,
                    l.video_url
                FROM {source_table} p
                LEFT JOIN pitch_play_lookup l
                    ON p.game_pk = l.game_pk
                    AND p.at_bat_number = l.at_bat_number
                    AND p.pitch_number = l.pitch_number
                """
            )
        for sql in [
            "CREATE INDEX idx_pitch_play_lookup_game_pk ON pitch_play_lookup(game_pk)",
            "CREATE INDEX idx_pitch_play_lookup_play_id ON pitch_play_lookup(play_id)",
            "CREATE INDEX idx_game_player_lookup_player_id ON game_player_lookup(player_id)",
        ]:
            try:
                conn.execute(sql)
            except Exception:
                continue

    meta = {
        "season_year": int(year),
        "all_games": len(all_game_pks),
        "games_requested": requested_games,
        "completed_games": int(pd.to_numeric(pitch_lookup.get("game_pk"), errors="coerce").dropna().nunique())
        if not pitch_lookup.empty
        else 0,
        "pitch_play_lookup_rows": int(len(pitch_lookup)),
        "game_player_lookup_rows": int(len(game_player_lookup)),
        "repaired_player_names": repaired_player_names,
        "failed_games": sorted(set(int(game_pk) for game_pk in failures)),
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "pitch_lookup_path": str(pitch_lookup_path),
        "game_player_lookup_path": str(game_player_lookup_path),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def get_video_lookup_status(year: int, data_dir: Path | None = None) -> dict[str, object]:
    root = data_dir or settings.data_dir
    db_path = get_season_duckdb_path(year, root)
    target_dir = root / f"MLB{int(year)}"
    meta_path = target_dir / f"mlb_{int(year)}_play_lookup_meta.json"
    status: dict[str, object] = {
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
        status["has_pitch_play_lookup"] = "pitch_play_lookup" in tables
        if source_table and "games" in tables:
            games = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
            latest_game = conn.execute("SELECT MAX(game_date) FROM games").fetchone()[0]
            status["season_games"] = int(games or 0)
            status["latest_game_date"] = str(latest_game)[:10] if latest_game is not None else None
        if "pitch_play_lookup" in tables:
            lookup = conn.execute(
                """
                SELECT
                    COUNT(*) AS rows,
                    COUNT(DISTINCT game_pk) AS games,
                    SUM(CASE WHEN video_url IS NOT NULL AND trim(CAST(video_url AS VARCHAR)) NOT IN ('', 'None', 'nan', 'NaN') THEN 1 ELSE 0 END) AS video_rows
                FROM pitch_play_lookup
                """
            ).fetchone()
            status["lookup_rows"] = int(lookup[0] or 0)
            status["lookup_games"] = int(lookup[1] or 0)
            status["video_rows"] = int(lookup[2] or 0)
    return status


def backfill_video_lookup(
    year: int,
    max_games: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    batch_size: int = 50,
    data_dir: Path | None = None,
) -> dict[str, object]:
    root = data_dir or settings.data_dir
    db_path = get_season_duckdb_path(year, root)
    if not db_path.exists():
        raise RuntimeError(f"DuckDB not found: {db_path}")

    filters: list[str] = []
    params: list[str] = []
    if start_date:
        filters.append("CAST(game_date AS DATE) >= ?")
        params.append(start_date)
    if end_date:
        filters.append("CAST(game_date AS DATE) <= ?")
        params.append(end_date)
    game_sql = "SELECT game_pk, game_date FROM games"
    if filters:
        game_sql += " WHERE " + " AND ".join(filters)
    game_sql += " ORDER BY CAST(game_date AS DATE), game_pk"

    with duckdb.connect(str(db_path), read_only=True) as conn:
        games_df = conn.execute(game_sql, params).fetchdf()
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        cached_pitch_lookup = conn.execute("SELECT * FROM pitch_play_lookup").fetchdf() if "pitch_play_lookup" in tables else pd.DataFrame()
        cached_player_lookup = conn.execute("SELECT * FROM game_player_lookup").fetchdf() if "game_player_lookup" in tables else pd.DataFrame()

    target_dir = root / f"MLB{int(year)}"
    pitch_lookup_path = target_dir / f"mlb_{int(year)}_pitch_play_lookup.csv.gz"
    player_lookup_path = target_dir / f"mlb_{int(year)}_game_player_lookup.csv.gz"
    if pitch_lookup_path.exists():
        cached_pitch_lookup = pd.concat([cached_pitch_lookup, pd.read_csv(pitch_lookup_path)], ignore_index=True)
    if player_lookup_path.exists():
        cached_player_lookup = pd.concat([cached_player_lookup, pd.read_csv(player_lookup_path)], ignore_index=True)

    all_game_pks = pd.to_numeric(games_df["game_pk"], errors="coerce").dropna().astype(int).tolist()
    pitch_lookup = normalize_pitch_lookup(cached_pitch_lookup)
    game_player_lookup = normalize_game_player_lookup(cached_player_lookup)
    cached_pitch_game_pks = (
        pd.to_numeric(pitch_lookup["game_pk"], errors="coerce").dropna().astype(int).unique().tolist()
        if not pitch_lookup.empty
        else []
    )
    cached_player_game_pks = (
        pd.to_numeric(game_player_lookup["game_pk"], errors="coerce").dropna().astype(int).unique().tolist()
        if not game_player_lookup.empty
        else []
    )
    complete_game_pks = set(cached_pitch_game_pks).intersection(cached_player_game_pks)
    missing_game_pks = [game_pk for game_pk in all_game_pks if game_pk not in complete_game_pks]
    if max_games is not None:
        missing_game_pks = missing_game_pks[: max(max_games, 0)]

    failures: list[int] = []
    for idx, game_pk in enumerate(missing_game_pks, start=1):
        try:
            payload = fetch_game_playbyplay(int(game_pk))
            mapped = build_playbyplay_pitch_map(game_pk, payload=payload)
            if not mapped.empty:
                pitch_lookup = normalize_pitch_lookup(pd.concat([pitch_lookup, mapped], ignore_index=True))
            player_rows = extract_game_player_rows(game_pk, payload)
            if player_rows:
                game_player_lookup = normalize_game_player_lookup(
                    pd.concat([game_player_lookup, pd.DataFrame(player_rows)], ignore_index=True)
                )
        except Exception:
            failures.append(int(game_pk))

        if idx % max(batch_size, 1) == 0:
            persist_video_lookup_outputs(
                year, root, pitch_lookup, game_player_lookup, all_game_pks, len(missing_game_pks), failures
            )

    return persist_video_lookup_outputs(
        year, root, pitch_lookup, game_player_lookup, all_game_pks, len(missing_game_pks), failures
    )
