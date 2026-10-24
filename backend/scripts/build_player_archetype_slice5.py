from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.player_archetype_slice5_service import (  # noqa: E402
    build_player_archetype_slice5,
    slice5_contract_path,
    slice5_model_path,
    slice5_prediction_path,
    slice5_report_path,
)


if __name__ == "__main__":
    payload = build_player_archetype_slice5()
    print(
        json.dumps(
            {
                "status": payload["status"],
                "selected_base": payload["selection"]["selected_base"],
                "selected_family_model": payload["selection"]["selected_family_model"],
                "hierarchical_release_supported": payload["selection"]["hierarchical_release_supported"],
                "contract": str(slice5_contract_path()),
                "models": str(slice5_model_path()),
                "predictions": str(slice5_prediction_path()),
                "report": str(slice5_report_path()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
