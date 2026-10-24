from __future__ import annotations

import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import requests

from app.core.config import settings
from app.repositories.pitch_repository import connect_duckdb_write_with_retry, get_season_duckdb_path
from app.services.admin_service import _import_legacy_statcast_store, legacy_data_dir


CONTRACT_VERSION = "arm_angle_2026_official_backfill_v1"
YEAR = 2026
KEY_COLUMNS = ["game_pk", "at_bat_number", "pitch_number", "pitcher", "batter"]
REFETCH_DATE_COVERAGE_PCT = 98.0


def backfill_contract_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "arm_angle_2026_backfill.json"


def backfill_patch_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "arm_angle_2026_backfill_v1.parquet"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _missing_date_audit(db_path: Path) -> tuple[list[date], dict[str, int | float]]:
    with duckdb.connect(str(db_path), read_only=True) as connection:
        dates = [
            row[0]
            for row in connection.execute(
                """SELECT cast(game_date AS DATE) AS game_day
                   FROM pitches WHERE game_type = 'R'
                   GROUP BY 1
                   HAVING 100.0 * count(arm_angle) / count(*) < ? ORDER BY 1""",
                [REFETCH_DATE_COVERAGE_PCT],
            ).fetchall()
        ]
        row = connection.execute(
            """SELECT count(*) AS pitches, count(arm_angle) AS arm_angle_pitches,
                      count(*) - count(arm_angle) AS missing
               FROM pitches WHERE game_type = 'R'"""
        ).fetchone()
    return dates, {
        "pitches": int(row[0]),
        "arm_angle_pitches": int(row[1]),
        "missing": int(row[2]),
        "coverage_pct": round(100.0 * int(row[1]) / int(row[0]), 3),
        "dates_below_refetch_threshold": len(dates),
    }


def apply_official_arm_angles(
    cached: pd.DataFrame,
    official: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = set(KEY_COLUMNS + ["arm_angle", "game_date"])
    for label, frame in (("cached", cached), ("official", official)):
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"{label} frame missing columns: {sorted(missing)}")

    source = official[KEY_COLUMNS + ["game_date", "arm_angle"]].copy()
    source["arm_angle"] = pd.to_numeric(source["arm_angle"], errors="coerce")
    source = source[source["arm_angle"].notna()].drop_duplicates(KEY_COLUMNS, keep="last")
    if source.duplicated(KEY_COLUMNS).any() or cached.duplicated(KEY_COLUMNS).any():
        raise ValueError("Pitch keys must be unique before the Arm Angle backfill.")

    merged = cached.merge(
        source[KEY_COLUMNS + ["arm_angle"]].rename(columns={"arm_angle": "official_arm_angle"}),
        on=KEY_COLUMNS,
        how="left",
        validate="one_to_one",
    )
    fill_mask = merged["arm_angle"].isna() & merged["official_arm_angle"].notna()
    patch = merged.loc[fill_mask, KEY_COLUMNS + ["game_date", "official_arm_angle"]].copy()
    patch.insert(len(KEY_COLUMNS) + 1, "previous_arm_angle", pd.NA)
    patch = patch.rename(columns={"official_arm_angle": "arm_angle"})
    merged.loc[fill_mask, "arm_angle"] = merged.loc[fill_mask, "official_arm_angle"]
    merged = merged.drop(columns=["official_arm_angle"])
    return merged, patch


def _fetch_official_windows(store: Any, target_dates: list[date]) -> pd.DataFrame:
    store.disable_proxies()
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/csv,application/octet-stream;q=0.9,*/*;q=0.8",
        "Referer": "https://baseballsavant.mlb.com/",
    }
    windows = [(target, target) for target in sorted(set(target_dates))]

    def fetch(window: tuple[date, date]) -> pd.DataFrame:
        start, end = window
        url = store.SAVANT_CSV_URL.format(start_dt=start.isoformat(), end_dt=end.isoformat())
        response = requests.get(url, headers=headers, timeout=180)
        response.raise_for_status()
        text = response.content.decode("utf-8-sig", errors="strict")
        return pd.read_csv(StringIO(text), low_memory=False)

    with ThreadPoolExecutor(max_workers=4) as executor:
        frames = list(executor.map(fetch, windows))
    official = pd.concat(frames, ignore_index=True)
    return store.prepare_statcast_batter_df(official)


def _write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.parquet")
    with duckdb.connect() as connection:
        connection.register("patch", frame)
        connection.execute("COPY patch TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(temporary)])
        connection.unregister("patch")
    temporary.replace(path)


def _write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.csv.gz")
    frame.to_csv(temporary, index=False, compression="gzip")
    temporary.replace(path)


def _patch_duckdb(db_path: Path, patch: pd.DataFrame) -> dict[str, Any]:
    before_dates, before = _missing_date_audit(db_path)
    del before_dates
    connection = connect_duckdb_write_with_retry(db_path)
    updated_tables: dict[str, int] = {}
    try:
        connection.register("arm_patch", patch[KEY_COLUMNS + ["arm_angle"]])
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_type = 'BASE TABLE'"
            ).fetchall()
        }
        for table in ("pitches", "pitches_enriched"):
            if table not in tables:
                continue
            columns = {row[0] for row in connection.execute(f"DESCRIBE {table}").fetchall()}
            if "arm_angle" not in columns:
                continue
            before_changes = connection.execute(
                f"""SELECT count(*) FROM {table} target JOIN arm_patch patch
                    ON target.game_pk = patch.game_pk
                   AND target.at_bat_number = patch.at_bat_number
                   AND target.pitch_number = patch.pitch_number
                   AND target.pitcher = patch.pitcher
                   AND target.batter = patch.batter
                    WHERE target.arm_angle IS NULL"""
            ).fetchone()[0]
            connection.execute(
                f"""UPDATE {table} AS target SET arm_angle = patch.arm_angle
                    FROM arm_patch AS patch
                    WHERE target.game_pk = patch.game_pk
                      AND target.at_bat_number = patch.at_bat_number
                      AND target.pitch_number = patch.pitch_number
                      AND target.pitcher = patch.pitcher
                      AND target.batter = patch.batter
                      AND target.arm_angle IS NULL"""
            )
            updated_tables[table] = int(before_changes)
        connection.unregister("arm_patch")
    finally:
        connection.close()
    _, after = _missing_date_audit(db_path)
    if before["pitches"] != after["pitches"]:
        raise RuntimeError(f"Pitch row count changed while patching {db_path}.")
    return {"path": str(db_path), "before": before, "after": after, "updated_tables": updated_tables}


def backfill_2026_arm_angle(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    site_db = get_season_duckdb_path(YEAR, root)
    missing_dates, before = _missing_date_audit(site_db)
    if not missing_dates:
        raise RuntimeError("No 2026 Arm Angle dates remain below the refetch threshold.")

    store = _import_legacy_statcast_store()
    official = _fetch_official_windows(store, missing_dates)
    cached = store.load_cached_statcast_year(YEAR)
    updated, patch = apply_official_arm_angles(cached, official)
    if patch.empty:
        raise RuntimeError("Official refetch supplied no usable Arm Angle values for the missing rows.")
    target_days = {pd.Timestamp(value).date() for value in missing_dates}
    patched_days = {pd.Timestamp(value).date() for value in patch["game_date"]}
    missing_patched_days = sorted(target_days.difference(patched_days))

    patch_path = backfill_patch_path(root)
    previous_patch = pd.read_parquet(patch_path) if patch_path.exists() else pd.DataFrame()
    cumulative_patch = pd.concat([previous_patch, patch], ignore_index=True)
    cumulative_patch = cumulative_patch.drop_duplicates(KEY_COLUMNS, keep="last")
    _write_parquet(cumulative_patch, patch_path)

    primary_cache = Path(store.get_statcast_cache_path(YEAR))
    _write_csv_atomic(updated, primary_cache)
    root_cache = Path(store.get_root_statcast_cache_path(YEAR))
    root_cache.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(primary_cache, root_cache)
    store.save_statcast_duckdb_year(YEAR, updated)

    legacy_season_dir = legacy_data_dir() / f"MLB{YEAR}"
    site_season_dir = root / f"MLB{YEAR}"
    for csv_path in (
        legacy_season_dir / f"mlb_{YEAR}_pitches.csv.gz",
        site_season_dir / f"mlb_{YEAR}_pitches.csv.gz",
    ):
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(primary_cache, csv_path)

    database_audits = []
    for db_path in (
        legacy_season_dir / f"mlb_{YEAR}.duckdb",
        site_season_dir / f"mlb_{YEAR}.duckdb",
    ):
        database_audits.append(_patch_duckdb(db_path, patch))

    _, after = _missing_date_audit(site_db)
    previous_contract = None
    if backfill_contract_path(root).exists():
        previous_contract = json.loads(backfill_contract_path(root).read_text(encoding="utf-8"))
    original_before = previous_contract.get("before") if previous_contract else before
    payload = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if after["coverage_pct"] >= REFETCH_DATE_COVERAGE_PCT else "incomplete",
        "source": "official Statcast refetch",
        "year": YEAR,
        "fetch_range": {"start": min(missing_dates).isoformat(), "end": max(missing_dates).isoformat()},
        "target_dates_below_98_pct": len(missing_dates),
        "source_limited_dates": [value.isoformat() for value in missing_patched_days],
        "patched_rows_this_run": int(len(patch)),
        "patched_rows": int(len(cumulative_patch)),
        "before": original_before,
        "run_before": before,
        "after": after,
        "patch_artifact": str(patch_path),
        "patch_sha256": _sha256(patch_path),
        "database_audits": database_audits,
        "rules": {
            "match_key": KEY_COLUMNS,
            "mutation": "Only null arm_angle cells with an exact official pitch-key match are filled.",
            "recovery": "The patch artifact contains every changed pitch key; reverting means setting arm_angle back to null only for those keys.",
            "non_synthetic": "Release coordinates were not used to estimate or impute Arm Angle.",
        },
    }
    contract = backfill_contract_path(root)
    temporary = contract.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(contract)
    return payload


def get_arm_angle_backfill_contract(data_dir: Path | None = None) -> dict[str, Any]:
    path = backfill_contract_path(data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Arm Angle backfill contract not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
