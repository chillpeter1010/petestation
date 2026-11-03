from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.services import pipeline_reliability_service as reliability
from app.services.pitch_refresh_service import mlb_source_date
from scripts import daily_update


def test_mlb_source_date_uses_new_york_calendar() -> None:
    instant = datetime(2026, 10, 14, 2, 30, tzinfo=timezone.utc)
    assert mlb_source_date(instant).isoformat() == "2026-10-13"


def test_dead_daily_process_is_marked_interrupted(monkeypatch, tmp_path: Path) -> None:
    path = reliability.daily_state_path(tmp_path)
    reliability.write_json_atomic(
        path,
        {
            "status": "running",
            "pid": 12345,
            "steps": {"pitch_data": {"status": "running"}},
        },
    )
    monkeypatch.setattr(reliability, "process_is_alive", lambda _pid: False)

    result = reliability.read_daily_update_state(tmp_path)

    assert result["status"] == "interrupted"
    assert result["recovery"]["reason"] == "dead_process"
    assert result["steps"]["pitch_data"]["status"] == "interrupted"


def test_dead_lock_is_recovered(monkeypatch, tmp_path: Path) -> None:
    lock = reliability.daily_lock_path(tmp_path)
    lock.parent.mkdir(parents=True)
    lock.write_text("12345", encoding="ascii")
    monkeypatch.setattr(reliability, "process_is_alive", lambda _pid: False)

    acquired = reliability.acquire_daily_lock(tmp_path, pid=67890)

    assert acquired.read_text(encoding="ascii") == "67890"


def test_retry_selection_keeps_only_retryable_steps_and_freshness() -> None:
    args = argparse.Namespace(step=None, retry_failed=True)
    previous = {
        "steps": {
            "pitch_data": {"status": "failed"},
            "video_lookup": {"status": "completed"},
            "stamina_dataset": {"status": "blocked"},
        }
    }

    assert daily_update._selected_steps(args, previous) == [
        "pitch_data",
        "stamina_dataset",
        "data_freshness",
    ]


def test_offseason_daily_selection_keeps_transactions_and_freshness() -> None:
    args = argparse.Namespace(step=None, retry_failed=False)

    assert daily_update._selected_steps(
        args,
        {},
        game_updates_enabled=False,
    ) == ["transactions", "data_freshness"]


def test_daily_update_settings_are_atomic_and_keep_transactions_enabled(tmp_path: Path) -> None:
    defaults = reliability.read_daily_update_settings(tmp_path)
    assert defaults["game_updates_enabled"] is True
    assert defaults["transactions_always_enabled"] is True

    updated = reliability.write_daily_update_settings(False, tmp_path)
    reloaded = reliability.read_daily_update_settings(tmp_path)

    assert updated["game_updates_enabled"] is False
    assert reloaded["game_updates_enabled"] is False
    assert reloaded["transactions_always_enabled"] is True


def test_daily_pipeline_continues_unrelated_steps_after_failure(monkeypatch, tmp_path: Path) -> None:
    executed: list[str] = []

    def run_step(name: str, year: int) -> dict[str, object]:
        executed.append(name)
        if name == "pitch_data":
            raise RuntimeError("source offline")
        return {"status": "current", "year": year}

    monkeypatch.setattr(daily_update.settings, "data_dir", tmp_path)
    monkeypatch.setattr(daily_update, "run_daily_pipeline_step", run_step)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "daily_update.py",
            "--year",
            "2026",
            "--step",
            "pitch_data",
            "--step",
            "video_lookup",
            "--step",
            "data_freshness",
            "--heartbeat-seconds",
            "1",
        ],
    )

    assert daily_update.main() == 1
    state = json.loads(reliability.daily_state_path(tmp_path).read_text(encoding="utf-8"))
    assert executed == ["pitch_data", "video_lookup", "data_freshness"]
    assert state["status"] == "partial"
    assert state["steps"]["pitch_data"]["status"] == "failed"
    assert state["steps"]["video_lookup"]["status"] == "completed"
    assert state["steps"]["data_freshness"]["status"] == "completed"
