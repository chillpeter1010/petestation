"""Offline preprocessing only; run python backend/scripts/build_batter_zone_baseline.py --year 2026."""
from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path
from app.services.batter_zone_baseline_service import build_baseline

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()
    build_baseline(args.year, get_season_duckdb_path(args.year, settings.data_dir), progress=lambda msg: print(msg, flush=True))
