from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.services.payroll.importer import fetch_payroll_markdown, parse_payroll_markdown, write_payroll_snapshot
from app.services.payroll.team_slugs import TEAM_PAYROLL_SLUGS


def refresh_team(team_code: str, season: int, data_dir: Path) -> Path:
    markdown = fetch_payroll_markdown(team_code)
    payload = parse_payroll_markdown(markdown, team_code, season)
    if not payload["guaranteed_players"] or not payload["estimated_payroll_by_year"]:
        raise ValueError("FanGraphs payroll tables were incomplete")
    return write_payroll_snapshot(payload, team_code, season, data_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh weekly FanGraphs payroll snapshots.")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--team", action="append", help="Team code; repeat for multiple teams. Defaults to all 30.")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    teams = [team.upper() for team in args.team] if args.team else sorted(TEAM_PAYROLL_SLUGS)
    failures: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 4))) as executor:
        jobs = {executor.submit(refresh_team, team, args.year, Path(settings.data_dir)): team for team in teams}
        for future in as_completed(jobs):
            team = jobs[future]
            try:
                print(f"{team}: {future.result()}")
            except Exception as exc:
                failures.append((team, str(exc)))
                print(f"{team}: ERROR {exc}")

    if failures:
        print(f"Completed with {len(failures)} failure(s): {', '.join(team for team, _ in failures)}")
        return 1
    print(f"Updated {len(teams)} payroll snapshots.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
