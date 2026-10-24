from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.catcher_descriptive_strategy_service import (  # noqa: E402
    build_catcher_descriptive_slice8_strategy_bridge,
    strategy_json_path,
    strategy_parquet_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Catcher Descriptive Metrics Slice 8 strategy bridge.")
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    payload = build_catcher_descriptive_slice8_strategy_bridge(args.data_dir)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "release_gate_passed": payload["release_gate_passed"],
                "summary": payload["summary"],
                "json": str(strategy_json_path(args.data_dir)),
                "parquet": str(strategy_parquet_path(args.data_dir)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
