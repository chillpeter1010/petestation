from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.player_archetype_slice6d_service import (
    build_player_archetype_slice6d,
    slice6d_contract_path,
)


if __name__ == "__main__":
    payload = build_player_archetype_slice6d()
    print(
        json.dumps(
            {
                "status": payload["status"],
                "diagnostic_rows": payload["audit"]["diagnostic_rows"],
                "aggregate_entropy_diagnostic_ready": payload["release_gate"][
                    "aggregate_entropy_diagnostic_ready"
                ],
                "true_exploitability_ready": payload["release_gate"][
                    "true_exploitability_ready"
                ],
                "contract": str(slice6d_contract_path()),
                "report": str(
                    Path(__file__).resolve().parents[2]
                    / "docs"
                    / "PLAYER_ARCHETYPES_PITCH_STRATEGY.md"
                ),
            },
            indent=2,
        )
    )
