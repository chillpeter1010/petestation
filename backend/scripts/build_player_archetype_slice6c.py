from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.player_archetype_slice6c_service import (  # noqa: E402
    build_player_archetype_slice6c,
    slice6c_candidate_value_path,
    slice6c_contract_path,
    slice6c_decision_value_path,
    slice6c_report_path,
)


if __name__ == "__main__":
    payload = build_player_archetype_slice6c()
    print(
        json.dumps(
            {
                "status": payload["status"],
                "decisions": payload["audit"]["decisions"],
                "multi_candidate_coverage": payload["audit"]["default_multi_candidate_coverage"],
                "aggregate_supported_value_ready": payload["release_gate"]["aggregate_supported_value_ready"],
                "contract": str(slice6c_contract_path()),
                "candidate_values": str(slice6c_candidate_value_path()),
                "decision_values": str(slice6c_decision_value_path()),
                "report": str(slice6c_report_path()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
