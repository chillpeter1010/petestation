from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.services.plus_v2_research_service import build_slice7, build_slice8, build_slice8b, build_slice9, build_slice10


def main() -> None:
    parser = argparse.ArgumentParser(description="Build research-only Plus v2 Slice 7-9 artifacts")
    parser.add_argument("--slice", choices=("7", "8", "8b", "9", "10", "all"), default="all")
    parser.add_argument("--data-dir", type=Path, default=settings.data_dir)
    args = parser.parse_args()
    builders = {"7": build_slice7, "8": build_slice8, "8b": build_slice8b, "9": build_slice9, "10": build_slice10}
    selected = ("7", "8", "8b", "9", "10") if args.slice == "all" else (args.slice,)
    for slice_id in selected:
        result = builders[slice_id](args.data_dir)
        print(f"slice{slice_id}: {result['artifact']} -> {result['generated_at']}")


if __name__ == "__main__":
    main()
