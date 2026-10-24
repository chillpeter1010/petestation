from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.player_archetype_challenger_service import build_player_archetype_challenger  # noqa: E402


def main() -> None:
    payload = build_player_archetype_challenger()
    print(
        json.dumps(
            {
                "status": payload["status"],
                "pitcher": payload["audit"]["pitcher"],
                "batter": payload["audit"]["batter"],
                "artifacts": payload["artifacts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
