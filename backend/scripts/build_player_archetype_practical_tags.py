from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.player_archetype_practical_tag_service import build_player_archetype_practical_tags


if __name__ == "__main__":
    print(json.dumps(build_player_archetype_practical_tags(), ensure_ascii=False, indent=2))
