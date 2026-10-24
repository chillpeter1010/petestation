from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.player_archetype_slice5a_location_service import (  # noqa: E402
    build_player_archetype_slice5a,
    slice5a_contract_path,
    slice5a_pitch_path,
    slice5a_report_path,
)


if __name__ == "__main__":
    payload = build_player_archetype_slice5a()
    print(
        json.dumps(
            {
                "status": payload["status"],
                "rows": payload["audit"]["rows"],
                "meatball_pct": payload["audit"]["meatball_pct"],
                "contract": str(slice5a_contract_path()),
                "locations": str(slice5a_pitch_path()),
                "report": str(slice5a_report_path()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
