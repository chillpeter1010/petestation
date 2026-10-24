from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.player_archetype_audit_service import (  # noqa: E402
    archetype_slice0_path,
    archetype_slice0_report_path,
    build_player_archetype_slice0_audit,
)


def main() -> None:
    payload = build_player_archetype_slice0_audit()
    summary = {
        "status": payload["status"],
        "years": payload["scope"]["years"],
        "old_archetype_rows": payload["prior_work"].get("rows", 0),
        "slice1_proceed": payload["slice1_decision"]["proceed"],
        "output": str(archetype_slice0_path()),
        "report": str(archetype_slice0_report_path()),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
