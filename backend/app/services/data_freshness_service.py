from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import duckdb

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.pitch_refresh_service import audit_pitch_coverage, classify_source_pending


TAIPEI = ZoneInfo("Asia/Taipei")
STATUS_PRIORITY = {
    "failed": 100,
    "stale": 90,
    "partial": 80,
    "source_pending": 70,
    "expected_lag": 60,
    "manual": 50,
    "unverified": 40,
    "unavailable": 30,
    "live": 10,
    "current": 0,
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _date_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _timestamp(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=TAIPEI).isoformat(timespec="seconds")


def _file_version(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _relative_status(data_as_of: str | None, source_as_of: str | None, expected_lag: int = 0) -> str:
    if not data_as_of:
        return "unavailable"
    if not source_as_of:
        return "unverified"
    lag = (date.fromisoformat(source_as_of) - date.fromisoformat(data_as_of)).days
    if lag <= expected_lag:
        return "current" if lag == 0 else "expected_lag"
    return "stale"


def _dataset(
    key: str,
    label: str,
    *,
    status: str,
    data_as_of: str | None,
    generated_at: str | None,
    automation: str,
    affected_pages: list[str],
    depends_on: list[str] | None = None,
    rows: int | None = None,
    source_as_of: str | None = None,
    warnings: list[str] | None = None,
    publication_status: str | None = None,
    artifact_version: str | None = None,
) -> dict[str, Any]:
    payload = {
        "key": key,
        "label": label,
        "status": status,
        "data_as_of": data_as_of,
        "source_as_of": source_as_of,
        "generated_at": generated_at,
        "rows": rows,
        "automation": automation,
        "affected_pages": affected_pages,
        "depends_on": depends_on or [],
        "warnings": warnings or [],
    }
    if publication_status:
        payload["publication_status"] = publication_status
    if artifact_version:
        payload["artifact_version"] = artifact_version
    return payload


def _pitch_source(year: int, data_dir: Path) -> dict[str, Any]:
    db_path = get_season_duckdb_path(year, data_dir)
    result: dict[str, Any] = {"path": str(db_path), "rows": None, "games": None, "latest": None}
    if not db_path.exists():
        return result
    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = resolve_pitch_table(tables)
        if source_table:
            row = conn.execute(
                f"""
                SELECT COUNT(*), COUNT(DISTINCT game_pk), MAX(CAST(game_date AS DATE))
                FROM {source_table}
                WHERE game_type = 'R'
                """
            ).fetchone()
            result.update({"rows": int(row[0] or 0), "games": int(row[1] or 0), "latest": _date_text(row[2])})
    result["generated_at"] = _timestamp(db_path)
    return result


def _location_status(year: int, data_dir: Path) -> dict[str, Any]:
    path = data_dir / "derived" / "location_plus_scores.duckdb"
    result: dict[str, Any] = {"path": str(path), "rows": None, "latest": None, "generated_at": _timestamp(path)}
    if not path.exists():
        return result
    table = f"location_pitch_scores_{year}"
    with duckdb.connect(str(path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        if table in tables:
            row = conn.execute(f"SELECT COUNT(*), MAX(CAST(game_date AS DATE)) FROM {table}").fetchone()
            result.update({"rows": int(row[0] or 0), "latest": _date_text(row[1])})
    return result


def _pitch_stuff_status(year: int, data_dir: Path) -> dict[str, Any]:
    path = data_dir / "derived" / "pitch_stuff_scores.sqlite3"
    state = _read_json(data_dir / "admin_job_logs" / f"pitch_stuff_backfill_{year}.json")
    result: dict[str, Any] = {
        "path": str(path),
        "rows": None,
        "pitchers": None,
        "generated_at": state.get("updated_at") or _timestamp(path),
        "status": state.get("status"),
        "deferred_pitchers": state.get("deferred_pitchers"),
    }
    if not path.exists():
        return result
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        row = connection.execute(
            "SELECT COUNT(*), COUNT(DISTINCT pitcher), MAX(calculated_at) FROM pitch_stuff_scores WHERE year = ?",
            (year,),
        ).fetchone()
    result.update({"rows": int(row[0] or 0), "pitchers": int(row[1] or 0), "generated_at": row[2] or result["generated_at"]})
    return result


def _legacy_derived_status(year: int, data_dir: Path) -> dict[str, Any]:
    path = data_dir / "derived" / "derived_exports.duckdb"
    result: dict[str, Any] = {"path": str(path), "rows": None, "latest": None, "generated_at": _timestamp(path)}
    if not path.exists():
        return result
    table = f"outing_reports_{year}"
    with duckdb.connect(str(path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        if table in tables:
            row = conn.execute(f"SELECT COUNT(*), MAX(CAST(game_date AS DATE)) FROM {table}").fetchone()
            result.update({"rows": int(row[0] or 0), "latest": _date_text(row[1])})
    return result


def _build_pages(datasets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    routes = sorted({route for item in datasets for route in item["affected_pages"]})
    pages: list[dict[str, Any]] = []
    for route in routes:
        dependencies = [item for item in datasets if route in item["affected_pages"]]
        dated = [item["data_as_of"] for item in dependencies if item.get("data_as_of")]
        worst = max(dependencies, key=lambda item: STATUS_PRIORITY.get(item["status"], 0))
        pages.append(
            {
                "route": route,
                "status": worst["status"],
                "data_as_of": min(dated) if dated else None,
                "datasets": [item["key"] for item in dependencies],
            }
        )
    return pages


def build_data_freshness_report(
    year: int = 2026,
    data_dir: Path | None = None,
    *,
    include_official: bool = True,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    generated_at = datetime.now(TAIPEI).isoformat(timespec="seconds")
    pitch = _pitch_source(year, root)
    official: dict[str, Any] = {}
    official_warning: list[str] = []
    if include_official:
        try:
            official = audit_pitch_coverage(year, root)
            official["source_pending"] = classify_source_pending(official)
        except Exception as exc:
            official_warning.append(f"Official coverage check failed: {exc}")
    official_latest = _date_text(official.get("latest_official_date"))
    pitch_status = _relative_status(pitch["latest"], official_latest)
    pending = official.get("source_pending") or {}
    if official.get("missing_games") and pending.get("source_pending"):
        pitch_status = "source_pending"

    datasets: list[dict[str, Any]] = []
    datasets.append(
        _dataset(
            "statcast_pitch_data",
            "Statcast pitch data",
            status=pitch_status,
            data_as_of=pitch["latest"],
            source_as_of=official_latest,
            generated_at=pitch.get("generated_at"),
            rows=pitch.get("rows"),
            automation="daily",
            affected_pages=["/leaderboards", "/pitcher-personal", "/batters", "/teams/:teamId", "/games/today", "/comparison/period", "/lab/leverage"],
            warnings=official_warning + ([f"{official.get('missing_games')} completed games are missing locally."] if official.get("missing_games") else []),
        )
    )

    video_meta = _read_json(root / f"MLB{year}" / f"mlb_{year}_play_lookup_meta.json")
    datasets.append(
        _dataset(
            "video_lookup",
            "Pitch video lookup",
            status=_relative_status(pitch["latest"], pitch["latest"]),
            data_as_of=pitch["latest"],
            source_as_of=pitch["latest"],
            generated_at=video_meta.get("built_at"),
            rows=video_meta.get("pitch_play_lookup_rows"),
            automation="daily",
            affected_pages=["/pitcher-personal", "/batters/:player", "/games/today", "/"],
            depends_on=["statcast_pitch_data"],
            warnings=[f"Failed games: {len(video_meta.get('failed_games') or [])}"],
        )
    )

    line_meta = _read_json(root / f"MLB{year}" / f"mlb_{year}_pitcher_game_lines_meta.json")
    datasets.append(
        _dataset(
            "pitcher_game_lines",
            "Official pitcher game lines",
            status=_relative_status(pitch["latest"], pitch["latest"]),
            data_as_of=pitch["latest"],
            source_as_of=pitch["latest"],
            generated_at=line_meta.get("built_at"),
            rows=line_meta.get("pitcher_game_line_rows"),
            automation="daily",
            affected_pages=["/rotation/starter", "/rotation/bullpen", "/pitcher-personal", "/teams/:teamId", "/games/today"],
            depends_on=["statcast_pitch_data"],
            warnings=[f"Failed games: {len(line_meta.get('failed_games') or [])}"],
        )
    )

    leaderboard_path = root / "derived" / f"stuff_leaderboard_{year}.json"
    leaderboard = _read_json(leaderboard_path)
    for key, label, value_key, status_key in [
        ("stuff_plus", "Stuff+", "data_as_of", "stuff_plus"),
        ("location_plus", "Location+", "data_as_of", "location_plus"),
        ("pitching_plus", "Pitching+", "pitching_data_as_of", "pitching_plus"),
    ]:
        value = _date_text(leaderboard.get(value_key))
        source_status = (leaderboard.get("source_status") or {}).get(status_key)
        status = _relative_status(value, pitch["latest"], expected_lag=1 if key == "pitching_plus" else 0)
        if source_status == "stale" and status == "current":
            status = "expected_lag"
        datasets.append(
            _dataset(
                key,
                label,
                status=status,
                data_as_of=value,
                source_as_of=pitch["latest"],
                generated_at=leaderboard.get("pitching_generated_at") if key == "pitching_plus" else leaderboard.get("generated_at"),
                rows=leaderboard.get("total_pitchers"),
                automation="daily inference",
                affected_pages=["/leaderboards", "/pitcher-personal", f"/lab/{key.removesuffix('_plus')}", "/comparison/period"],
                depends_on=["statcast_pitch_data"],
                warnings=list(leaderboard.get("warnings") or []) if key == "pitching_plus" else [],
            )
        )

    pitch_stuff = _pitch_stuff_status(year, root)
    datasets.append(
        _dataset(
            "pitch_stuff_cache",
            "Per-pitch Stuff+ cache",
            status="partial" if pitch_stuff.get("status") == "partial" else ("current" if pitch_stuff.get("rows") else "unavailable"),
            data_as_of=pitch["latest"],
            source_as_of=pitch["latest"],
            generated_at=pitch_stuff.get("generated_at"),
            rows=pitch_stuff.get("rows"),
            automation="daily · full incremental completion with coverage verification",
            affected_pages=["/pitcher-personal", "/batters/:player", "/batters/lab/stuff-attack"],
            depends_on=["statcast_pitch_data", "stuff_plus"],
            warnings=[f"Deferred pitchers: {pitch_stuff.get('deferred_pitchers')}"] if pitch_stuff.get("deferred_pitchers") else [],
        )
    )

    stamina_path = root / "derived" / f"stamina_lab_{year}.json"
    stamina = _read_json(stamina_path)
    stamina_as_of = _date_text(stamina.get("data_as_of"))
    datasets.append(
        _dataset(
            "stamina_lab",
            "Stamina Lab research dataset",
            status=_relative_status(stamina_as_of, pitch["latest"]) if stamina else "unavailable",
            data_as_of=stamina_as_of,
            source_as_of=pitch["latest"],
            generated_at=stamina.get("generated_at") or _timestamp(stamina_path),
            rows=stamina.get("dataset_rows"),
            automation="daily after verified per-pitch Stuff+ completion",
            affected_pages=["/lab/stamina"],
            depends_on=["statcast_pitch_data", "pitch_stuff_cache", "location_plus"],
            warnings=list(stamina.get("warnings") or []),
        )
    )

    shadow_path = root / "derived" / "performance_state_slice11.json"
    shadow = _read_json(shadow_path)
    shadow_year = int(shadow.get("evaluation_year") or 0)
    shadow_dates = [
        _date_text(target.get("data_as_of"))
        for role_payload in (shadow.get("monitoring") or {}).values()
        if isinstance(role_payload, dict)
        for target in role_payload.values()
        if isinstance(target, dict)
    ]
    shadow_as_of = max((value for value in shadow_dates if value), default=None)
    shadow_status = "unavailable"
    if shadow and shadow_year == int(year):
        shadow_status = _relative_status(shadow_as_of, pitch["latest"])
    shadow_warnings = [
        "The frozen forecast ledger is research-only and is not part of the daily refresh pipeline.",
        "Historical backfill rows are not prospective validation; integration remains gated on untouched 2027 data.",
    ] if shadow else []
    datasets.append(
        _dataset(
            "performance_state_shadow",
            "Performance State frozen shadow ledger",
            status=shadow_status,
            data_as_of=shadow_as_of if shadow_year == int(year) else None,
            source_as_of=pitch["latest"],
            generated_at=shadow.get("generated_at") or _timestamp(shadow_path),
            rows=shadow.get("ledger_rows"),
            automation="manual frozen-model rebuild · immutable append ledger",
            affected_pages=["/lab/performance-state"],
            depends_on=["statcast_pitch_data", "stamina_lab"],
            warnings=shadow_warnings,
        )
    )

    location = _location_status(year, root)
    location_item = next(item for item in datasets if item["key"] == "location_plus")
    location_item.update({"data_as_of": location["latest"] or location_item["data_as_of"], "rows": location["rows"], "generated_at": location["generated_at"]})

    starter_path = root / "Starter" / f"{year}_starter_dashboard.csv"
    datasets.append(
        _dataset(
            "starter_reference",
            "Starter dashboard reference",
            status=_relative_status(pitch["latest"], pitch["latest"]),
            data_as_of=pitch["latest"],
            source_as_of=pitch["latest"],
            generated_at=_timestamp(starter_path),
            automation="daily",
            affected_pages=["/rotation/starter", "/teams/:teamId", "/comparison/pitcher"],
            depends_on=["statcast_pitch_data", "pitcher_game_lines"],
        )
    )

    lineup_path = root / "derived" / f"batter_lineup_scenarios_{year}.json"
    lineup = _read_json(lineup_path)
    lineup_dates = [_date_text(item.get("data_updated_at")) for item in (lineup.get("entries") or {}).values() if isinstance(item, dict)]
    lineup_as_of = max((value for value in lineup_dates if value), default=None)
    datasets.append(
        _dataset(
            "lineup_scenarios",
            "Team lineup scenarios",
            status=_relative_status(lineup_as_of, pitch["latest"]),
            data_as_of=lineup_as_of,
            source_as_of=pitch["latest"],
            generated_at=lineup.get("generated_at"),
            rows=len(lineup.get("entries") or {}),
            automation="daily",
            affected_pages=["/teams/:teamId", "/batters/comparison/lineup"],
            depends_on=["statcast_pitch_data"],
        )
    )

    timing_path = root / "MissDistance" / f"{year}_batter_timing_summary_all.meta.json"
    timing = _read_json(timing_path)
    datasets.append(
        _dataset(
            "batter_timing",
            "Batter timing summary",
            status="unverified" if timing else "unavailable",
            data_as_of=None,
            source_as_of=None,
            generated_at=timing.get("generated_at"),
            rows=timing.get("rows"),
            automation="daily",
            affected_pages=["/batters/lab/swing-timing", "/batters/:player", "/teams/:teamId"],
            warnings=["The source snapshot does not record an exact data_as_of date."] if timing else [],
        )
    )

    transaction_path = root / f"MLB{year}" / f"mlb_{year}_transactions.json"
    transactions = _read_json(transaction_path)
    transaction_as_of = _date_text(transactions.get("petehubPeriodEnd"))
    transaction_status = "current" if transaction_as_of and (date.today() - date.fromisoformat(transaction_as_of)).days <= 2 else "stale"
    datasets.append(
        _dataset(
            "transactions",
            "Transactions and injury events",
            status=transaction_status if transactions else "unavailable",
            data_as_of=transaction_as_of,
            source_as_of=date.today().isoformat(),
            generated_at=transactions.get("petehubFetchedAt"),
            rows=len(transactions.get("transactions") or []),
            automation="daily · rolling 60 days",
            affected_pages=["/teams/:teamId"],
        )
    )

    payroll_paths = list((root / f"MLB{year}" / "payroll").glob("*.json"))
    payroll_payloads = [_read_json(path) for path in payroll_paths]
    payroll_times = [payload.get("source_updated_at") for payload in payroll_payloads if payload.get("source_updated_at")]
    payroll_dates = [_date_text(value) for value in payroll_times]
    payroll_as_of = max((value for value in payroll_dates if value), default=None)
    payroll_age = (date.today() - date.fromisoformat(payroll_as_of)).days if payroll_as_of else 999
    datasets.append(
        _dataset(
            "payroll",
            "Team payroll snapshots",
            status="current" if len(payroll_paths) == 30 and payroll_age <= 7 else ("partial" if payroll_paths else "unavailable"),
            data_as_of=payroll_as_of,
            source_as_of=date.today().isoformat(),
            generated_at=max(payroll_times, default=None),
            rows=len(payroll_paths),
            automation="daily refresh · weekly freshness",
            affected_pages=["/teams/:teamId"],
            warnings=[] if len(payroll_paths) == 30 else [f"Snapshots available: {len(payroll_paths)}/30"],
        )
    )

    reliever_path = root / "Reliever" / f"{year}_reliever_wpa.csv"
    reliever_rows = None
    if reliever_path.exists():
        with reliever_path.open("r", encoding="utf-8-sig", errors="replace") as source:
            reliever_rows = max(sum(1 for _ in source) - 1, 0)
    datasets.append(
        _dataset(
            "reliever_reference",
            "Collected reliever WPA reference",
            status="manual" if reliever_path.exists() else "unavailable",
            data_as_of=None,
            source_as_of=None,
            generated_at=_timestamp(reliever_path),
            rows=reliever_rows,
            automation="manual import",
            affected_pages=["/lab/leverage"],
            warnings=["The collected reference does not record an exact data_as_of date; its SHA-256 version is shown instead."],
            publication_status="manual_reference_only",
            artifact_version=_file_version(reliever_path),
        )
    )

    legacy = _legacy_derived_status(year, root)
    datasets.append(
        _dataset(
            "legacy_derived_exports",
            "Legacy derived exports",
            status="stale" if legacy["latest"] else "unavailable",
            data_as_of=legacy["latest"],
            source_as_of=pitch["latest"],
            generated_at=legacy["generated_at"],
            rows=legacy["rows"],
            automation="retired · no automatic refresh",
            affected_pages=["/api/derived", "/lab/stuff?model_mode=snapshot"],
            depends_on=["statcast_pitch_data"],
            warnings=["Read-only compatibility artifact. Do not use it for current leaderboards or canonical Stuff+ pages."],
            publication_status="retired_read_only",
            artifact_version=_file_version(root / "derived" / "derived_exports.duckdb"),
        )
    )

    datasets.append(
        _dataset(
            "mlb_live_context",
            "MLB standings, schedule, probable starters and active pitchers",
            status="live",
            data_as_of=date.today().isoformat(),
            source_as_of=date.today().isoformat(),
            generated_at=None,
            automation="request-time · 5 minute memory cache",
            affected_pages=["/teams/:teamId"],
        )
    )

    pages = _build_pages(datasets)
    overall = max(datasets, key=lambda item: STATUS_PRIORITY.get(item["status"], 0))["status"]
    return {
        "schema_version": 1,
        "year": int(year),
        "generated_at": generated_at,
        "overall_status": overall,
        "official_coverage": official,
        "datasets": datasets,
        "pages": pages,
        "status_legend": {
            "current": "Caught up to its source",
            "expected_lag": "Within an intentional calculation lag",
            "source_pending": "Recent completed games are not yet available upstream",
            "partial": "Only part of the target scope is complete",
            "stale": "Behind its source beyond the allowed lag",
            "manual": "Updated only when a reference file is imported",
            "unverified": "Snapshot exists but does not expose a trustworthy cutoff date",
            "unavailable": "No usable snapshot exists",
            "live": "Fetched when the page is requested",
        },
    }


def render_data_freshness_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Petehub Data Freshness",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Season: {report.get('year')}",
        f"Overall status: **{str(report.get('overall_status') or 'unknown').upper()}**",
        "",
        "## Datasets",
        "",
        "| Dataset | Status | Data as of | Source as of | Automation | Affected pages |",
        "|---|---|---|---|---|---|",
    ]
    for item in report.get("datasets") or []:
        pages = ", ".join(item.get("affected_pages") or [])
        lines.append(
            f"| {item.get('label')} | {item.get('status')} | {item.get('data_as_of') or '—'} | "
            f"{item.get('source_as_of') or '—'} | {item.get('automation') or '—'} | {pages or '—'} |"
        )
    lines.extend(["", "## Page impact", "", "| Page | Status | Oldest dated dependency | Datasets |", "|---|---|---|---|"])
    for page in report.get("pages") or []:
        lines.append(
            f"| {page.get('route')} | {page.get('status')} | {page.get('data_as_of') or '—'} | "
            f"{', '.join(page.get('datasets') or [])} |"
        )
    warnings = [f"- **{item.get('label')}**: {warning}" for item in report.get("datasets") or [] for warning in item.get("warnings") or []]
    lines.extend(["", "## Warnings", "", *(warnings or ["- None"]), ""])
    return "\n".join(lines)


def write_data_freshness_report(report: dict[str, Any], data_dir: Path | None = None, *, keep_history: bool = True) -> dict[str, str]:
    root = Path(data_dir or settings.data_dir) / "admin_job_logs"
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "data_freshness_latest.json"
    markdown_path = root / "DATA_FRESHNESS.md"
    json_temp = json_path.with_suffix(".tmp")
    markdown_temp = markdown_path.with_suffix(".tmp")
    json_temp.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    markdown_temp.write_text(render_data_freshness_markdown(report), encoding="utf-8")
    json_temp.replace(json_path)
    markdown_temp.replace(markdown_path)
    paths = {"json": str(json_path), "markdown": str(markdown_path)}
    if keep_history:
        history_dir = root / "data_freshness_history"
        history_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(TAIPEI).strftime("%Y-%m-%d_%H-%M-%S")
        history_path = history_dir / f"{stamp}.json"
        history_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        paths["history"] = str(history_path)
    return paths


def refresh_data_freshness_report(year: int = 2026, data_dir: Path | None = None, *, keep_history: bool = True) -> dict[str, Any]:
    report = build_data_freshness_report(year, data_dir, include_official=True)
    report["outputs"] = write_data_freshness_report(report, data_dir, keep_history=keep_history)
    return report


def get_data_freshness_report(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    path = root / "admin_job_logs" / "data_freshness_latest.json"
    payload = _read_json(path)
    if payload and int(payload.get("year") or 0) == int(year):
        return payload
    return build_data_freshness_report(year, root, include_official=False)
