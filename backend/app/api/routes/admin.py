from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Any, Callable
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Query

from app.services.admin_service import (
    get_admin_status,
    get_historical_plus_backfill_status,
    get_pitcher_data_status,
    run_pitcher_game_line_backfill,
    run_historical_plus_backfill,
    run_pitcher_data_refresh,
    run_roster_reference_refresh,
    run_video_lookup_backfill,
    write_job_log,
)
from app.services.game_line_service import get_pitcher_game_line_status
from app.services.catcher_descriptive_ledger_service import get_slice1_status, run_slice1_year_update
from app.services.data_freshness_service import get_data_freshness_report, refresh_data_freshness_report
from app.services.project_tracker_service import get_project_tracker
from app.services.player_archetype_slice3_service import get_player_archetype_slice3_view
from app.services.pipeline_reliability_service import (
    read_daily_update_settings,
    write_daily_update_settings,
)
from app.services.video_service import get_video_lookup_status


router = APIRouter()
JOB_REGISTRY: dict[str, dict[str, Any]] = {}
_VIDEO_JOB_LOCK = Lock()


def _video_jobs() -> list[dict[str, Any]]:
    return [dict(job) for job in list(JOB_REGISTRY.values()) if job.get("name") == "backfill_video_lookup"]


@router.get("/player-archetypes/slice3")
def read_player_archetype_slice3(
    year: int = Query(default=2026, ge=2021, le=2026),
    population: str = Query(default="pitcher", pattern="^(pitcher|batter)$"),
    role: str | None = None,
) -> dict[str, Any]:
    return get_player_archetype_slice3_view(year=year, population=population, role=role)


def _run_registered_job(job_id: str, name: str, year: int, fn: Callable[[], dict[str, object]]) -> None:
    JOB_REGISTRY[job_id].update({"status": "running", "started_at": datetime.now().isoformat(timespec="seconds")})
    try:
        result = fn()
        JOB_REGISTRY[job_id].update(
            {
                "status": "completed",
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "result": result,
            }
        )
    except Exception as exc:
        JOB_REGISTRY[job_id].update(
            {
                "status": "failed",
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "error": str(exc),
            }
        )
    finally:
        try:
            JOB_REGISTRY[job_id]["data_freshness"] = refresh_data_freshness_report(year=year)
        except Exception as exc:
            JOB_REGISTRY[job_id]["data_freshness_error"] = str(exc)
        JOB_REGISTRY[job_id]["log_path"] = str(write_job_log(f"{name}_{job_id}", JOB_REGISTRY[job_id]))


def _start_job(background_tasks: BackgroundTasks, name: str, year: int, fn: Callable[[], dict[str, object]]) -> dict[str, object]:
    job_id = uuid4().hex
    JOB_REGISTRY[job_id] = {
        "job_id": job_id,
        "name": name,
        "year": int(year),
        "status": "queued",
        "queued_at": datetime.now().isoformat(timespec="seconds"),
    }
    background_tasks.add_task(_run_registered_job, job_id, name, int(year), fn)
    return JOB_REGISTRY[job_id]


@router.post("/jobs/refresh-pitcher-data")
def refresh_pitcher_data_job(background_tasks: BackgroundTasks, year: int = 2026) -> dict[str, object]:
    return _start_job(
        background_tasks,
        "refresh_pitcher_data",
        year,
        lambda: run_pitcher_data_refresh(year=year),
    )


@router.post("/jobs/backfill-video-lookup")
def backfill_video_lookup_job(
    background_tasks: BackgroundTasks,
    year: int = 2026,
    max_games: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    batch_size: int = 50,
) -> dict[str, object]:
    with _VIDEO_JOB_LOCK:
        active = next((job for job in _video_jobs() if job.get("status") in {"queued", "running"}), None)
        if active:
            return active
        return _start_job(
            background_tasks,
            "backfill_video_lookup",
            year,
            lambda: run_video_lookup_backfill(
                year=year,
                max_games=max_games,
                start_date=start_date,
                end_date=end_date,
                batch_size=batch_size,
            ),
        )


@router.post("/jobs/backfill-pitcher-game-lines")
def backfill_pitcher_game_lines_job(
    background_tasks: BackgroundTasks,
    year: int = 2026,
    max_games: int | None = None,
    batch_size: int = 50,
) -> dict[str, object]:
    return _start_job(
        background_tasks,
        "backfill_pitcher_game_lines",
        year,
        lambda: run_pitcher_game_line_backfill(year=year, max_games=max_games, batch_size=batch_size),
    )


@router.post("/jobs/refresh-roster-data")
def refresh_roster_data_job(background_tasks: BackgroundTasks, year: int = 2026) -> dict[str, object]:
    return _start_job(
        background_tasks,
        "refresh_roster_data",
        year,
        lambda: run_roster_reference_refresh(year=year),
    )


@router.post("/jobs/backfill-historical-plus")
def backfill_historical_plus_job(
    background_tasks: BackgroundTasks,
    year: int = Query(ge=2021, le=2025),
) -> dict[str, object]:
    for job in JOB_REGISTRY.values():
        if job.get("name") == "backfill_historical_plus" and job.get("status") in {"queued", "running"}:
            return job
    return _start_job(
        background_tasks,
        "backfill_historical_plus",
        year,
        lambda: run_historical_plus_backfill(start_year=year, end_year=year),
    )


@router.get("/jobs/historical-plus-status")
def read_historical_plus_status() -> dict[str, object]:
    payload = get_historical_plus_backfill_status()
    active = next(
        (
            job
            for job in JOB_REGISTRY.values()
            if job.get("name") == "backfill_historical_plus" and job.get("status") in {"queued", "running"}
        ),
        None,
    )
    return {**payload, "active_job": active}


@router.post("/jobs/catcher-descriptive-ledger")
def build_catcher_descriptive_ledger_job(
    background_tasks: BackgroundTasks,
    year: int = Query(ge=2021, le=2026),
    workers: int = Query(default=12, ge=1, le=24),
    force_rebuild: bool = False,
) -> dict[str, object]:
    for job in JOB_REGISTRY.values():
        if job.get("name") == "catcher_descriptive_slice1" and job.get("status") in {"queued", "running"}:
            return job
    return _start_job(
        background_tasks,
        "catcher_descriptive_slice1",
        year,
        lambda: run_slice1_year_update(year=year, workers=workers, force_rebuild=force_rebuild),
    )


@router.get("/jobs/catcher-descriptive-ledger-status")
def read_catcher_descriptive_ledger_status() -> dict[str, object]:
    payload = get_slice1_status()
    active = next(
        (
            job
            for job in JOB_REGISTRY.values()
            if job.get("name") == "catcher_descriptive_slice1" and job.get("status") in {"queued", "running"}
        ),
        None,
    )
    return {**payload, "active_job": active}


@router.get("/jobs/{job_id}")
def read_job(job_id: str) -> dict[str, object]:
    return JOB_REGISTRY.get(job_id, {"job_id": job_id, "status": "not_found"})


@router.get("/pitcher-data-status")
def read_pitcher_data_status(year: int = 2026) -> dict[str, object]:
    return get_pitcher_data_status(year=year)


@router.get("/video-lookup-status")
def read_video_lookup_status(year: int = 2026) -> dict[str, object]:
    try:
        payload = get_video_lookup_status(year=year)
    except Exception as exc:
        # A brief DuckDB write lock must not hide the still-running job.
        payload = {"year": year, "coverage_error": str(exc)}
    jobs = _video_jobs()
    active = next((job for job in jobs if job.get("status") in {"queued", "running"}), None)
    latest = next((job for job in reversed(jobs) if job.get("year") == year), None)
    return {**payload, "active_job": active, "latest_job": latest}


@router.get("/pitcher-game-line-status")
def read_pitcher_game_line_status(year: int = 2026) -> dict[str, object]:
    return get_pitcher_game_line_status(year=year)


@router.get("/status")
def read_admin_status(year: int = 2026) -> dict[str, object]:
    return get_admin_status(year=year)


@router.get("/daily-update-settings")
def read_daily_settings() -> dict[str, object]:
    return read_daily_update_settings()


@router.put("/daily-update-settings")
def update_daily_settings(game_updates_enabled: bool) -> dict[str, object]:
    return write_daily_update_settings(game_updates_enabled=game_updates_enabled)


@router.get("/data-freshness")
def read_data_freshness(year: int = 2026) -> dict[str, object]:
    return get_data_freshness_report(year=year)


@router.post("/data-freshness/refresh")
def refresh_data_freshness(year: int = 2026) -> dict[str, object]:
    return refresh_data_freshness_report(year=year)


@router.get("/project-tracker")
def read_project_tracker() -> dict[str, object]:
    return get_project_tracker()
