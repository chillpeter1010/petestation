from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.arm_angle_backfill_service import backfill_2026_arm_angle  # noqa: E402


if __name__ == "__main__":
    result = backfill_2026_arm_angle()
    print(json.dumps({key: result[key] for key in ("status", "patched_rows", "before", "after")}, indent=2))
