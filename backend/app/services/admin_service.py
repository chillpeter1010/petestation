from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
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
from app.services.pipeline_reliability_service import read_daily_update_state
from app.services.pitch_refresh_service import (
    audit_pitch_coverage,
    classify_source_pending,
    mlb_source_date,
    summarize_missing_coverage,
)
from app.services.transaction_service import get_team_transactions
from app.services.video_service import get_video_lookup_status

_DUCKDB_WRITE_LOCK = threading.Lock()


HISTORICAL_PLUS_STAGES = [
    ("location_plus", {"job": "location_scores"}),
    ("pitch_stuff_plus", {"job": "pitch_stuff_scores"}),
    ("pitching_plus", {"job": "pitching_plus"}),
    ("plus_leaderboard", {"job": "stuff_leaderboard"}),
    ("stamina_dataset", {"job": "stamina_dataset"}),
]

_DUCKDB_WRITE_CHILD = r"""
from __future__ import annotations

import json
import sys
import traceback

from app.core.config import settings


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


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
        elif job == "starter_reference":
            from app.services.starter_reference_service import refresh_starter_reference_data

            result = refresh_starter_reference_data(data_dir=settings.data_dir, **payload)
        elif job == "batter_timing":
            from app.services.batter_swing_timing_service import refresh_batter_timing_cache

            year = int(payload["year"])
            result = {
                hand: refresh_batter_timing_cache(year=year, pitcher_hand=hand, data_dir=settings.data_dir)
                for hand in ["All", "L", "R"]
            }
        elif job == "location_scores":
            from app.ml.location_exports import export_location_scores

            result = export_location_scores(data_dir=settings.data_dir, **payload)
        elif job == "pitch_stuff_scores":
            from app.services.pitch_stuff_cache_service import refresh_pitch_stuff_scores

            result = refresh_pitch_stuff_scores(data_dir=settings.data_dir, **payload)
        elif job == "stamina_dataset":
            from app.services.stamina_lab_service import refresh_stamina_dataset

            result = refresh_stamina_dataset(data_dir=settings.data_dir, **payload)
        elif job == "stuff_leaderboard":
            from app.services.stuff_leaderboard_service import refresh_stuff_leaderboard

            result = refresh_stuff_leaderboard(data_dir=settings.data_dir, **payload)
        elif job == "pitching_plus":
            from app.ml.pitching_plus import refresh_pitching_exports

            result = refresh_pitching_exports(
                data_dir=settings.data_dir,
                artifact_dir=settings.data_dir / "models" / "pitching_plus",
                **payload,
            )
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


def _refresh_legacy_pitcher_data(module: Any, year: int, source_through: date) -> dict[str, object]:
    """Cap the external legacy updater without modifying its separate worktree."""

    original_update = getattr(module, "update_statcast_year_cache", None)
    if not callable(original_update):
        return dict(module.refresh_pitcher_data(year=int(year)))

    def capped_update(*args: object, **kwargs: object) -> object:
        requested = kwargs.get("end_dt")
        kwargs["end_dt"] = min(requested, source_through) if isinstance(requested, date) else source_through
        return original_update(*args, **kwargs)

    module.update_statcast_year_cache = capped_update
    try:
        return dict(module.refresh_pitcher_data(year=int(year)))
    finally:
        module.update_statcast_year_cache = original_update


def run_pitch_source_refresh(year: int = 2026) -> dict[str, object]:
    source_through = mlb_source_date()
    with _DUCKDB_WRITE_LOCK:
        initial_audit = audit_pitch_coverage(year=int(year), data_dir=settings.data_dir, through=source_through)
        repair = None
        if not initial_audit["complete"]:
            repair = _repair_missing_statcast_dates(int(year), list(initial_audit["missing_dates"]))

        module = _import_legacy_pitcher_data_update()
        result = _refresh_legacy_pitcher_data(module, int(year), source_through)
        result["source_through"] = source_through.isoformat()
        result["synced_to_site_data"] = sync_legacy_pitcher_refresh_outputs(year=int(year))
        result["initial_coverage"] = initial_audit
        if repair is not None:
            result["repair"] = repair

        final_audit = audit_pitch_coverage(year=int(year), data_dir=settings.data_dir, through=source_through)
        pending = classify_source_pending(final_audit, today=source_through)
        final_audit["status"] = "current" if final_audit["complete"] else ("source_pending" if pending["source_pending"] else "incomplete")
        final_audit["source_pending"] = pending
        result["coverage"] = final_audit
        if not final_audit["complete"] and not pending["source_pending"]:
            raise RuntimeError(summarize_missing_coverage(final_audit))
        return result


def run_pitcher_data_refresh(year: int = 2026, include_pitch_stuff: bool = False) -> dict[str, object]:
    # ``include_pitch_stuff`` is retained for callers created before per-pitch
    # Stuff+ became a required refresh step. Incremental scoring skips unchanged
    # pitchers, so the complete cache remains the only publishable state.
    del include_pitch_stuff
    result = run_pitch_source_refresh(year=int(year))
    with _DUCKDB_WRITE_LOCK:
        result["pitcher_game_lines"] = _run_duckdb_write_child(
            {"job": "pitcher_game_lines", "year": int(year)}
        )
        result["starter_reference"] = _run_optional_refresh_child(
            {"job": "starter_reference", "year": int(year)}
        )
        result["location_plus"] = _run_duckdb_write_child(
            {"job": "location_scores", "year": int(year)}
        )
        result["pitching_plus"] = _run_optional_refresh_child(
            {"job": "pitching_plus", "export_year": int(year), "reference_year": int(year) - 1}
        )
        result["pitch_stuff_plus"] = _run_duckdb_write_child(
            {"job": "pitch_stuff_scores", "year": int(year)}
        )
        if result["pitch_stuff_plus"].get("status") != "current":  # type: ignore[union-attr]
            raise RuntimeError(
                "Per-pitch Stuff+ refresh did not reach current status: "
                f"{result['pitch_stuff_plus']}"
            )
        result["plus_leaderboard"] = _run_optional_refresh_child(
            {"job": "stuff_leaderboard", "year": int(year)}
        )
        result["stamina_dataset"] = _run_duckdb_write_child(
            {"job": "stamina_dataset", "year": int(year)}
        )
        result["batter_lineup_scenarios"] = _run_duckdb_write_child(
            {"job": "batter_lineup_scenarios", "year": int(year)}
        )
        result["batter_timing"] = _run_optional_refresh_child(
            {"job": "batter_timing", "year": int(year)}
        )
        return result


DAILY_PIPELINE_STEPS = (
    "pitch_data",
    "video_lookup",
    "pitcher_game_lines",
    "starter_reference",
    "location_plus",
    "pitching_plus",
    "pitch_stuff_plus",
    "plus_leaderboard",
    "stamina_dataset",
    "batter_lineup_scenarios",
    "batter_timing",
    "roster_data",
    "data_freshness",
)


def run_daily_pipeline_step(name: str, year: int = 2026) -> dict[str, object]:
    target = str(name)
    season = int(year)
    if target == "pitch_data":
        return run_pitch_source_refresh(season)
    if target == "video_lookup":
        return run_video_lookup_backfill(year=season)
    if target == "pitcher_game_lines":
        return run_pitcher_game_line_backfill(year=season)
    if target == "starter_reference":
        with _DUCKDB_WRITE_LOCK:
            return _run_optional_refresh_child({"job": "starter_reference", "year": season})
    if target == "location_plus":
        with _DUCKDB_WRITE_LOCK:
            return _run_duckdb_write_child({"job": "location_scores", "year": season})
    if target == "pitching_plus":
        with _DUCKDB_WRITE_LOCK:
            return _run_optional_refresh_child({"job": "pitching_plus", "export_year": season, "reference_year": season - 1})
    if target == "pitch_stuff_plus":
        with _DUCKDB_WRITE_LOCK:
            result = _run_duckdb_write_child({"job": "pitch_stuff_scores", "year": season})
        if result.get("status") != "current":
            raise RuntimeError(f"Per-pitch Stuff+ remains {result.get('status') or 'unknown'}.")
        return result
    if target == "plus_leaderboard":
        with _DUCKDB_WRITE_LOCK:
            return _run_optional_refresh_child({"job": "stuff_leaderboard", "year": season})
    if target == "stamina_dataset":
        with _DUCKDB_WRITE_LOCK:
            return _run_duckdb_write_child({"job": "stamina_dataset", "year": season})
    if target == "batter_lineup_scenarios":
        with _DUCKDB_WRITE_LOCK:
            return _run_duckdb_write_child({"job": "batter_lineup_scenarios", "year": season})
    if target == "batter_timing":
        with _DUCKDB_WRITE_LOCK:
            return _run_optional_refresh_child({"job": "batter_timing", "year": season})
    if target == "roster_data":
        return run_roster_reference_refresh(year=season)
    if target == "data_freshness":
        from app.services.data_freshness_service import refresh_data_freshness_report

        return refresh_data_freshness_report(year=season)
    raise ValueError(f"Unknown daily pipeline step: {target}")


def _run_optional_refresh_child(payload: dict[str, object]) -> dict[str, object]:
    """Keep the last atomic snapshot when an external reference source is temporarily unavailable."""
    try:
        return _run_duckdb_write_child(payload)
    except Exception as exc:
        return {
            "status": "stale",
            "error": str(exc),
            "preserved_previous_snapshot": True,
        }


def _historical_plus_state_path(data_dir: Path | None = None) -> Path:
    root = data_dir or settings.data_dir
    return root / "admin_job_logs" / "historical_plus_backfill.json"


def get_historical_plus_backfill_status(data_dir: Path | None = None) -> dict[str, object]:
    path = _historical_plus_state_path(data_dir)
    if not path.exists():
        return {
            "status": "not_started",
            "start_year": 2021,
            "end_year": 2025,
            "state_path": str(path),
            "years": {},
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "invalid", "error": str(exc), "state_path": str(path), "years": {}}
    for year, year_state in dict(payload.get("years") or {}).items():
        if not isinstance(year_state, dict) or year_state.get("current_stage") != "pitch_stuff_plus":
            continue
        progress_path = (data_dir or settings.data_dir) / "admin_job_logs" / f"pitch_stuff_backfill_{year}.json"
        if not progress_path.exists():
            continue
        try:
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        stages = year_state.get("stages")
        if isinstance(stages, dict) and isinstance(stages.get("pitch_stuff_plus"), dict):
            stages["pitch_stuff_plus"]["progress"] = progress
    payload["state_path"] = str(path)
    return payload


def run_historical_plus_backfill(
    start_year: int = 2021,
    end_year: int = 2025,
    data_dir: Path | None = None,
) -> dict[str, object]:
    """Resume the historical Plus pipeline without recomputing completed pitch caches."""

    first_year, last_year = int(start_year), int(end_year)
    if first_year > last_year:
        raise ValueError("start_year must be less than or equal to end_year")
    root = data_dir or settings.data_dir
    path = _historical_plus_state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = get_historical_plus_backfill_status(root)
    years = dict(previous.get("years") or {})

    def write_state(status: str, **updates: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": status,
            "start_year": first_year,
            "end_year": last_year,
            "years": years,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **updates,
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        temporary.replace(path)
        payload["state_path"] = str(path)
        return payload

    write_state("running", message="Historical Plus backfill started.")
    failed_years: list[int] = []
    year_order = list(range(first_year, last_year + 1))
    if 2025 in year_order:
        year_order = [2025, *[year for year in year_order if year != 2025]]
    for year in year_order:
        source_path = root / f"MLB{year}" / f"mlb_{year}.duckdb"
        year_state = dict(years.get(str(year)) or {})
        year_state.update({"status": "running", "source_path": str(source_path), "stages": dict(year_state.get("stages") or {})})
        years[str(year)] = year_state
        if not source_path.exists():
            year_state.update({"status": "failed", "error": f"Missing season database: {source_path}"})
            failed_years.append(year)
            write_state("running", current_year=year, message=year_state["error"])
            continue

        for stage_name, base_payload in HISTORICAL_PLUS_STAGES:
            existing_stage = year_state["stages"].get(stage_name)
            if isinstance(existing_stage, dict) and existing_stage.get("status") in {"completed", "current"}:
                continue
            stage_payload = dict(base_payload)
            if stage_name == "pitching_plus":
                # Historical exports are centered on the season being displayed;
                # unlike the live-year refresh they do not require a prior-year database.
                stage_payload.update({"export_year": year, "reference_year": year})
            else:
                stage_payload["year"] = year
            year_state["current_stage"] = stage_name
            year_state["stages"][stage_name] = {"status": "running"}
            write_state(
                "running",
                current_year=year,
                current_stage=stage_name,
                message=f"{year}: running {stage_name}.",
            )
            try:
                with _DUCKDB_WRITE_LOCK:
                    result = _run_duckdb_write_child(stage_payload)
                stage_status = str(result.get("status") or "completed")
                year_state["stages"][stage_name] = {"status": stage_status, "result": result}
                if stage_name == "pitch_stuff_plus" and stage_status != "current":
                    raise RuntimeError(f"Per-pitch Stuff+ remains {stage_status}; rerun to resume missing pitchers.")
            except Exception as exc:
                year_state["stages"][stage_name] = {"status": "failed", "error": str(exc)}
                year_state.update({"status": "failed", "error": f"{stage_name}: {exc}"})
                failed_years.append(year)
                write_state(
                    "running",
                    current_year=year,
                    current_stage=stage_name,
                    message=f"{year}: {stage_name} failed; continuing with the next season.",
                )
                break
        else:
            year_state.update({"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()})
            year_state.pop("error", None)
            year_state.pop("current_stage", None)
            write_state("running", current_year=year, message=f"{year}: all Plus datasets completed.")

    final_status = "completed" if not failed_years else "partial"
    return write_state(
        final_status,
        failed_years=sorted(set(failed_years)),
        message=(
            "Historical Plus backfill completed."
            if not failed_years
            else "Historical Plus backfill is partial. Press the button again to resume failed seasons."
        ),
        finished_at=datetime.now(timezone.utc).isoformat(),
    )


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
    env["PYTHONIOENCODING"] = "utf-8"
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
    log_dir = settings.data_dir / "admin_job_logs" / "child_processes"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    job_name = str(payload.get("job") or "unknown").replace("/", "_").replace("\\", "_")
    (log_dir / f"{stamp}_{job_name}.stdout.log").write_text(stdout, encoding="utf-8")
    (log_dir / f"{stamp}_{job_name}.stderr.log").write_text(stderr, encoding="utf-8")
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
    from app.services.stuff_leaderboard_service import get_stuff_leaderboard

    try:
        leaderboard_status = get_stuff_leaderboard(year=year)
        leaderboard_status = {
            key: leaderboard_status.get(key)
            for key in ["cache_status", "data_as_of", "generated_at", "model_version", "total_pitchers", "warnings"]
        }
    except FileNotFoundError as exc:
        leaderboard_status = {"cache_status": "unavailable", "error": str(exc)}

    return {
        "year": int(year),
        "daily_update": read_daily_update_state(settings.data_dir),
        "pitcher_data": get_pitcher_data_status(year=year),
        "video_lookup": get_video_lookup_status(year=year, data_dir=settings.data_dir),
        "pitcher_game_lines": get_pitcher_game_line_status(year=year, data_dir=settings.data_dir),
        "pitch_stuff_plus": get_pitch_stuff_cache_status(year=year, data_dir=settings.data_dir),
        "plus_leaderboard": leaderboard_status,
    }


def write_job_log(name: str, payload: dict[str, object]) -> Path:
    log_dir = settings.data_dir / "admin_job_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
