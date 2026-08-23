from __future__ import annotations

import argparse

from app.services.batter_swing_timing_service import refresh_batter_timing_cache


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh Savant batter Swing Timing / Miss Distance caches.")
    parser.add_argument("--years", nargs="+", type=int, default=[2023, 2024, 2025, 2026])
    parser.add_argument("--hands", nargs="+", choices=["All", "L", "R"], default=["All", "L", "R"])
    args = parser.parse_args()
    for year in args.years:
        for hand in args.hands:
            meta = refresh_batter_timing_cache(year, hand)
            print(f"{year} {hand}: {meta['rows']} rows -> {meta['output']}")


if __name__ == "__main__":
    main()
