from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TRACKER_PATH = PROJECT_ROOT / "docs" / "PROJECT_TRACKER.json"
HANDOFF_PATH = PROJECT_ROOT / "docs" / "NEXT_CHAT_HANDOFF.md"
HANDOFF_PROGRESS_START = "<!-- PROJECT_PROGRESS:START -->"
HANDOFF_PROGRESS_END = "<!-- PROJECT_PROGRESS:END -->"


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


def _markdown_cell(value: Any) -> str:
    return str(value or "—").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render_handoff_progress_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"Tracker updated: {payload.get('updated_at') or '—'}",
        "",
        "| Project | Status | Slices | Current direction |",
        "| --- | --- | ---: | --- |",
    ]
    for project in payload.get("projects") or []:
        completed = project.get("completed_slices")
        total = project.get("total_slices")
        if completed is None or total is None:
            progress = _progress(project)
            completed = progress["completed_slices"]
            total = progress["total_slices"]
        lines.append(
            "| {title} | {status} | {completed}/{total} | {next_step} |".format(
                title=_markdown_cell(project.get("title")),
                status=_markdown_cell(project.get("status")),
                completed=completed,
                total=total,
                next_step=_markdown_cell(project.get("next_step")),
            )
        )
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
        "active_projects": sum(
            1 for project in projects if project.get("status") in {"active", "in_progress"}
        ),
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


def write_handoff_progress(payload: dict[str, Any], path: Path | None = None) -> Path:
    output = path or HANDOFF_PATH
    content = output.read_text(encoding="utf-8")
    start = content.find(HANDOFF_PROGRESS_START)
    end = content.find(HANDOFF_PROGRESS_END)
    if start < 0 or end < 0 or end < start:
        raise ValueError(f"Handoff progress markers are missing or invalid: {output}")
    replacement = "\n".join(
        [HANDOFF_PROGRESS_START, render_handoff_progress_markdown(payload), HANDOFF_PROGRESS_END]
    )
    updated = content[:start] + replacement + content[end + len(HANDOFF_PROGRESS_END) :]
    temp = output.with_suffix(".tmp")
    temp.write_text(updated, encoding="utf-8")
    temp.replace(output)
    return output


def write_project_tracker_documents(
    tracker_path: Path | None = None, handoff_path: Path | None = None
) -> tuple[Path, Path]:
    payload = get_project_tracker(tracker_path)
    tracker_output = PROJECT_ROOT / "docs" / "PROJECT_TRACKER.md"
    tracker_temp = tracker_output.with_suffix(".tmp")
    tracker_temp.write_text(payload["handoff_markdown"], encoding="utf-8")
    tracker_temp.replace(tracker_output)
    handoff_output = write_handoff_progress(payload, handoff_path)
    return tracker_output, handoff_output


def tracker_updated_at() -> str:
    return datetime.fromtimestamp(TRACKER_PATH.stat().st_mtime).isoformat(timespec="seconds")
