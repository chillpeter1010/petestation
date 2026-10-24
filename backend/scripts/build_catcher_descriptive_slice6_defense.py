from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.catcher_descriptive_defense_service import (  # noqa: E402
    DEFAULT_YEARS,
    build_catcher_descriptive_slice6_defense,
    defense_catcher_parquet_path,
    defense_json_path,
    defense_team_parquet_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Catcher Descriptive Metrics Slice 6 DRS artifacts.")
    parser.add_argument("--years", nargs="+", type=int, default=list(DEFAULT_YEARS))
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    payload = build_catcher_descriptive_slice6_defense(args.years, source_path=args.source)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "release_gate_passed": payload["release_gate_passed"],
                "years": payload["years"],
                "row_counts": payload["row_counts"],
                "reconciliation": payload["reconciliation"],
                "cross_year_diagnostics": payload["cross_year_diagnostics"],
                "json": str(defense_json_path()),
                "team_parquet": str(defense_team_parquet_path()),
                "catcher_parquet": str(defense_catcher_parquet_path()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
