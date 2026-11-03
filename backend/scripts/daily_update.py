from __future__ import annotations

import argparse
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, TextIO

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.services.admin_service import (
    DAILY_ALWAYS_PIPELINE_STEPS,
    DAILY_GAME_PIPELINE_STEPS,
    DAILY_PIPELINE_STEPS,
    run_daily_pipeline_step,
)
from app.services.pipeline_reliability_service import (
    acquire_daily_lock,
    daily_state_path,
    read_daily_update_settings,
    read_daily_update_state,
    utc_now,
    write_json_atomic,
)


DEPENDENCIES = {
    "plus_leaderboard": {"location_plus", "pitch_stuff_plus"},
    "stamina_dataset": {"location_plus", "pitch_stuff_plus"},
}


class Tee:
    def __init__(self, console: TextIO, durable: TextIO) -> None:
        self.console = console
        self.durable = durable

    def write(self, text: str) -> int:
        self.console.write(text)
        written = self.durable.write(text)
        self.durable.flush()
        return written

    def flush(self) -> None:
        self.console.flush()
        self.durable.flush()


def _result_summary(result: dict[str, object]) -> dict[str, object]:
    summary: dict[str, object] = {}
    for key in [
        "status",
        "data_as_of",
        "generated_at",
        "source_through",
        "overall_status",
        "fetched_at",
        "period_end",
        "source_status",
        "updated_count",
        "failed_count",
        "outputs",
    ]:
        if key in result:
            summary[key] = result[key]
    coverage = result.get("coverage")
    if isinstance(coverage, dict):
        summary["coverage"] = {
            key: coverage.get(key)
            for key in ["status", "latest_official_date", "latest_local_date", "missing_games", "complete"]
        }
    summary["result_keys"] = sorted(result)
    return summary


def _selected_steps(
    args: argparse.Namespace,
    previous: dict[str, Any],
    *,
    game_updates_enabled: bool | None = None,
) -> list[str]:
    if args.step:
        return list(dict.fromkeys(args.step))
    if args.retry_failed:
        retryable = {"failed", "interrupted", "blocked"}
        selected = [
            name
            for name in DAILY_PIPELINE_STEPS
            if str((previous.get("steps") or {}).get(name, {}).get("status")) in retryable
        ]
        if selected and "data_freshness" not in selected:
            selected.append("data_freshness")
        return selected
    enabled = (
        read_daily_update_settings(settings.data_dir)["game_updates_enabled"]
        if game_updates_enabled is None
        else bool(game_updates_enabled)
    )
    return [
        *(DAILY_GAME_PIPELINE_STEPS if enabled else ()),
        *DAILY_ALWAYS_PIPELINE_STEPS,
    ]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run the Petehub daily data pipeline with resumable steps.")
    parser.add_argument("--year", type=int, default=datetime.now().year)
    parser.add_argument("--step", action="append", choices=DAILY_PIPELINE_STEPS, help="Run only this step; repeat for multiple steps.")
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed, interrupted, or blocked steps from the latest run.")
    parser.add_argument("--heartbeat-seconds", type=float, default=30.0, help=argparse.SUPPRESS)
    parser.add_argument("--include-pitch-stuff", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    log_dir = settings.data_dir / "admin_job_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    stdout_path = log_dir / f"daily_update_{stamp}.stdout.log"
    stderr_path = log_dir / f"daily_update_{stamp}.stderr.log"
    stdout_file = stdout_path.open("a", encoding="utf-8")
    stderr_file = stderr_path.open("a", encoding="utf-8")
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = Tee(original_stdout, stdout_file)  # type: ignore[assignment]
    sys.stderr = Tee(original_stderr, stderr_file)  # type: ignore[assignment]

    try:
        lock_path = acquire_daily_lock(settings.data_dir)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        stdout_file.close()
        stderr_file.close()
        return 2

    state_path = daily_state_path(settings.data_dir)
    previous = read_daily_update_state(settings.data_dir)
    daily_settings = read_daily_update_settings(settings.data_dir)
    selected = _selected_steps(
        args,
        previous,
        game_updates_enabled=bool(daily_settings["game_updates_enabled"]),
    )
    state_lock = threading.Lock()
    started = datetime.now(timezone.utc)
    state: dict[str, Any] = {
        "schema_version": 2,
        "status": "running",
        "pid": os.getpid(),
        "year": int(args.year),
        "started_at": started.isoformat(timespec="seconds"),
        "heartbeat_at": utc_now(),
        "selected_steps": selected,
        "game_updates_enabled": bool(daily_settings["game_updates_enabled"]),
        "transactions_always_enabled": True,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "steps": {},
    }
    if args.retry_failed and int(previous.get("year") or 0) == int(args.year):
        state["steps"] = dict(previous.get("steps") or {})

    def persist() -> None:
        with state_lock:
            state["heartbeat_at"] = utc_now()
            write_json_atomic(state_path, state)

    persist()
    failed = False
    try:
        if not selected:
            state["status"] = "completed"
            state["message"] = "No failed or interrupted steps required a retry."
        for name in selected:
            failed_dependencies = [
                dependency
                for dependency in DEPENDENCIES.get(name, set())
                if dependency in selected and state["steps"].get(dependency, {}).get("status") != "completed"
            ]
            if failed_dependencies:
                state["steps"][name] = {
                    "status": "blocked",
                    "blocked_by": sorted(failed_dependencies),
                    "finished_at": utc_now(),
                    "retryable": True,
                }
                failed = True
                persist()
                continue

            prior_attempts = int(state["steps"].get(name, {}).get("attempt") or 0)
            step_started = perf_counter()
            state["steps"][name] = {
                "status": "running",
                "attempt": prior_attempts + 1,
                "started_at": utc_now(),
                "heartbeat_at": utc_now(),
            }
            persist()
            stop_heartbeat = threading.Event()

            def heartbeat(step_name: str = name) -> None:
                while not stop_heartbeat.wait(max(1.0, float(args.heartbeat_seconds))):
                    state["steps"][step_name]["heartbeat_at"] = utc_now()
                    persist()

            heartbeat_thread = threading.Thread(target=heartbeat, name=f"heartbeat-{name}", daemon=True)
            heartbeat_thread.start()
            try:
                print(f"[{utc_now()}] starting {name}")
                result = run_daily_pipeline_step(name, year=int(args.year))
                state["steps"][name].update(
                    {
                        "status": "completed",
                        "finished_at": utc_now(),
                        "seconds": round(perf_counter() - step_started, 2),
                        "result": _result_summary(result),
                    }
                )
                print(f"[{utc_now()}] completed {name}")
            except Exception as exc:
                failed = True
                state["steps"][name].update(
                    {
                        "status": "failed",
                        "finished_at": utc_now(),
                        "seconds": round(perf_counter() - step_started, 2),
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                        "retryable": True,
                    }
                )
                print(f"[{utc_now()}] failed {name}: {exc}", file=sys.stderr)
            finally:
                stop_heartbeat.set()
                heartbeat_thread.join(timeout=2)
                persist()

        state["status"] = "partial" if failed else "completed"
        state["finished_at"] = utc_now()
        state["total_seconds"] = round((datetime.now(timezone.utc) - started).total_seconds(), 2)
        persist()
        print(f"Daily update finished with status={state['status']}")
        return 1 if failed else 0
    finally:
        lock_path.unlink(missing_ok=True)
        stdout_file.flush()
        stderr_file.flush()
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        stdout_file.close()
        stderr_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
