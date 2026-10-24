from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.catcher_descriptive_ledger_service import DEFAULT_YEARS, build_slice1


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Catcher Descriptive Metrics Slice 1 ledger.")
    parser.add_argument("--years", nargs="+", type=int, default=list(DEFAULT_YEARS))
    parser.add_argument("--fetch", action="store_true", help="Download missing immutable MLB game-feed snapshots.")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    result = build_slice1(years=args.years, fetch=args.fetch, workers=args.workers)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
