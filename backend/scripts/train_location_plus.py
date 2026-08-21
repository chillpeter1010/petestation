from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.ml.location_plus import train_location_plus


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the independent Location+ model.")
    parser.add_argument("--data-dir", type=Path, default=settings.data_dir)
    parser.add_argument("--artifact-dir", type=Path, default=settings.data_dir / "models" / "location_plus")
    parser.add_argument("--estimators", type=int, default=220)
    parser.add_argument("--sample-fraction", type=float, default=1.0)
    args = parser.parse_args()

    metadata = train_location_plus(
        data_dir=args.data_dir,
        artifact_dir=args.artifact_dir,
        n_estimators=args.estimators,
        sample_fraction=args.sample_fraction,
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
