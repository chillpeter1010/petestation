from __future__ import annotations

from fastapi import BackgroundTasks

from app.api.routes import admin as admin_routes


def test_catcher_ledger_route_runs_only_selected_year(monkeypatch) -> None:
    requested: list[tuple[int, int, bool]] = []
    monkeypatch.setattr(
        admin_routes,
        "run_slice1_year_update",
        lambda year, workers, force_rebuild: requested.append((year, workers, force_rebuild)) or {"status": "completed"},
    )

    def run_immediately(_tasks, name, year, fn):
        return {"name": name, "year": year, "result": fn()}

    monkeypatch.setattr(admin_routes, "_start_job", run_immediately)
    admin_routes.JOB_REGISTRY.clear()

    result = admin_routes.build_catcher_descriptive_ledger_job(
        BackgroundTasks(),
        year=2024,
        workers=7,
    )

    assert result["name"] == "catcher_descriptive_slice1"
    assert result["year"] == 2024
    assert requested == [(2024, 7, False)]


def test_catcher_ledger_route_does_not_start_a_second_active_job(monkeypatch) -> None:
    existing = {
        "job_id": "existing",
        "name": "catcher_descriptive_slice1",
        "year": 2022,
        "status": "running",
    }
    admin_routes.JOB_REGISTRY.clear()
    admin_routes.JOB_REGISTRY["existing"] = existing
    monkeypatch.setattr(
        admin_routes,
        "_start_job",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not start")),
    )

    result = admin_routes.build_catcher_descriptive_ledger_job(
        BackgroundTasks(),
        year=2025,
        workers=12,
    )

    assert result is existing
