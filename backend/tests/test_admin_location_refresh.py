from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks

from app.api.routes import admin as admin_routes
from app.services import admin_service


def test_pitch_refresh_rebuilds_location_scores(monkeypatch) -> None:
    audit = {"complete": True, "missing_dates": []}
    monkeypatch.setattr(admin_service, "audit_pitch_coverage", lambda **_: dict(audit))
    monkeypatch.setattr(
        admin_service,
        "_import_legacy_pitcher_data_update",
        lambda: type("LegacyRefresh", (), {"refresh_pitcher_data": staticmethod(lambda **_: {"updated": True})}),
    )
    monkeypatch.setattr(admin_service, "sync_legacy_pitcher_refresh_outputs", lambda **_: {"files": []})

    child_jobs: list[dict[str, object]] = []

    def fake_child(payload: dict[str, object]) -> dict[str, object]:
        child_jobs.append(payload)
        return {
            "generated_at": "2026-08-10T00:00:00+00:00",
            "outing_rows": 1,
            "status": "current" if payload.get("job") == "pitch_stuff_scores" else "completed",
        }

    monkeypatch.setattr(admin_service, "_run_duckdb_write_child", fake_child)

    result = admin_service.run_pitcher_data_refresh(year=2026, include_pitch_stuff=True)

    assert child_jobs == [
        {"job": "pitcher_game_lines", "year": 2026},
        {"job": "starter_reference", "year": 2026},
        {"job": "location_scores", "year": 2026},
        {"job": "pitching_plus", "export_year": 2026, "reference_year": 2025},
        {"job": "pitch_stuff_scores", "year": 2026},
        {"job": "stuff_leaderboard", "year": 2026},
        {"job": "stamina_dataset", "year": 2026},
        {"job": "batter_lineup_scenarios", "year": 2026},
        {"job": "batter_timing", "year": 2026},
    ]
    assert result["location_plus"]["outing_rows"] == 1


def test_default_pitch_refresh_completes_pitch_stuff_and_rebuilds_stamina(monkeypatch) -> None:
    monkeypatch.setattr(admin_service, "audit_pitch_coverage", lambda **_: {"complete": True, "missing_dates": []})
    monkeypatch.setattr(admin_service, "classify_source_pending", lambda _: {"source_pending": False})
    monkeypatch.setattr(admin_service, "_import_legacy_pitcher_data_update", lambda: type("Updater", (), {"refresh_pitcher_data": staticmethod(lambda **_: {})}))
    monkeypatch.setattr(admin_service, "sync_legacy_pitcher_refresh_outputs", lambda **_: {})
    child_jobs = []
    monkeypatch.setattr(
        admin_service,
        "_run_duckdb_write_child",
        lambda payload: child_jobs.append(payload) or ({"status": "current"} if payload.get("job") == "pitch_stuff_scores" else {}),
    )

    admin_service.run_pitcher_data_refresh(year=2026)

    assert {"job": "pitch_stuff_scores", "year": 2026} in child_jobs
    assert {"job": "stamina_dataset", "year": 2026} in child_jobs
    assert not any("max_pitchers" in job for job in child_jobs if job.get("job") == "pitch_stuff_scores")


def test_optional_reference_refresh_preserves_previous_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(admin_service, "_run_duckdb_write_child", lambda _: (_ for _ in ()).throw(RuntimeError("offline")))

    result = admin_service._run_optional_refresh_child({"job": "batter_timing", "year": 2026})

    assert result["status"] == "stale"
    assert result["preserved_previous_snapshot"] is True


def test_duckdb_child_handles_missing_captured_output(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_service.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=None, stderr=None),
    )

    with pytest.raises(RuntimeError, match="exit code 1"):
        admin_service._run_duckdb_write_child({"job": "location_scores", "year": 2026})


def test_duckdb_child_forces_utf8_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout='{"ok": true, "result": {"label": "≤"}}\n', stderr="")

    monkeypatch.setattr(admin_service.subprocess, "run", fake_run)

    result = admin_service._run_duckdb_write_child({"job": "location_scores", "year": 2024})

    assert result == {"label": "≤"}
    assert captured["env"]["PYTHONIOENCODING"] == "utf-8"


def test_historical_plus_backfill_runs_all_stages_and_persists_progress(monkeypatch, tmp_path) -> None:
    for year in (2021, 2022):
        season_dir = tmp_path / f"MLB{year}"
        season_dir.mkdir()
        (season_dir / f"mlb_{year}.duckdb").touch()

    child_jobs: list[dict[str, object]] = []

    def fake_child(payload: dict[str, object]) -> dict[str, object]:
        child_jobs.append(payload)
        return {"status": "current" if payload["job"] == "pitch_stuff_scores" else "completed"}

    monkeypatch.setattr(admin_service, "_run_duckdb_write_child", fake_child)

    result = admin_service.run_historical_plus_backfill(2021, 2022, tmp_path)
    saved = admin_service.get_historical_plus_backfill_status(tmp_path)

    assert result["status"] == "completed"
    assert saved["status"] == "completed"
    assert saved["years"]["2021"]["status"] == "completed"
    assert saved["years"]["2022"]["status"] == "completed"
    assert child_jobs == [
        {"job": "location_scores", "year": 2021},
        {"job": "pitch_stuff_scores", "year": 2021},
        {"job": "pitching_plus", "export_year": 2021, "reference_year": 2021},
        {"job": "stuff_leaderboard", "year": 2021},
        {"job": "stamina_dataset", "year": 2021},
        {"job": "location_scores", "year": 2022},
        {"job": "pitch_stuff_scores", "year": 2022},
        {"job": "pitching_plus", "export_year": 2022, "reference_year": 2022},
        {"job": "stuff_leaderboard", "year": 2022},
        {"job": "stamina_dataset", "year": 2022},
    ]


def test_historical_plus_backfill_stops_dependent_stages_when_stuff_is_partial(monkeypatch, tmp_path) -> None:
    season_dir = tmp_path / "MLB2021"
    season_dir.mkdir()
    (season_dir / "mlb_2021.duckdb").touch()
    child_jobs: list[dict[str, object]] = []

    def fake_child(payload: dict[str, object]) -> dict[str, object]:
        child_jobs.append(payload)
        return {"status": "partial" if payload["job"] == "pitch_stuff_scores" else "completed"}

    monkeypatch.setattr(admin_service, "_run_duckdb_write_child", fake_child)

    result = admin_service.run_historical_plus_backfill(2021, 2021, tmp_path)

    assert result["status"] == "partial"
    assert result["failed_years"] == [2021]
    assert child_jobs == [
        {"job": "location_scores", "year": 2021},
        {"job": "pitch_stuff_scores", "year": 2021},
    ]


def test_historical_plus_resume_skips_completed_stages(monkeypatch, tmp_path) -> None:
    season_dir = tmp_path / "MLB2024"
    season_dir.mkdir()
    (season_dir / "mlb_2024.duckdb").touch()
    state_path = tmp_path / "admin_job_logs" / "historical_plus_backfill.json"
    state_path.parent.mkdir()
    state_path.write_text(json.dumps({
        "status": "partial",
        "years": {
            "2024": {
                "status": "failed",
                "stages": {
                    "location_plus": {"status": "completed"},
                    "pitch_stuff_plus": {"status": "current"},
                    "pitching_plus": {"status": "completed"},
                    "plus_leaderboard": {"status": "completed"},
                    "stamina_dataset": {"status": "failed", "error": "cp950"},
                },
            },
        },
    }), encoding="utf-8")
    child_jobs: list[dict[str, object]] = []
    monkeypatch.setattr(
        admin_service,
        "_run_duckdb_write_child",
        lambda payload: child_jobs.append(payload) or {"status": "completed"},
    )

    result = admin_service.run_historical_plus_backfill(2024, 2024, tmp_path)

    assert result["status"] == "completed"
    assert child_jobs == [{"job": "stamina_dataset", "year": 2024}]


def test_historical_plus_route_runs_only_selected_year(monkeypatch) -> None:
    requested: list[tuple[int, int]] = []
    monkeypatch.setattr(
        admin_routes,
        "run_historical_plus_backfill",
        lambda start_year, end_year: requested.append((start_year, end_year)) or {"status": "completed"},
    )

    def run_immediately(_tasks, name, year, fn):
        return {"name": name, "year": year, "result": fn()}

    monkeypatch.setattr(admin_routes, "_start_job", run_immediately)
    admin_routes.JOB_REGISTRY.clear()

    result = admin_routes.backfill_historical_plus_job(BackgroundTasks(), year=2024)

    assert result["year"] == 2024
    assert requested == [(2024, 2024)]
