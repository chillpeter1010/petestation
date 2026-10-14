from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.services.admin_service import (
    run_pitcher_data_refresh,
    run_pitcher_game_line_backfill,
    run_roster_reference_refresh,
    run_video_lookup_backfill,
)
from app.services.data_freshness_service import refresh_data_freshness_report


def write_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temp_path.replace(path)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run the complete Petehub daily data pipeline.")
    parser.add_argument("--year", type=int, default=datetime.now().year)
    parser.add_argument(
        "--include-pitch-stuff",
        action="store_true",
        help="Deprecated compatibility flag; per-pitch Stuff+ is now always completed and verified.",
    )
    args = parser.parse_args()

    log_dir = settings.data_dir / "admin_job_logs"
    lock_path = log_dir / "daily_update.lock"
    state_path = log_dir / "daily_update_latest.json"
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
    except FileExistsError:
        age_seconds = datetime.now().timestamp() - lock_path.stat().st_mtime
        if age_seconds < 6 * 60 * 60:
            print("Petehub daily update is already running.")
            return 2
        lock_path.unlink(missing_ok=True)
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)

    started = datetime.now()
    state: dict[str, object] = {
        "status": "running",
        "year": args.year,
        "started_at": started.isoformat(timespec="seconds"),
        "steps": {},
    }
    write_state(state_path, state)
    failed = False
    try:
        game_steps = [
            (
                "pitch_data",
                lambda: run_pitcher_data_refresh(
                    year=args.year,
                    include_pitch_stuff=args.include_pitch_stuff,
                ),
            ),
            ("video_lookup", lambda: run_video_lookup_backfill(year=args.year)),
            ("pitcher_game_lines", lambda: run_pitcher_game_line_backfill(year=args.year)),
        ]
        for name, task in game_steps:
            step_started = perf_counter()
            try:
                result = task()
                state["steps"][name] = {"status": "completed", "seconds": round(perf_counter() - step_started, 2), "result": result}  # type: ignore[index]
            except Exception as exc:
                state["steps"][name] = {"status": "failed", "seconds": round(perf_counter() - step_started, 2), "error": str(exc)}  # type: ignore[index]
                failed = True
                break
            finally:
                write_state(state_path, state)

        roster_started = perf_counter()
        try:
            roster_result = run_roster_reference_refresh(year=args.year)
            state["steps"]["roster_data"] = {"status": "completed", "seconds": round(perf_counter() - roster_started, 2), "result": roster_result}  # type: ignore[index]
        except Exception as exc:
            state["steps"]["roster_data"] = {"status": "failed", "seconds": round(perf_counter() - roster_started, 2), "error": str(exc)}  # type: ignore[index]
            failed = True

        freshness_started = perf_counter()
        try:
            freshness_result = refresh_data_freshness_report(year=args.year)
            state["steps"]["data_freshness"] = {  # type: ignore[index]
                "status": "completed",
                "seconds": round(perf_counter() - freshness_started, 2),
                "result": {
                    "overall_status": freshness_result.get("overall_status"),
                    "generated_at": freshness_result.get("generated_at"),
                    "outputs": freshness_result.get("outputs"),
                },
            }
        except Exception as exc:
            state["steps"]["data_freshness"] = {  # type: ignore[index]
                "status": "failed",
                "seconds": round(perf_counter() - freshness_started, 2),
                "error": str(exc),
            }
            failed = True

        state["status"] = "failed" if failed else "completed"
        state["finished_at"] = datetime.now().isoformat(timespec="seconds")
        state["total_seconds"] = round((datetime.now() - started).total_seconds(), 2)
        write_state(state_path, state)
        print(json.dumps(state, ensure_ascii=False, default=str))
        return 1 if failed else 0
    finally:
        lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
