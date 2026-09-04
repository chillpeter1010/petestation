from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from app.core.config import settings
from app.services.game_line_service import get_pitcher_game_line_status
from app.services.payroll.importer import (
    PayrollSourceBlockedError,
    fetch_payroll_markdown,
    parse_payroll_markdown,
    write_payroll_snapshot,
)
from app.services.payroll.team_slugs import TEAM_PAYROLL_SLUGS
from app.services.pitch_refresh_service import audit_pitch_coverage, classify_source_pending, summarize_missing_coverage
from app.services.transaction_service import get_team_transactions
from app.services.video_service import get_video_lookup_status

_DUCKDB_WRITE_LOCK = threading.Lock()

_DUCKDB_WRITE_CHILD = r"""
from __future__ import annotations

import json
import sys
import traceback

from app.core.config import settings


def main() -> int:
    payload = json.loads(sys.argv[1])
    job = payload.pop("job")
    try:
        if job == "video_lookup":
            from app.services.video_service import backfill_video_lookup

            result = backfill_video_lookup(data_dir=settings.data_dir, **payload)
        elif job == "pitcher_game_lines":
            from app.services.game_line_service import backfill_pitcher_game_lines

            result = backfill_pitcher_game_lines(data_dir=settings.data_dir, **payload)
        elif job == "location_scores":
            from app.ml.location_exports import export_location_scores

            result = export_location_scores(data_dir=settings.data_dir, **payload)
        elif job == "pitch_stuff_scores":
            from app.services.pitch_stuff_cache_service import refresh_pitch_stuff_scores

            result = refresh_pitch_stuff_scores(data_dir=settings.data_dir, **payload)
        elif job == "batter_lineup_scenarios":
            from app.services.batter_team_research_service import refresh_batter_lineup_scenario_cache

            result = refresh_batter_lineup_scenario_cache(data_dir=settings.data_dir, **payload)
        else:
            raise ValueError(f"Unknown admin child job: {job}")
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, default=str))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "traceback": traceback.format_exc(),
                },
                ensure_ascii=False,
            )
        )
        return 1


raise SystemExit(main())
"""


def legacy_project_dir() -> Path:
    candidates = [
        settings.legacy_project_dir,
        settings.data_dir.parent / "claude",
        Path.home() / "Desktop" / "實習個案" / "abs2025" / "claude",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return next(candidate for candidate in candidates if candidate is not None)


def _import_legacy_pitcher_data_update() -> Any:
    legacy_dir = legacy_project_dir()
    if not legacy_dir.exists():
        raise RuntimeError(f"Legacy project directory not found: {legacy_dir}")
    for path in [legacy_dir.parent, legacy_dir]:
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)
    return importlib.import_module("pitcher_data_update")


def _import_legacy_statcast_store() -> Any:
    legacy_dir = legacy_project_dir()
    for path in [legacy_dir.parent, legacy_dir]:
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)
    return importlib.import_module("statcast_store")


def legacy_data_dir() -> Path:
    return legacy_project_dir().parent / "data"


def _copy_if_newer(source: Path, target: Path) -> dict[str, object] | None:
    if not source.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    copied = not target.exists() or source.stat().st_mtime > target.stat().st_mtime or source.stat().st_size != target.stat().st_size
    if copied:
        shutil.copy2(source, target)
    return {
        "source": str(source),
        "target": str(target),
        "copied": copied,
        "bytes": target.stat().st_size if target.exists() else 0,
    }


def sync_legacy_pitcher_refresh_outputs(year: int) -> dict[str, object]:
    source_root = legacy_data_dir()
    target_root = settings.data_dir
    if source_root.resolve() == target_root.resolve():
        return {"source_root": str(source_root), "target_root": str(target_root), "skipped": True, "files": []}

    year = int(year)
    relative_paths = [
        Path(f"MLB{year}") / f"mlb_{year}.duckdb",
        Path(f"MLB{year}") / f"mlb_{year}_pitches.csv.gz",
        Path(f"MLB{year}") / f"mlb_{year}_meta.json",
        Path(f"MLB{year}") / f"mlb_{year}_download_meta.json",
        Path(f"{year}_pitcher_comparison.csv"),
        Path(f"{year}_pitching_estimators.csv"),
        Path(f"{year}_pitcher_comparison_with_est_xera.csv"),
        Path(f"estimated_xera_model_{year - 1}.json"),
    ]
    files = [
        copied
        for relative_path in relative_paths
        if (copied := _copy_if_newer(source_root / relative_path, target_root / relative_path)) is not None
    ]
    return {
        "source_root": str(source_root),
        "target_root": str(target_root),
        "skipped": False,
        "files": files,
    }


def run_pitcher_data_refresh(year: int = 2026, include_pitch_stuff: bool = False) -> dict[str, object]:
    with _DUCKDB_WRITE_LOCK:
        initial_audit = audit_pitch_coverage(year=int(year), data_dir=settings.data_dir)
        repair = None
        if not initial_audit["complete"]:
            repair = _repair_missing_statcast_dates(int(year), list(initial_audit["missing_dates"]))

        module = _import_legacy_pitcher_data_update()
        result = dict(module.refresh_pitcher_data(year=int(year)))
        result["synced_to_site_data"] = sync_legacy_pitcher_refresh_outputs(year=int(year))
        result["initial_coverage"] = initial_audit
        if repair is not None:
            result["repair"] = repair

        final_audit = audit_pitch_coverage(year=int(year), data_dir=settings.data_dir)
        pending = classify_source_pending(final_audit)
        final_audit["status"] = "current" if final_audit["complete"] else ("source_pending" if pending["source_pending"] else "incomplete")
        final_audit["source_pending"] = pending
        result["coverage"] = final_audit
        if not final_audit["complete"] and not pending["source_pending"]:
            raise RuntimeError(summarize_missing_coverage(final_audit))
        result["pitcher_game_lines"] = _run_duckdb_write_child(
            {"job": "pitcher_game_lines", "year": int(year)}
        )
        result["location_plus"] = _run_duckdb_write_child(
            {"job": "location_scores", "year": int(year)}
        )
        if include_pitch_stuff:
            result["pitch_stuff_plus"] = _run_duckdb_write_child(
                {"job": "pitch_stuff_scores", "year": int(year)}
            )
        else:
            result["pitch_stuff_plus"] = {
                "status": "deferred",
                "reason": "Per-pitch Stuff+ backfill runs separately so it cannot block the daily data refresh.",
            }
        result["batter_lineup_scenarios"] = _run_duckdb_write_child(
            {"job": "batter_lineup_scenarios", "year": int(year)}
        )
        return result


def _repair_missing_statcast_dates(year: int, missing_dates: list[str]) -> dict[str, object]:
    from io import StringIO

    import pandas as pd
    import requests

    store = _import_legacy_statcast_store()
    cached = store.load_cached_statcast_year(int(year))
    fetched_frames: list[Any] = []
    failed_dates: list[str] = []
    rows_by_date: dict[str, int] = {}
    for date_label in sorted(set(missing_dates)):
        day = date.fromisoformat(date_label)
        fetched = pd.DataFrame()
        for _ in range(2):
            fetched = store.fetch_statcast_range(int(year), day, day)
            if fetched.empty:
                try:
                    store.disable_proxies()
                    response = requests.get(
                        store.SAVANT_CSV_URL.format(start_dt=date_label, end_dt=date_label),
                        headers={
                            "User-Agent": "Mozilla/5.0",
                            "Accept": "text/csv,application/octet-stream;q=0.9,*/*;q=0.8",
                            "Referer": "https://baseballsavant.mlb.com/",
                        },
                        timeout=120,
                    )
                    response.raise_for_status()
                    candidate = pd.read_csv(StringIO(response.content.decode("utf-8-sig", errors="replace")), low_memory=False)
                    fetched = store.prepare_statcast_batter_df(candidate)
                    fetched = fetched[pd.to_numeric(fetched.get("game_year"), errors="coerce") == int(year)].copy()
                except Exception:
                    fetched = pd.DataFrame()
            if not fetched.empty:
                break
        if fetched.empty:
            failed_dates.append(date_label)
            continue
        rows_by_date[date_label] = int(len(fetched))
        fetched_frames.append(fetched)

    if fetched_frames:
        combined = pd.concat([cached, *fetched_frames], ignore_index=True) if not cached.empty else pd.concat(fetched_frames, ignore_index=True)
        dedupe_cols = [
            column
            for column in ["game_pk", "at_bat_number", "pitch_number", "pitcher", "batter"]
            if column in combined.columns
        ]
        if dedupe_cols:
            combined = combined.drop_duplicates(subset=dedupe_cols, keep="last")
        combined = store.prepare_statcast_batter_df(combined)
        store.save_statcast_cache(int(year), combined)
        store.save_statcast_duckdb_year(int(year), combined)

    return {
        "requested_dates": sorted(set(missing_dates)),
        "repaired_dates": sorted(rows_by_date),
        "failed_dates": failed_dates,
        "fetched_rows": sum(rows_by_date.values()),
        "rows_by_date": rows_by_date,
    }


def sync_pitcher_data_from_legacy(year: int = 2026) -> dict[str, object]:
    with _DUCKDB_WRITE_LOCK:
        return sync_legacy_pitcher_refresh_outputs(year=int(year))


def _run_duckdb_write_child(payload: dict[str, object]) -> dict[str, object]:
    backend_dir = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(backend_dir)
        if not existing_pythonpath
        else str(backend_dir) + os.pathsep + existing_pythonpath
    )
    completed = subprocess.run(
        [sys.executable, "-c", _DUCKDB_WRITE_CHILD, json.dumps(payload, ensure_ascii=False)],
        cwd=str(backend_dir.parent),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    parsed: dict[str, Any] | None = None
    if lines:
        try:
            parsed = json.loads(lines[-1])
        except json.JSONDecodeError:
            parsed = None

    if completed.returncode != 0:
        if parsed and parsed.get("error"):
            raise RuntimeError(str(parsed["error"]))
        detail = stderr.strip() or stdout.strip() or f"exit code {completed.returncode}"
        raise RuntimeError(detail)
    if not parsed or not parsed.get("ok"):
        detail = stderr.strip() or stdout.strip() or "child job returned no JSON result"
        raise RuntimeError(detail)
    return dict(parsed["result"])


def get_pitcher_data_status(year: int = 2026) -> dict[str, object]:
    snapshot: dict[str, object] = {"year": int(year)}
    legacy_dir = legacy_project_dir()
    if legacy_dir.exists():
        try:
            module = _import_legacy_pitcher_data_update()
            if hasattr(module, "get_pitcher_update_snapshot"):
                snapshot.update(dict(module.get_pitcher_update_snapshot(year=int(year))))
        except Exception as exc:
            snapshot["legacy_snapshot_error"] = str(exc)

    db_path = settings.data_dir / f"MLB{int(year)}" / f"mlb_{int(year)}.duckdb"
    comparison_path = settings.data_dir / "Starter" / f"{int(year)}_pitcher_comparison.csv"
    estimator_candidates = list(settings.data_dir.glob(f"**/*{int(year)}*estimators*.csv"))
    xera_candidates = list(settings.data_dir.glob("**/*xera*.csv"))
    for key, path in [
        ("duckdb", db_path),
        ("comparison_csv", comparison_path),
    ]:
        snapshot[f"{key}_path"] = str(path)
        snapshot[f"{key}_exists"] = path.exists()
        if path.exists():
            snapshot[f"{key}_updated_at"] = path.stat().st_mtime
    snapshot["estimator_candidates"] = [str(path) for path in estimator_candidates[:8]]
    snapshot["xera_candidates"] = [str(path) for path in xera_candidates[:8]]
    if db_path.exists():
        try:
            with duckdb.connect(str(db_path), read_only=True) as conn:
                tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
                if "pitches" in tables:
                    latest = conn.execute("SELECT MAX(CAST(game_date AS DATE)) FROM pitches WHERE game_type = 'R'").fetchone()[0]
                    snapshot["latest_pitch_date"] = str(latest)[:10] if latest else None
        except duckdb.Error as exc:
            snapshot["latest_pitch_date_error"] = str(exc)
    location_path = settings.data_dir / "derived" / "location_plus_scores.duckdb"
    snapshot["location_plus_path"] = str(location_path)
    snapshot["location_plus_exists"] = location_path.exists()
    if location_path.exists():
        try:
            with duckdb.connect(str(location_path), read_only=True) as conn:
                table = f"location_outing_scores_{int(year)}"
                tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
                if table in tables:
                    latest = conn.execute(f"SELECT MAX(CAST(game_date AS DATE)) FROM {table}").fetchone()[0]
                    snapshot["latest_location_plus_date"] = str(latest)[:10] if latest else None
        except duckdb.Error as exc:
            snapshot["latest_location_plus_date_error"] = str(exc)
    return snapshot


def run_video_lookup_backfill(
    year: int = 2026,
    max_games: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    batch_size: int = 50,
) -> dict[str, object]:
    with _DUCKDB_WRITE_LOCK:
        return _run_duckdb_write_child(
            {
                "job": "video_lookup",
                "year": int(year),
                "max_games": max_games,
                "start_date": start_date,
                "end_date": end_date,
                "batch_size": batch_size,
            }
        )


def run_pitcher_game_line_backfill(
    year: int = 2026,
    max_games: int | None = None,
    batch_size: int = 50,
) -> dict[str, object]:
    with _DUCKDB_WRITE_LOCK:
        return _run_duckdb_write_child(
            {
                "job": "pitcher_game_lines",
                "year": int(year),
                "max_games": max_games,
                "batch_size": batch_size,
            }
        )


def run_transaction_refresh(year: int = 2026) -> dict[str, object]:
    """Refresh the league-wide MLB transaction payload used by every team page."""
    response = get_team_transactions(
        year=int(year),
        team_code="AZ",
        mlb_team_id=109,
        days=60,
        limit=100,
        data_dir=settings.data_dir,
        force_refresh=True,
    )
    warnings = list(response.meta.warnings or [])
    if warnings:
        raise RuntimeError("; ".join(warnings))
    return {
        "scope": "all_mlb_teams",
        "fetched_at": response.fetched_at,
        "period_start": response.period_start,
        "period_end": response.period_end,
        "cache_path": str(settings.data_dir / f"MLB{int(year)}" / f"mlb_{int(year)}_transactions.json"),
    }


def _refresh_payroll_team(team_code: str, year: int) -> str:
    markdown = fetch_payroll_markdown(team_code)
    payload = parse_payroll_markdown(markdown, team_code, int(year))
    if not payload["guaranteed_players"] or not payload["estimated_payroll_by_year"]:
        raise ValueError("FanGraphs payroll tables were incomplete")
    return str(write_payroll_snapshot(payload, team_code, int(year), settings.data_dir))


def run_payroll_refresh(year: int = 2026, workers: int = 2) -> dict[str, object]:
    """Refresh all available FanGraphs team payroll snapshots with bounded concurrency."""
    teams = sorted(TEAM_PAYROLL_SLUGS)
    snapshot_dir = settings.data_dir / f"MLB{int(year)}" / "payroll"
    preserved_teams = sorted(team for team in teams if (snapshot_dir / f"{team.casefold()}.json").exists())
    updated: dict[str, str] = {}
    failures: dict[str, str] = {}

    probe_team = teams[0]
    try:
        updated[probe_team] = _refresh_payroll_team(probe_team, int(year))
    except PayrollSourceBlockedError as exc:
        if not preserved_teams:
            raise RuntimeError(str(exc)) from exc
        return {
            "requested_count": len(teams),
            "updated_count": 0,
            "failed_count": 0,
            "preserved_count": len(preserved_teams),
            "updated_teams": [],
            "preserved_teams": preserved_teams,
            "source_status": "temporarily_blocked",
            "warning": str(exc),
        }
    except Exception as exc:
        failures[probe_team] = str(exc)

    remaining_teams = [team for team in teams if team != probe_team]
    with ThreadPoolExecutor(max_workers=max(1, min(int(workers), 4))) as executor:
        jobs = {executor.submit(_refresh_payroll_team, team, int(year)): team for team in remaining_teams}
        for future in as_completed(jobs):
            team = jobs[future]
            try:
                updated[team] = future.result()
            except Exception as exc:
                failures[team] = str(exc)
    if not updated and not preserved_teams:
        raise RuntimeError(f"All payroll refreshes failed: {failures}")
    return {
        "requested_count": len(teams),
        "updated_count": len(updated),
        "failed_count": len(failures),
        "preserved_count": len([team for team in failures if team in preserved_teams]),
        "updated_teams": sorted(updated),
        "failures": failures,
        "source_status": "current" if not failures else "partial",
    }


def run_roster_reference_refresh(year: int = 2026) -> dict[str, object]:
    """Refresh transactions/injuries and contract snapshots as one maintenance job."""
    return {
        "transactions": run_transaction_refresh(year=int(year)),
        "payroll": run_payroll_refresh(year=int(year)),
    }


def get_admin_status(year: int = 2026) -> dict[str, object]:
    from app.services.pitch_stuff_cache_service import get_pitch_stuff_cache_status

    return {
        "year": int(year),
        "pitcher_data": get_pitcher_data_status(year=year),
        "video_lookup": get_video_lookup_status(year=year, data_dir=settings.data_dir),
        "pitcher_game_lines": get_pitcher_game_line_status(year=year, data_dir=settings.data_dir),
        "pitch_stuff_plus": get_pitch_stuff_cache_status(year=year, data_dir=settings.data_dir),
    }


def write_job_log(name: str, payload: dict[str, object]) -> Path:
    log_dir = settings.data_dir / "admin_job_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
