from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.player_archetype_slice4_service import (  # noqa: E402
    DEFAULT_YEARS,
    build_player_archetype_slice4,
    slice4_contract_path,
    slice4_report_path,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build chronological Slice 4 pitch-decision warehouses.")
    parser.add_argument("--year", action="append", type=int, dest="years")
    args = parser.parse_args()
    years = tuple(args.years) if args.years else DEFAULT_YEARS
    payload = build_player_archetype_slice4(years=years)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "years": payload["scope"]["years"],
                "rows": payload["totals"]["rows"],
                "integrity_passed": payload["integrity_passed"],
                "contract": str(slice4_contract_path()),
                "report": str(slice4_report_path()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
