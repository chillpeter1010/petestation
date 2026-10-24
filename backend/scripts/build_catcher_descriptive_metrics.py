from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.catcher_descriptive_metrics_service import build_catcher_descriptive_metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Build provisional Catcher Descriptive Metrics Slice 2–3 artifacts.")
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()
    result = build_catcher_descriptive_metrics(args.year)
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
