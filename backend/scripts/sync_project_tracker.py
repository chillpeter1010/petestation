from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.project_tracker_service import write_project_tracker_documents


if __name__ == "__main__":
    for output in write_project_tracker_documents():
        print(output)
