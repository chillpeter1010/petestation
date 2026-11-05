from concurrent.futures import ThreadPoolExecutor

import duckdb
import pytest
from fastapi import BackgroundTasks

from app.api.routes import admin
from app.services import video_service


@pytest.fixture
def video_registry(monkeypatch):
    registry = {}
    monkeypatch.setattr(admin, "JOB_REGISTRY", registry)
    return registry


def test_parallel_clicks_queue_only_one_video_job(video_registry):
    tasks = [BackgroundTasks() for _ in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda task: admin.backfill_video_lookup_job(task, year=2026), tasks))
    assert len({result["job_id"] for result in results}) == 1
    assert sum(len(task.tasks) for task in tasks) == 1
    # Calls only register tasks: no real network or season data writes in tests.
    assert next(iter(video_registry.values()))["status"] == "queued"


def test_active_other_season_returned_and_failed_job_can_retry(video_registry):
    first = admin.backfill_video_lookup_job(BackgroundTasks(), year=2025)
    first["status"] = "running"
    duplicate_tasks = BackgroundTasks()
    assert admin.backfill_video_lookup_job(duplicate_tasks, year=2026)["year"] == 2025
    assert not duplicate_tasks.tasks
    first["status"] = "failed"
    assert admin.backfill_video_lookup_job(BackgroundTasks(), year=2026)["job_id"] != first["job_id"]


def test_status_reconnects_to_active_and_season_latest(video_registry, monkeypatch):
    old = admin.backfill_video_lookup_job(BackgroundTasks(), year=2026)
    old.update(status="completed", result={"failed_games": [123]})
    active = admin.backfill_video_lookup_job(BackgroundTasks(), year=2025)
    monkeypatch.setattr(admin, "get_video_lookup_status", lambda year: {"year": year, "missing_games": 1})
    status = admin.read_video_lookup_status(year=2026)
    assert status["active_job"]["job_id"] == active["job_id"]
    assert status["latest_job"]["result"]["failed_games"] == [123]
    assert status["missing_games"] == 1


def test_status_read_error_does_not_hide_active_job(video_registry, monkeypatch):
    active = admin.backfill_video_lookup_job(BackgroundTasks())

    def locked(year):
        raise RuntimeError("database locked")

    monkeypatch.setattr(admin, "get_video_lookup_status", locked)
    status = admin.read_video_lookup_status()
    assert status["coverage_error"] == "database locked"
    assert status["active_job"]["job_id"] == active["job_id"]
    assert "missing_games" not in status


@pytest.mark.parametrize("with_lookups,expected_complete", [(False, 0), (True, 1)])
def test_coverage_matches_worker_intersection(tmp_path, with_lookups, expected_complete):
    season = tmp_path / "MLB2026"
    season.mkdir()
    with duckdb.connect(str(season / "mlb_2026.duckdb")) as conn:
        conn.execute("CREATE TABLE pitches (game_pk BIGINT)")
        conn.execute("CREATE TABLE games (game_pk BIGINT, game_date DATE)")
        conn.execute("INSERT INTO games VALUES (1, '2026-07-01'), (2, '2026-07-02'), (3, '2026-07-03')")
        if with_lookups:
            conn.execute("CREATE TABLE pitch_play_lookup (game_pk BIGINT, video_url VARCHAR)")
            conn.execute("INSERT INTO pitch_play_lookup VALUES (1, 'url'), (2, 'url'), (999, 'url')")
            conn.execute("CREATE TABLE game_player_lookup (game_pk BIGINT)")
            conn.execute("INSERT INTO game_player_lookup VALUES (1), (3), (999)")
    status = video_service.get_video_lookup_status(2026, data_dir=tmp_path)
    assert status["season_games"] == 3
    assert status["complete_games"] == expected_complete
    assert status["missing_games"] == 3 - expected_complete
