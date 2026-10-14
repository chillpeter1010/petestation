from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.services.pitch_stuff_cache_service import refresh_pitch_stuff_scores


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill cached per-pitch Pete Stuff+ scores.")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--shard-count", type=int)
    args = parser.parse_args()
    result = refresh_pitch_stuff_scores(
        year=args.year,
        data_dir=settings.data_dir,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
