from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import available_db_years, get_season_duckdb_path
from app.services.pitcher_service import list_pitcher_leaderboard
from app.services.stamina_lab_service import (
    get_stamina_leaderboard,
    stamina_adjusted_season_summary_path,
)
from app.services.stuff_leaderboard_service import get_stuff_leaderboard, snapshot_path


METRICS = [
    {"key": "ip", "label": "IP", "category": "Results & workload", "unit": "innings", "higher_is_better": None, "description": "Innings pitched."},
    {"key": "games", "label": "G", "category": "Results & workload", "unit": "count", "higher_is_better": None, "description": "Games pitched."},
    {"key": "starts", "label": "GS", "category": "Results & workload", "unit": "count", "higher_is_better": None, "description": "Games started."},
    {"key": "relief_games", "label": "GR", "category": "Results & workload", "unit": "count", "higher_is_better": None, "description": "Relief appearances."},
    {"key": "pitches", "label": "Pitches", "category": "Results & workload", "unit": "count", "higher_is_better": None, "description": "Tracked season pitch count."},
    {"key": "avg_pitches", "label": "Avg Pitches", "category": "Results & workload", "unit": "pitches", "higher_is_better": None, "description": "Average pitches per appearance."},
    {"key": "era", "label": "ERA", "category": "Results & workload", "unit": "rate", "higher_is_better": False, "description": "Earned runs allowed per nine innings."},
    {"key": "whip", "label": "WHIP", "category": "Results & workload", "unit": "rate", "higher_is_better": False, "description": "Walks and hits allowed per inning."},
    {"key": "k_pct", "label": "K%", "category": "Results & workload", "unit": "%", "higher_is_better": True, "description": "Strikeouts divided by batters faced."},
    {"key": "bb_pct", "label": "BB%", "category": "Results & workload", "unit": "%", "higher_is_better": False, "description": "Walks divided by batters faced."},
    {"key": "k_minus_bb_pct", "label": "K-BB%", "category": "Results & workload", "unit": "pp", "higher_is_better": True, "description": "Strikeout rate minus walk rate."},
    {"key": "avg_game_score", "label": "Avg Game Score", "category": "Results & workload", "unit": "score", "higher_is_better": True, "description": "Average Bill James-style Game Score in starts."},
    {"key": "k_per_9", "label": "K/9", "category": "Standard advanced", "unit": "rate", "higher_is_better": True, "description": "Strikeouts per nine innings."},
    {"key": "bb_per_9", "label": "BB/9", "category": "Standard advanced", "unit": "rate", "higher_is_better": False, "description": "Walks per nine innings."},
    {"key": "hr_per_9", "label": "HR/9", "category": "Standard advanced", "unit": "rate", "higher_is_better": False, "description": "Home runs allowed per nine innings."},
    {"key": "babip", "label": "BABIP", "category": "Standard advanced", "unit": "rate", "higher_is_better": False, "description": "Batting average on balls in play allowed."},
    {"key": "lob_pct", "label": "LOB%", "category": "Standard advanced", "unit": "%", "higher_is_better": True, "description": "Share of baserunners stranded."},
    {"key": "gb_pct", "label": "GB%", "category": "Standard advanced", "unit": "%", "higher_is_better": True, "description": "Ground-ball rate."},
    {"key": "hr_fb_pct", "label": "HR/FB", "category": "Standard advanced", "unit": "%", "higher_is_better": False, "description": "Home runs per fly ball."},
    {"key": "fastball_velo", "label": "Fastball Velo", "category": "Standard advanced", "unit": "mph", "higher_is_better": True, "description": "Average fastball velocity from the season dashboard."},
    {"key": "xera", "label": "xERA", "category": "Standard advanced", "unit": "rate", "higher_is_better": False, "description": "Expected ERA."},
    {"key": "fip", "label": "FIP", "category": "Standard advanced", "unit": "rate", "higher_is_better": False, "description": "Fielding Independent Pitching."},
    {"key": "xfip", "label": "xFIP", "category": "Standard advanced", "unit": "rate", "higher_is_better": False, "description": "FIP with a normalized home-run rate."},
    {"key": "war", "label": "WAR", "category": "Standard advanced", "unit": "wins", "higher_is_better": True, "description": "Wins Above Replacement from the season dashboard."},
    {"key": "stuff_plus", "label": "Stuff+", "category": "Petehub Plus", "unit": "plus", "higher_is_better": True, "description": "Context-neutral modeled pitch quality; 100 is league average."},
    {"key": "location_plus", "label": "Location+", "category": "Petehub Plus", "unit": "plus", "higher_is_better": True, "description": "Modeled pitch-location execution; 100 is league average."},
    {"key": "pitching_plus", "label": "Pitching+", "category": "Petehub Plus", "unit": "plus", "higher_is_better": True, "description": "Complete-pitch modeled value; 100 is league average."},
    {"key": "stamina_plus", "label": "Stamina+", "category": "Stamina & stability", "unit": "plus", "higher_is_better": True, "description": "Validated adjusted observed-season pitch-quality retention."},
    {"key": "quality_stamina_plus", "label": "Q-Stm+", "category": "Stamina & stability", "unit": "plus", "higher_is_better": True, "description": "Mean eligible single-game Quality Stamina+."},
    {"key": "physical_stability_plus", "label": "Phy-Stb+", "category": "Stamina & stability", "unit": "plus", "higher_is_better": True, "description": "Mean eligible physical tracking stability score."},
    {"key": "command_retention_plus", "label": "Cmd-Ret+", "category": "Stamina & stability", "unit": "plus", "higher_is_better": True, "description": "Mean eligible Location+ retention score."},
    {"key": "fastball_stamina_plus", "label": "Stm+ FB", "category": "Stamina & stability", "unit": "plus", "higher_is_better": True, "description": "Adjusted fastball-family season Stamina+."},
    {"key": "breaking_stamina_plus", "label": "Stm+ BRK", "category": "Stamina & stability", "unit": "plus", "higher_is_better": True, "description": "Adjusted breaking-ball-family season Stamina+."},
    {"key": "offspeed_stamina_plus", "label": "Stm+ OFF", "category": "Stamina & stability", "unit": "plus", "higher_is_better": True, "description": "Adjusted offspeed-family season Stamina+."},
    {"key": "stamina_reliability", "label": "Stamina Reliability", "category": "Stamina & stability", "unit": "rate", "higher_is_better": True, "description": "Support and precision of the official season Stamina+ estimate."},
]


DASHBOARD_MAP = {
    "K/9": "k_per_9", "BB/9": "bb_per_9", "HR/9": "hr_per_9", "BABIP": "babip",
    "LOB%": "lob_pct", "GB%": "gb_pct", "HR/FB": "hr_fb_pct", "vFA (pi)": "fastball_velo",
    "xERA": "xera", "FIP": "fip", "xFIP": "xfip", "WAR": "war",
}


def _number(value: Any, *, percent: bool = False) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"nan", "none", "null", "-"}:
        return None
    has_percent = text.endswith("%")
    try:
        numeric = float(text.rstrip("%"))
    except ValueError:
        return None
    if percent and not has_percent and abs(numeric) <= 1:
        numeric *= 100
    return numeric


def _dashboard_path(year: int, root: Path) -> Path | None:
    candidates = [
        root / "Starter" / f"{year}_starter_dashboard.csv",
        root / "Starter" / "2021_2026_starter_dashboard.csv",
        root / f"MLB{year}" / f"{year}_all_pitcher_standard.csv",
    ]
    return next((path for path in candidates if path.exists()), None)


def _load_dashboard_metrics(year: int, root: Path) -> dict[int, dict[str, float | None]]:
    path = _dashboard_path(year, root)
    if path is None:
        return {}
    frame = pd.read_csv(path, low_memory=False)
    if "Season" in frame.columns:
        frame = frame[pd.to_numeric(frame["Season"], errors="coerce").eq(int(year))].copy()
    if "MLBAMID" not in frame.columns:
        return {}
    frame["MLBAMID"] = pd.to_numeric(frame["MLBAMID"], errors="coerce")
    frame = frame.dropna(subset=["MLBAMID"]).drop_duplicates("MLBAMID", keep="first")
    result: dict[int, dict[str, float | None]] = {}
    for row in frame.to_dict(orient="records"):
        values: dict[str, float | None] = {}
        for source, target in DASHBOARD_MAP.items():
            values[target] = _number(row.get(source), percent=source.endswith("%") or source == "HR/FB")
        result[int(row["MLBAMID"])] = values
    return result


def _build_metric_explorer(year: int, root: Path) -> dict[str, Any]:
    basic_rows = list_pitcher_leaderboard(year=year, role="All", team="All")
    advanced = _load_dashboard_metrics(year, root)
    warnings: list[str] = []
    status = {"basic": "current" if basic_rows else "unavailable", "advanced": "current" if advanced else "unavailable", "plus": "unavailable", "stamina": "unavailable"}

    plus: dict[int, dict[str, Any]] = {}
    data_as_of: str | None = None
    try:
        plus_payload = get_stuff_leaderboard(year=year, data_dir=root)
        plus = {int(row["player_id"]): row for row in plus_payload.get("rows", [])}
        data_as_of = plus_payload.get("data_as_of")
        status["plus"] = str(plus_payload.get("cache_status") or "current")
        warnings.extend(plus_payload.get("warnings", []))
    except (FileNotFoundError, ValueError) as exc:
        warnings.append(str(exc))

    stamina: dict[int, dict[str, Any]] = {}
    try:
        stamina_payload = get_stamina_leaderboard(year=year, data_dir=root)
        stamina = {int(row["pitcher_id"]): row for row in stamina_payload.get("rows", [])}
        data_as_of = data_as_of or stamina_payload.get("data_as_of")
        status["stamina"] = "current"
    except (FileNotFoundError, ValueError) as exc:
        warnings.append(str(exc))

    rows = []
    for basic in basic_rows:
        player_id = int(basic.player_id)
        metrics: dict[str, float | None] = {definition["key"]: None for definition in METRICS}
        metrics.update({
            "ip": basic.ip,
            "games": float(basic.games),
            "starts": float(basic.starts),
            "relief_games": float(basic.relief_games),
            "pitches": _number(basic.pitches),
            "avg_pitches": basic.avg_pitches,
            "era": basic.era,
            "whip": basic.whip,
            "k_pct": _number(basic.strikeout_rate * 100 if basic.strikeout_rate is not None else None),
            "bb_pct": _number(basic.walk_rate * 100 if basic.walk_rate is not None else None),
            "k_minus_bb_pct": _number((basic.strikeout_rate - basic.walk_rate) * 100 if basic.strikeout_rate is not None and basic.walk_rate is not None else None),
            "avg_game_score": basic.avg_game_score,
        })
        metrics.update(advanced.get(player_id, {}))
        plus_row = plus.get(player_id, {})
        metrics.update({key: _number(plus_row.get(key)) for key in ["stuff_plus", "location_plus", "pitching_plus"]})
        stamina_row = stamina.get(player_id, {})
        metrics.update({
            "stamina_plus": _number(stamina_row.get("stamina_plus")),
            "quality_stamina_plus": _number(stamina_row.get("quality_game_stamina_plus")),
            "physical_stability_plus": _number(stamina_row.get("physical_stability_plus")),
            "command_retention_plus": _number(stamina_row.get("command_retention_plus")),
            "fastball_stamina_plus": _number(stamina_row.get("fastball_stamina_plus")),
            "breaking_stamina_plus": _number(stamina_row.get("breaking_stamina_plus")),
            "offspeed_stamina_plus": _number(stamina_row.get("offspeed_stamina_plus")),
            "stamina_reliability": _number(stamina_row.get("reliability")),
        })
        rows.append({"player_id": player_id, "name": basic.name, "team": basic.team, "role": basic.role, "metrics": metrics})

    return {
        "year": int(year),
        "available_years": sorted(available_db_years(root), reverse=True),
        "data_as_of": data_as_of,
        "metrics": METRICS,
        "rows": rows,
        "teams": sorted({row["team"] for row in rows if row["team"]}),
        "source_status": status,
        "warnings": list(dict.fromkeys(warnings)),
    }


def _stamp(path: Path | None) -> int:
    try:
        return path.stat().st_mtime_ns if path else 0
    except OSError:
        return 0


@lru_cache(maxsize=12)
def _cached_metric_explorer(year: int, data_root: str, source_stamp: tuple[int, ...]) -> dict[str, Any]:
    del source_stamp
    return _build_metric_explorer(year, Path(data_root))


def get_pitcher_metric_explorer(year: int = 2026, data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    paths = [
        get_season_duckdb_path(year, root),
        root / f"MLB{year}" / f"mlb_{year}_pitcher_game_lines.csv.gz",
        snapshot_path(year, root),
        stamina_adjusted_season_summary_path(year, root),
        _dashboard_path(year, root),
    ]
    return _cached_metric_explorer(int(year), str(root), tuple(_stamp(path) for path in paths))
