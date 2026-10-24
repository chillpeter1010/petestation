from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.catcher_descriptive_closeout_service import (  # noqa: E402
    build_catcher_descriptive_slice123_closeout,
    closeout_json_path,
)


def main() -> int:
    payload = build_catcher_descriptive_slice123_closeout()
    print(json.dumps({
        "status": payload["status"],
        "contract_version": payload["contract_version"],
        "years": payload["years"],
        "totals": payload["totals"],
        "output": str(closeout_json_path()),
    }, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
