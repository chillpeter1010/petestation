from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.admin_service import run_historical_plus_backfill


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume the historical Plus backfill with 2025 first.")
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=2025)
    args = parser.parse_args()
    result = run_historical_plus_backfill(start_year=args.start_year, end_year=args.end_year)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
