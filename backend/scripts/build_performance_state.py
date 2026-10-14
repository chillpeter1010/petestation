from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.performance_state_service import refresh_performance_state
from app.services.performance_state_advanced_service import (
    refresh_performance_state_advanced,
    refresh_performance_state_tail,
)
from app.services.performance_state_forecast_service import (
    refresh_performance_state_forecasts,
    refresh_performance_state_shadow,
)
from app.services.performance_state_v2_service import refresh_performance_state_v2
from app.services.performance_state_v2_slice14_service import refresh_performance_state_v2_slice14
from app.services.performance_state_v2_slice15_service import refresh_performance_state_v2_slice15
from app.services.performance_state_v2_slice16_service import refresh_performance_state_v2_slice16
from app.services.performance_state_v2_slice17_service import refresh_performance_state_v2_slice17
from app.services.performance_state_v2_slice18_20_service import refresh_performance_state_v2_slice18_20
from app.services.performance_state_v2_slice21_22_service import refresh_performance_state_v2_slice21_22
from app.services.performance_state_v2_strict_replay_service import refresh_strict_2026_replay


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--slice4-6-only", action="store_true")
    group.add_argument("--slice7-only", action="store_true")
    group.add_argument("--slice8-9-only", action="store_true")
    group.add_argument("--slice11-only", action="store_true")
    group.add_argument("--slice11a-13-only", action="store_true")
    group.add_argument("--slice14-only", action="store_true")
    group.add_argument("--slice15-only", action="store_true")
    group.add_argument("--slice16-only", action="store_true")
    group.add_argument("--slice17-only", action="store_true")
    group.add_argument("--slice18-20-only", action="store_true")
    group.add_argument("--slice21-22-only", action="store_true")
    group.add_argument("--strict-2026-replay-only", action="store_true")
    args = parser.parse_args()
    if args.strict_2026_replay_only:
        result = refresh_strict_2026_replay()
    elif args.slice21_22_only:
        result = refresh_performance_state_v2_slice21_22()
    elif args.slice18_20_only:
        result = refresh_performance_state_v2_slice18_20()
    elif args.slice17_only:
        result = refresh_performance_state_v2_slice17()
    elif args.slice16_only:
        result = refresh_performance_state_v2_slice16()
    elif args.slice15_only:
        result = refresh_performance_state_v2_slice15()
    elif args.slice14_only:
        result = refresh_performance_state_v2_slice14()
    elif args.slice11a_13_only:
        result = refresh_performance_state_v2()
    elif args.slice11_only:
        result = refresh_performance_state_shadow()
    elif args.slice8_9_only:
        result = refresh_performance_state_forecasts()
    elif args.slice7_only:
        result = refresh_performance_state_tail()
    elif args.slice4_6_only:
        result = refresh_performance_state_advanced()
    else:
        refresh_performance_state()
        refresh_performance_state_advanced()
        refresh_performance_state_tail()
        refresh_performance_state_forecasts()
        result = refresh_performance_state_shadow()
    print(json.dumps(result, ensure_ascii=False, indent=2))
