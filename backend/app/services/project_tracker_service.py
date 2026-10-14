from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TRACKER_PATH = PROJECT_ROOT / "docs" / "PROJECT_TRACKER.json"


def _progress(project: dict[str, Any]) -> dict[str, Any]:
    slices = list(project.get("slices") or [])
    completed = sum(1 for item in slices if item.get("status") == "done")
    total = len(slices)
    progress = round(completed * 100 / total) if total else 0
    enriched = dict(project)
    enriched.update({"completed_slices": completed, "total_slices": total, "progress": progress})
    return enriched


def render_project_tracker_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Petehub Project Tracker",
        "",
        f"Updated: {payload.get('updated_at')}",
        "",
        "This file is generated from `docs/PROJECT_TRACKER.json`. Update the JSON first.",
        "",
    ]
    for project in payload.get("projects") or []:
        lines.extend(
            [
                f"## {project.get('title')}",
                "",
                f"- Status: **{project.get('status')}**",
                f"- Progress: **{project.get('progress')}%** ({project.get('completed_slices')}/{project.get('total_slices')} slices)",
                f"- Owner area: {project.get('area') or '—'}",
                f"- Updated: {project.get('updated_at') or '—'}",
                f"- Summary: {project.get('summary') or '—'}",
                f"- Next step: {project.get('next_step') or '—'}",
                "",
            ]
        )
        if project.get("slices"):
            lines.extend(["| Slice | Status | Deliverable | Verification |", "|---|---|---|---|"])
            for item in project["slices"]:
                lines.append(
                    f"| {item.get('label')} | {item.get('status')} | {item.get('deliverable') or '—'} | {item.get('verification') or '—'} |"
                )
            lines.append("")
    return "\n".join(lines)


def get_project_tracker(path: Path | None = None) -> dict[str, Any]:
    source = path or TRACKER_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    projects = [_progress(project) for project in payload.get("projects") or []]
    completed = sum(project["completed_slices"] for project in projects)
    total = sum(project["total_slices"] for project in projects)
    response = dict(payload)
    response["projects"] = projects
    response["summary"] = {
        "projects": len(projects),
        "active_projects": sum(1 for project in projects if project.get("status") == "in_progress"),
        "completed_slices": completed,
        "total_slices": total,
        "progress": round(completed * 100 / total) if total else 0,
    }
    response["source_path"] = str(source)
    response["handoff_markdown"] = render_project_tracker_markdown(response)
    return response


def write_project_tracker_markdown(path: Path | None = None) -> Path:
    payload = get_project_tracker(path)
    output = PROJECT_ROOT / "docs" / "PROJECT_TRACKER.md"
    temp = output.with_suffix(".tmp")
    temp.write_text(payload["handoff_markdown"], encoding="utf-8")
    temp.replace(output)
    return output


def tracker_updated_at() -> str:
    return datetime.fromtimestamp(TRACKER_PATH.stat().st_mtime).isoformat(timespec="seconds")
