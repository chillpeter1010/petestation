from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.player_archetype_slice6ab_service import (  # noqa: E402
    build_player_archetype_slice6ab,
    slice6a_candidate_path,
    slice6a_chosen_path,
    slice6ab_contract_path,
    slice6ab_report_path,
    slice6b_surface_path,
)


if __name__ == "__main__":
    payload = build_player_archetype_slice6ab()
    print(
        json.dumps(
            {
                "status": payload["status"],
                "weapon_candidates": payload["audit"]["slice6a"]["candidate_rows"],
                "decisions": payload["audit"]["slice6a"]["decision_rows"],
                "threat_surface_rows": payload["audit"]["slice6b"]["rows"],
                "contract": str(slice6ab_contract_path()),
                "weapon_candidate_path": str(slice6a_candidate_path()),
                "weapon_chosen_path": str(slice6a_chosen_path()),
                "threat_surface_path": str(slice6b_surface_path()),
                "report": str(slice6ab_report_path()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
