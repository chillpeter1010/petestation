from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.catcher_pitch_calling_prework_service import (  # noqa: E402
    build_catcher_pitch_calling_prework,
    catcher_prework_path,
    catcher_prework_report_path,
)


def main() -> None:
    payload = build_catcher_pitch_calling_prework()
    print(
        json.dumps(
            {
                "status": payload["status"],
                "decision": payload["decision"],
                "output": str(catcher_prework_path()),
                "report": str(catcher_prework_report_path()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
