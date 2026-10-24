from __future__ import annotations

import json

from app.services.player_archetype_slice3_service import build_player_archetype_slice3


if __name__ == "__main__":
    print(json.dumps(build_player_archetype_slice3(), ensure_ascii=False, indent=2))
