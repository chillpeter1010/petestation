from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table


KEY_COLUMNS = ["game_pk", "at_bat_number", "pitch_number", "pitcher"]
SCORE_COLUMN = "pitch_stuff_plus"


def cache_path(data_dir: Path | None = None) -> Path:
    root = data_dir or settings.data_dir
    return root / "derived" / "pitch_stuff_scores.sqlite3"


def _artifact_version(data_dir: Path | None = None) -> str:
    root = data_dir or settings.data_dir
    metadata_path = root / "models" / "stuff_plus" / "pete_stuff_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return f"{metadata.get('model_version', 'unknown')}::{metadata.get('generated_at', metadata_path.stat().st_mtime_ns)}"


def _connect(data_dir: Path | None = None) -> sqlite3.Connection:
    path = cache_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=60)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS pitch_stuff_scores (
            year INTEGER NOT NULL,
            game_pk INTEGER NOT NULL,
            at_bat_number INTEGER NOT NULL,
            pitch_number INTEGER NOT NULL,
            pitcher INTEGER NOT NULL,
            model_version TEXT NOT NULL,
            pitch_stuff_plus REAL NOT NULL,
            calculated_at TEXT NOT NULL,
            PRIMARY KEY (year, game_pk, at_bat_number, pitch_number, pitcher, model_version)
        );
        CREATE INDEX IF NOT EXISTS idx_pitch_stuff_pitcher
            ON pitch_stuff_scores (year, pitcher, model_version);
        CREATE TABLE IF NOT EXISTS pitch_stuff_pitcher_state (
            year INTEGER NOT NULL,
            pitcher INTEGER NOT NULL,
            model_version TEXT NOT NULL,
            source_rows INTEGER NOT NULL,
            scored_rows INTEGER NOT NULL,
            calculated_at TEXT NOT NULL,
            PRIMARY KEY (year, pitcher, model_version)
        );
        """
    )
    return connection


def _normalized_keys(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty or not set(KEY_COLUMNS).issubset(data.columns):
        return pd.DataFrame(index=data.index)
    keys = data[KEY_COLUMNS].apply(pd.to_numeric, errors="coerce")
    return keys.where(keys.notna())


def load_pitch_stuff_scores(data: pd.DataFrame, data_dir: Path | None = None) -> pd.Series:
    """Return cached per-pitch scores aligned to the input frame."""

    result = pd.Series(np.nan, index=data.index, dtype="float64")
    path = cache_path(data_dir)
    if data.empty or not path.exists() or "game_date" not in data.columns:
        return result
    keys = _normalized_keys(data)
    valid = keys.notna().all(axis=1)
    if not valid.any():
        return result
    years = pd.to_datetime(data.loc[valid, "game_date"], errors="coerce").dt.year
    version = _artifact_version(data_dir)
    with closing(sqlite3.connect(path, timeout=30)) as connection:
        for year in sorted(years.dropna().astype(int).unique()):
            year_mask = valid & pd.to_datetime(data["game_date"], errors="coerce").dt.year.eq(year)
            pitchers = [int(value) for value in sorted(keys.loc[year_mask, "pitcher"].dropna().astype(int).unique())]
            if not pitchers:
                continue
            placeholders = ",".join("?" for _ in pitchers)
            cached = pd.read_sql_query(
                f"""
                SELECT game_pk, at_bat_number, pitch_number, pitcher, pitch_stuff_plus
                FROM pitch_stuff_scores
                WHERE year = ? AND model_version = ? AND pitcher IN ({placeholders})
                """,
                connection,
                params=[int(year), version, *pitchers],
            )
            if cached.empty:
                continue
            lookup = keys.loc[year_mask].copy()
            lookup["_index"] = lookup.index
            merged = lookup.merge(cached, on=KEY_COLUMNS, how="left")
            result.loc[merged["_index"].to_numpy()] = pd.to_numeric(merged[SCORE_COLUMN], errors="coerce").to_numpy()
    return result


def _load_source(year: int, data_dir: Path) -> pd.DataFrame:
    path = get_season_duckdb_path(year, data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Missing season database: {path}")
    with duckdb.connect(str(path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        table = resolve_pitch_table(tables)
        if not table:
            raise RuntimeError(f"No pitch table found in {path}")
        available = {row[1] for row in connection.execute(f"PRAGMA table_info('{table}')").fetchall()}
        required = {
            *KEY_COLUMNS, "game_date", "game_type", "pitch_name", "pitch_type", "p_throws",
            "release_speed", "pfx_x", "pfx_z", "release_spin_rate", "release_extension",
            "release_pos_z", "release_pos_x", "spin_axis", "arm_angle",
        }
        missing = sorted(required - available)
        if missing:
            raise RuntimeError(f"Pitch source is missing Stuff+ columns: {', '.join(missing)}")
        columns = ", ".join(sorted(required - {"game_type"}))
        return connection.execute(
            f"SELECT {columns} FROM {table} WHERE game_type = 'R' AND pitcher IS NOT NULL"
        ).fetchdf()


def refresh_pitch_stuff_scores(
    year: int = 2026,
    data_dir: Path | None = None,
    max_pitchers: int | None = None,
    shard_index: int | None = None,
    shard_count: int | None = None,
) -> dict[str, Any]:
    """Incrementally fill missing pitch keys, with an optional daily work budget."""

    root = data_dir or settings.data_dir
    version = _artifact_version(root)
    source = _load_source(int(year), root)
    source["pitcher"] = pd.to_numeric(source["pitcher"], errors="coerce")
    source = source.dropna(subset=["pitcher"]).copy()
    source["pitcher"] = source["pitcher"].astype(int)
    calculated_at = datetime.now(timezone.utc).isoformat()
    refreshed_pitchers = 0
    written_rows = 0
    skipped_pitchers = 0
    deferred_pitchers = 0
    if shard_index is not None and shard_count is not None:
        if int(shard_count) < 1 or not 0 <= int(shard_index) < int(shard_count):
            raise ValueError("shard_index must be between 0 and shard_count - 1")
        state_name = f"pitch_stuff_backfill_{int(year)}_shard_{int(shard_index)}_of_{int(shard_count)}.json"
    else:
        state_name = f"pitch_stuff_backfill_{int(year)}.json"
    state_path = root / "admin_job_logs" / state_name
    state_path.parent.mkdir(parents=True, exist_ok=True)

    final_metrics: dict[str, Any] = {}

    def write_state(status: str) -> None:
        temporary = state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "status": status,
                    "year": int(year),
                    "source_rows": int(len(source)),
                    "processed_pitchers": refreshed_pitchers + skipped_pitchers,
                    "refreshed_pitchers": refreshed_pitchers,
                    "skipped_pitchers": skipped_pitchers,
                    "deferred_pitchers": deferred_pitchers,
                    "written_rows": written_rows,
                    **final_metrics,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(state_path)

    write_state("running")

    with closing(_connect(root)) as connection:
        connection.execute("DELETE FROM pitch_stuff_scores WHERE year = ? AND model_version <> ?", (int(year), version))
        connection.execute("DELETE FROM pitch_stuff_pitcher_state WHERE year = ? AND model_version <> ?", (int(year), version))
        states = {
            int(pitcher): int(source_rows)
            for pitcher, source_rows in connection.execute(
                "SELECT pitcher, source_rows FROM pitch_stuff_pitcher_state WHERE year = ? AND model_version = ?",
                (int(year), version),
            ).fetchall()
        }

        from app.services.personal_service import score_pitch_stuff_uncached

        for pitcher, pitcher_rows in source.groupby("pitcher", sort=True):
            pitcher_id = int(pitcher)
            if shard_index is not None and shard_count is not None and pitcher_id % int(shard_count) != int(shard_index):
                continue
            if states.get(pitcher_id) == len(pitcher_rows):
                skipped_pitchers += 1
                if (refreshed_pitchers + skipped_pitchers) % 10 == 0:
                    write_state("running")
                continue
            if max_pitchers is not None and refreshed_pitchers >= int(max_pitchers):
                deferred_pitchers += 1
                continue

            current_keys = _normalized_keys(pitcher_rows)
            current_valid = current_keys.notna().all(axis=1)
            cached = pd.read_sql_query(
                """
                SELECT game_pk, at_bat_number, pitch_number, pitcher
                FROM pitch_stuff_scores
                WHERE year = ? AND pitcher = ? AND model_version = ?
                """,
                connection,
                params=[int(year), pitcher_id, version],
            )
            cached_index = (
                pd.MultiIndex.from_frame(cached[KEY_COLUMNS])
                if not cached.empty
                else pd.MultiIndex.from_arrays([[] for _ in KEY_COLUMNS], names=KEY_COLUMNS)
            )
            source_index = pd.MultiIndex.from_frame(current_keys.loc[current_valid, KEY_COLUMNS])
            full_rebuild = len(cached) > len(source_index) or not cached_index.difference(source_index).empty
            if full_rebuild:
                rows_to_score = pitcher_rows
                connection.execute(
                    "DELETE FROM pitch_stuff_scores WHERE year = ? AND pitcher = ? AND model_version = ?",
                    (int(year), pitcher_id, version),
                )
            else:
                missing = ~source_index.isin(cached_index)
                rows_to_score = pitcher_rows.loc[current_keys.index[current_valid][missing]]

            scored = score_pitch_stuff_uncached(rows_to_score, pitcher_rows)
            keys = _normalized_keys(scored)
            scores = pd.to_numeric(scored.get(SCORE_COLUMN), errors="coerce")
            valid = keys.notna().all(axis=1) & scores.notna()
            records = [
                (
                    int(year), int(row.game_pk), int(row.at_bat_number), int(row.pitch_number),
                    pitcher_id, version, float(score), calculated_at,
                )
                for row, score in zip(keys.loc[valid].itertuples(index=False), scores.loc[valid])
            ]
            connection.executemany(
                """
                INSERT OR REPLACE INTO pitch_stuff_scores
                (year, game_pk, at_bat_number, pitch_number, pitcher, model_version, pitch_stuff_plus, calculated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                records,
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO pitch_stuff_pitcher_state
                (year, pitcher, model_version, source_rows, scored_rows, calculated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (int(year), pitcher_id, version, len(pitcher_rows), len(source_index), calculated_at),
            )
            connection.commit()
            refreshed_pitchers += 1
            written_rows += len(records)
            if (refreshed_pitchers + skipped_pitchers) % 10 == 0:
                write_state("running")

        totals = connection.execute(
            "SELECT COUNT(*), COUNT(DISTINCT pitcher) FROM pitch_stuff_scores WHERE year = ? AND model_version = ?",
            (int(year), version),
        ).fetchone()
    from app.services.personal_service import STUFF_PITCH_TYPE_CODES

    if "pitch_type" in source.columns or "pitch_name" in source.columns:
        raw_pitch_types = source.get("pitch_type", pd.Series("", index=source.index, dtype="object"))
        raw_pitch_names = source.get("pitch_name", pd.Series(pd.NA, index=source.index, dtype="object"))
        raw_codes = raw_pitch_types.fillna("").astype(str).str.upper().str.strip()
        fallback_codes = raw_pitch_names.map(STUFF_PITCH_TYPE_CODES)
        scoreable = raw_codes.ne("") | fallback_codes.notna()
    else:
        # Small injected frames used by callers/tests predate pitch descriptors;
        # production source loading always includes both columns.
        scoreable = pd.Series(True, index=source.index)
    valid_keys = _normalized_keys(source).notna().all(axis=1)
    eligible_rows = int((scoreable & valid_keys).sum())
    cached_rows = int(totals[0])
    missing_eligible_rows = max(eligible_rows - cached_rows, 0)
    final_status = "current" if deferred_pitchers == 0 and missing_eligible_rows == 0 else "partial"
    final_metrics.update(
        {
            "eligible_rows": eligible_rows,
            "cached_rows": cached_rows,
            "missing_eligible_rows": missing_eligible_rows,
            "coverage_pct": round(cached_rows * 100.0 / eligible_rows, 2) if eligible_rows else 100.0,
        }
    )
    result = {
        "year": int(year),
        "model_version": version,
        "source_rows": int(len(source)),
        "eligible_rows": eligible_rows,
        "cached_rows": cached_rows,
        "cached_pitchers": int(totals[1]),
        "missing_eligible_rows": missing_eligible_rows,
        "coverage_pct": final_metrics["coverage_pct"],
        "refreshed_pitchers": refreshed_pitchers,
        "skipped_pitchers": skipped_pitchers,
        "deferred_pitchers": deferred_pitchers,
        "written_rows": written_rows,
        "status": final_status,
        "cache_path": str(cache_path(root)),
        "state_path": str(state_path),
    }
    write_state(final_status)
    return result


def get_pitch_stuff_cache_status(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    path = cache_path(data_dir)
    status: dict[str, Any] = {"path": str(path), "exists": path.exists(), "year": int(year)}
    if not path.exists():
        return status
    version = _artifact_version(data_dir)
    with closing(sqlite3.connect(path, timeout=30)) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT pitcher), MAX(calculated_at)
            FROM pitch_stuff_scores WHERE year = ? AND model_version = ?
            """,
            (int(year), version),
        ).fetchone()
    status.update({"model_version": version, "cached_rows": row[0], "cached_pitchers": row[1], "updated_at": row[2]})
    return status
