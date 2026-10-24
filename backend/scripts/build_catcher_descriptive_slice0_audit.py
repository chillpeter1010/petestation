from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.catcher_descriptive_audit_service import (  # noqa: E402
    audit_output_path,
    build_catcher_descriptive_slice0_audit,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the read-only catcher descriptive Slice 0 audit.")
    parser.add_argument(
        "--probe-official",
        action="store_true",
        help="Probe one high-scoring MLB Stats API game per year to verify runner accounting fields.",
    )
    args = parser.parse_args()
    payload = build_catcher_descriptive_slice0_audit(probe_official=args.probe_official)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "contract_version": payload["contract_version"],
                "years": payload["scope"]["years"],
                "output": str(audit_output_path()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
