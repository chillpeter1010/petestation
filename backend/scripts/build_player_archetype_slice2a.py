from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.player_archetype_slice2a_service import build_player_archetype_slice2a  # noqa: E402


if __name__ == "__main__":
    result = build_player_archetype_slice2a()
    print(json.dumps({"status": result["status"], "audit": result["audit"], "artifacts": result["artifacts"]}, ensure_ascii=False, indent=2))
