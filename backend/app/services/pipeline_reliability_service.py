from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def daily_state_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "admin_job_logs" / "daily_update_latest.json"


def daily_lock_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "admin_job_logs" / "daily_update.lock"


def daily_settings_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "admin_job_logs" / "daily_update_settings.json"


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def read_daily_update_settings(data_dir: Path | None = None) -> dict[str, Any]:
    path = daily_settings_path(data_dir)
    defaults = {
        "schema_version": 1,
        "game_updates_enabled": True,
        "transactions_always_enabled": True,
        "settings_path": str(path),
    }
    if not path.exists():
        return defaults
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {**defaults, "status": "invalid", "error": str(exc)}
    if not isinstance(payload, dict):
        return {**defaults, "status": "invalid", "error": "Daily settings are not an object."}
    return {
        **defaults,
        "game_updates_enabled": bool(payload.get("game_updates_enabled", True)),
        "updated_at": payload.get("updated_at"),
    }


def write_daily_update_settings(
    game_updates_enabled: bool,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    path = daily_settings_path(data_dir)
    payload = {
        "schema_version": 1,
        "game_updates_enabled": bool(game_updates_enabled),
        "transactions_always_enabled": True,
        "updated_at": utc_now(),
    }
    write_json_atomic(path, payload)
    return {**payload, "settings_path": str(path)}


def process_is_alive(pid: int | None) -> bool:
    if not pid or int(pid) <= 0:
        return False
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError):
        return False
    return True


def read_daily_update_state(
    data_dir: Path | None = None,
    *,
    recover_dead_process: bool = True,
) -> dict[str, Any]:
    path = daily_state_path(data_dir)
    if not path.exists():
        return {"status": "not_started", "steps": {}, "state_path": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "invalid", "steps": {}, "error": str(exc), "state_path": str(path)}
    if not isinstance(payload, dict):
        return {"status": "invalid", "steps": {}, "error": "Daily state is not an object.", "state_path": str(path)}

    payload["state_path"] = str(path)
    if recover_dead_process and payload.get("status") == "running" and not process_is_alive(payload.get("pid")):
        recovered_at = utc_now()
        payload.update(
            {
                "status": "interrupted",
                "finished_at": recovered_at,
                "recovery": {
                    "reason": "dead_process",
                    "detected_at": recovered_at,
                    "retryable": True,
                },
            }
        )
        for step in dict(payload.get("steps") or {}).values():
            if isinstance(step, dict) and step.get("status") == "running":
                step.update({"status": "interrupted", "finished_at": recovered_at, "retryable": True})
        persisted = dict(payload)
        persisted.pop("state_path", None)
        write_json_atomic(path, persisted)
    return payload


def acquire_daily_lock(data_dir: Path | None = None, *, pid: int | None = None) -> Path:
    path = daily_lock_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    owner = int(pid or os.getpid())
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            existing_pid = int(path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            existing_pid = 0
        if process_is_alive(existing_pid):
            raise RuntimeError(f"Petehub daily update is already running as PID {existing_pid}.")
        path.unlink(missing_ok=True)
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(descriptor, str(owner).encode("ascii"))
    finally:
        os.close(descriptor)
    return path
