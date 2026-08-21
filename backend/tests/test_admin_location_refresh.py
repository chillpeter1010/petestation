from __future__ import annotations

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
        return {"generated_at": "2026-08-10T00:00:00+00:00", "outing_rows": 1}

    monkeypatch.setattr(admin_service, "_run_duckdb_write_child", fake_child)

    result = admin_service.run_pitcher_data_refresh(year=2026)

    assert child_jobs == [
        {"job": "pitcher_game_lines", "year": 2026},
        {"job": "location_scores", "year": 2026},
        {"job": "pitch_stuff_scores", "year": 2026},
    ]
    assert result["location_plus"]["outing_rows"] == 1
