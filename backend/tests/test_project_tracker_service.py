from __future__ import annotations

import json
from pathlib import Path

from app.services.project_tracker_service import (
    HANDOFF_PROGRESS_END,
    HANDOFF_PROGRESS_START,
    get_project_tracker,
    write_handoff_progress,
)


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


def test_handoff_progress_replaces_only_marked_block(tmp_path: Path) -> None:
    handoff = tmp_path / "NEXT_CHAT_HANDOFF.md"
    handoff.write_text(
        "\n".join(
            [
                "# Handoff",
                "",
                "Stable before",
                HANDOFF_PROGRESS_START,
                "old progress",
                HANDOFF_PROGRESS_END,
                "Stable after",
            ]
        ),
        encoding="utf-8",
    )
    payload = {
        "updated_at": "2026-10-24",
        "projects": [
            {
                "title": "Example | escaped",
                "status": "in_progress",
                "completed_slices": 1,
                "total_slices": 2,
                "next_step": "Next step",
            }
        ],
    }

    write_handoff_progress(payload, handoff)

    rendered = handoff.read_text(encoding="utf-8")
    assert "Stable before" in rendered
    assert "Stable after" in rendered
    assert "old progress" not in rendered
    assert "Example \\| escaped" in rendered
    assert "| in_progress | 1/2 | Next step |" in rendered


def test_project_tracker_counts_monitoring_projects_as_active(tmp_path: Path) -> None:
    path = tmp_path / "tracker.json"
    path.write_text(
        json.dumps(
            {
                "projects": [
                    {"status": "active", "slices": []},
                    {"status": "in_progress", "slices": []},
                    {"status": "done", "slices": []},
                ]
            }
        ),
        encoding="utf-8",
    )

    tracker = get_project_tracker(path)

    assert tracker["summary"]["active_projects"] == 2
