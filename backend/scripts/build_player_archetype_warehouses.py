from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.player_archetype_warehouse_service import build_player_archetype_warehouses  # noqa: E402


def main() -> None:
    payload = build_player_archetype_warehouses()
    print(
        json.dumps(
            {
                "status": payload["status"],
                "pitcher_rows": payload["audit"]["pitcher_rows"],
                "batter_rows": payload["audit"]["batter_rows"],
                "pitcher_duplicate_keys": payload["audit"]["pitcher_duplicate_keys"],
                "batter_duplicate_keys": payload["audit"]["batter_duplicate_keys"],
                "artifacts": payload["artifacts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
