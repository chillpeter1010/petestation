from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.catcher_descriptive_reliability_service import (  # noqa: E402
    DEFAULT_YEARS,
    build_catcher_descriptive_slice4_reliability,
    reliability_json_path,
    reliability_parquet_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Catcher Descriptive Metrics Slice 4 reliability artifacts.")
    parser.add_argument("--years", nargs="+", type=int, default=list(DEFAULT_YEARS))
    args = parser.parse_args()
    payload = build_catcher_descriptive_slice4_reliability(args.years)
    print(json.dumps({
        "status": "completed",
        "years": payload["years"],
        "cross_year": payload["cross_year"],
        "dominant_pair": payload["dominant_pair"],
        "summary": payload["summary"],
        "json": str(reliability_json_path()),
        "parquet": str(reliability_parquet_path()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
