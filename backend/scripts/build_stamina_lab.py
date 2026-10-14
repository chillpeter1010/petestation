from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.stamina_lab_service import (
    refresh_stamina_external_validation,
    refresh_stamina_season_bias_repair,
    refresh_stamina_game_states,
    refresh_stamina_dataset,
    refresh_stamina_season_summaries,
    refresh_stamina_slice11,
)
from app.services.physical_stability_service import refresh_physical_stability
from app.services.command_retention_service import refresh_product_integration, refresh_slices_17_18


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Build Stamina Lab artifacts.")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--slice11-only", action="store_true", help="Build Slice 11 from existing immutable artifacts.")
    parser.add_argument("--game-state-only", action="store_true", help="Build observed single-game and season-timeline Stamina+ artifacts only.")
    parser.add_argument("--season-summary-only", action="store_true", help="Build Slice 12 season summaries from existing game-state artifacts only.")
    parser.add_argument("--external-validation-only", action="store_true", help="Build Slice 13 cross-season validation from frozen observed-state artifacts.")
    parser.add_argument("--season-bias-repair-only", action="store_true", help="Build Slice 13A season ceiling correction and untouched-year audit.")
    parser.add_argument("--physical-stability-only", action="store_true", help="Build Slice 15–16 physical-signal contract and Physical Stability+ artifacts.")
    parser.add_argument("--command-validation-only", action="store_true", help="Build Slice 17 Command Retention+ and Slice 18 incremental validation artifacts.")
    parser.add_argument("--product-integration-only", action="store_true", help="Build the Slice 19 separate-panel product decision and representative-player audit.")
    args = parser.parse_args()
    if sum([args.slice11_only, args.game_state_only, args.season_summary_only, args.external_validation_only, args.season_bias_repair_only, args.physical_stability_only, args.command_validation_only, args.product_integration_only]) > 1:
        parser.error("Choose only one partial rebuild mode.")
    if args.product_integration_only:
        result = refresh_product_integration(args.year)
    elif args.command_validation_only:
        result = refresh_slices_17_18(args.year)
    elif args.physical_stability_only:
        result = refresh_physical_stability(args.year)
    elif args.season_bias_repair_only:
        result = refresh_stamina_season_bias_repair(args.year)
    elif args.external_validation_only:
        result = refresh_stamina_external_validation(args.year)
    elif args.season_summary_only:
        result = refresh_stamina_season_summaries(args.year)
    elif args.game_state_only:
        result = refresh_stamina_game_states(args.year)
    elif args.slice11_only:
        result = refresh_stamina_slice11(args.year)
    else:
        result = refresh_stamina_dataset(args.year)
    print(json.dumps(result, ensure_ascii=False, indent=2))
