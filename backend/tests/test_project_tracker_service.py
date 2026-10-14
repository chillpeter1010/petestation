from __future__ import annotations

import json
from pathlib import Path

from app.services.project_tracker_service import get_project_tracker


def test_project_tracker_computes_slice_progress_and_handoff(tmp_path: Path) -> None:
    path = tmp_path / "tracker.json"
    path.write_text(
        json.dumps(
            {
                "updated_at": "2026-09-26",
                "projects": [
                    {
                        "id": "example",
                        "title": "Example",
                        "area": "Lab",
                        "status": "in_progress",
                        "summary": "Summary",
                        "next_step": "Next",
                        "slices": [
                            {"id": "0", "label": "Slice 0", "status": "done", "deliverable": "A", "verification": "Passed"},
                            {"id": "1", "label": "Slice 1", "status": "planned", "deliverable": "B", "verification": "Pending"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    tracker = get_project_tracker(path)
    assert tracker["projects"][0]["progress"] == 50
    assert tracker["summary"]["completed_slices"] == 1
    assert tracker["summary"]["active_projects"] == 1
    assert "## Example" in tracker["handoff_markdown"]
