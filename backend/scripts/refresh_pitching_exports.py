from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.ml.pitching_plus import refresh_pitching_exports


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-center Pitching+ and export a complete season.")
    parser.add_argument("--data-dir", type=Path, default=settings.data_dir)
    parser.add_argument("--artifact-dir", type=Path, default=settings.data_dir / "models" / "pitching_plus")
    parser.add_argument("--reference-year", type=int, default=2025)
    parser.add_argument("--export-year", type=int, default=2026)
    args = parser.parse_args()
    metadata = refresh_pitching_exports(
        data_dir=args.data_dir,
        artifact_dir=args.artifact_dir,
        reference_year=args.reference_year,
        export_year=args.export_year,
    )
    print(json.dumps({"scale": metadata["pitching_plus_scale"], "exports": metadata["exports"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
