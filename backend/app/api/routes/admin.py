from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks

from app.services.admin_service import (
    get_admin_status,
    get_pitcher_data_status,
    run_pitcher_game_line_backfill,
    run_pitcher_data_refresh,
    run_roster_reference_refresh,
    run_video_lookup_backfill,
    write_job_log,
)
from app.services.game_line_service import get_pitcher_game_line_status
from app.services.video_service import get_video_lookup_status


router = APIRouter()
JOB_REGISTRY: dict[str, dict[str, Any]] = {}


def _run_registered_job(job_id: str, name: str, fn: Callable[[], dict[str, object]]) -> None:
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
        JOB_REGISTRY[job_id]["log_path"] = str(write_job_log(f"{name}_{job_id}", JOB_REGISTRY[job_id]))
    except Exception as exc:
        JOB_REGISTRY[job_id].update(
            {
                "status": "failed",
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "error": str(exc),
            }
        )
        JOB_REGISTRY[job_id]["log_path"] = str(write_job_log(f"{name}_{job_id}", JOB_REGISTRY[job_id]))


def _start_job(background_tasks: BackgroundTasks, name: str, fn: Callable[[], dict[str, object]]) -> dict[str, object]:
    job_id = uuid4().hex
    JOB_REGISTRY[job_id] = {
        "job_id": job_id,
        "name": name,
        "status": "queued",
        "queued_at": datetime.now().isoformat(timespec="seconds"),
    }
    background_tasks.add_task(_run_registered_job, job_id, name, fn)
    return JOB_REGISTRY[job_id]


@router.post("/jobs/refresh-pitcher-data")
def refresh_pitcher_data_job(background_tasks: BackgroundTasks, year: int = 2026) -> dict[str, object]:
    return _start_job(
        background_tasks,
        "refresh_pitcher_data",
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
    return _start_job(
        background_tasks,
        "backfill_video_lookup",
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
        lambda: run_pitcher_game_line_backfill(year=year, max_games=max_games, batch_size=batch_size),
    )


@router.post("/jobs/refresh-roster-data")
def refresh_roster_data_job(background_tasks: BackgroundTasks, year: int = 2026) -> dict[str, object]:
    return _start_job(
        background_tasks,
        "refresh_roster_data",
        lambda: run_roster_reference_refresh(year=year),
    )


@router.get("/jobs/{job_id}")
def read_job(job_id: str) -> dict[str, object]:
    return JOB_REGISTRY.get(job_id, {"job_id": job_id, "status": "not_found"})


@router.get("/pitcher-data-status")
def read_pitcher_data_status(year: int = 2026) -> dict[str, object]:
    return get_pitcher_data_status(year=year)


@router.get("/video-lookup-status")
def read_video_lookup_status(year: int = 2026) -> dict[str, object]:
    return get_video_lookup_status(year=year)


@router.get("/pitcher-game-line-status")
def read_pitcher_game_line_status(year: int = 2026) -> dict[str, object]:
    return get_pitcher_game_line_status(year=year)


@router.get("/status")
def read_admin_status(year: int = 2026) -> dict[str, object]:
    return get_admin_status(year=year)
