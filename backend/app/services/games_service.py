from __future__ import annotations

from collections import defaultdict
from typing import Any

import duckdb
import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.game_line_service import load_pitcher_game_lines


PITCH_COLORS = {
    "4-Seam": "#c43d34",
    "Four-Seam": "#c43d34",
    "Four-Seam Fastball": "#c43d34",
    "Sinker": "#e8892d",
    "Cutter": "#7b5a3d",
    "Curveball": "#4f86a9",
    "Slider": "#f2ce6b",
    "Sweeper": "#b89755",
    "Changeup": "#65bd7b",
    "Splitter": "#5aa7a9",
}


def _ip_to_float(value: object) -> float:
    if value is None or pd.isna(value):
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0
    whole, _, frac = text.partition(".")
    innings = float(whole or 0)
    outs = int(frac or 0) if frac.isdigit() else 0
    return innings + outs / 3


def _pitch_label(value: object) -> str:
    label = str(value or "Unknown").strip() or "Unknown"
    if label == "Four-Seam Fastball":
        return "4-Seam"
    if label == "Split-Finger":
        return "Splitter"
    return label


def _format_era(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def list_games(year: int = 2026, date: str | None = None, limit: int = 100, data_dir=settings.data_dir) -> dict[str, Any]:
    db_path = get_season_duckdb_path(year, data_dir)
    if not db_path.exists():
        return {"year": int(year), "games": [], "latest_game_date": None, "warnings": [f"DuckDB not found: {db_path}"]}

    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        if "games" not in tables:
            return {"year": int(year), "games": [], "latest_game_date": None, "warnings": ["games table not found"]}

        latest = conn.execute("SELECT MAX(CAST(game_date AS DATE)) FROM games WHERE game_type = 'R'").fetchone()[0]
        where = ["game_type = 'R'"]
        params: list[object] = []
        if date:
            where.append("CAST(game_date AS DATE) = ?")
            params.append(date)
        games = conn.execute(
            f"""
            SELECT game_pk, game_date, away_team, home_team, total_pitches, total_plate_appearances
            FROM games
            WHERE {" AND ".join(where)}
            ORDER BY CAST(game_date AS DATE) DESC, game_pk DESC
            LIMIT ?
            """,
            [*params, max(int(limit), 1)],
        ).fetchdf()

    games["away_score"] = None
    games["home_score"] = None
    lines = load_pitcher_game_lines(year, data_dir)
    if not games.empty and not lines.empty:
        for index, game in games.iterrows():
            game_lines = lines[pd.to_numeric(lines["game_pk"], errors="coerce").eq(int(game["game_pk"]))]
            if game_lines.empty:
                continue
            teams = game_lines["team"].astype(str)
            runs = pd.to_numeric(game_lines["runs"], errors="coerce").fillna(0)
            games.at[index, "away_score"] = int(runs[teams.eq(str(game["home_team"]))].sum())
            games.at[index, "home_score"] = int(runs[teams.eq(str(game["away_team"]))].sum())

    return {
        "year": int(year),
        "latest_game_date": str(latest)[:10] if latest is not None else None,
        "games": games.where(pd.notna(games), None).to_dict(orient="records"),
        "warnings": [],
    }


def get_game_pitching(year: int, game_pk: int, data_dir=settings.data_dir) -> dict[str, Any]:
    db_path = get_season_duckdb_path(year, data_dir)
    if not db_path.exists():
        return {"year": int(year), "game_pk": int(game_pk), "teams": [], "warnings": [f"DuckDB not found: {db_path}"]}

    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        source_table = resolve_pitch_table(tables)
        if not source_table:
            return {"year": int(year), "game_pk": int(game_pk), "teams": [], "warnings": ["game pitch tables not found"]}

        game_df = conn.execute(
            """
            SELECT game_pk, game_date, away_team, home_team, total_pitches, total_plate_appearances
            FROM games
            WHERE game_pk = ?
            LIMIT 1
            """,
            [int(game_pk)],
        ).fetchdf() if "games" in tables else pd.DataFrame()

        pitch_mix = conn.execute(
            f"""
            SELECT
                pitcher AS pitcher_id,
                pitcher_team AS team,
                pitch_name,
                COUNT(*) AS pitches
            FROM {source_table}
            WHERE game_pk = ? AND pitcher IS NOT NULL
            GROUP BY 1, 2, 3
            ORDER BY 1, pitches DESC
            """,
            [int(game_pk)],
        ).fetchdf()

        hard_hit = conn.execute(
            f"""
            SELECT
                pitcher AS pitcher_id,
                SUM(CASE WHEN launch_speed >= 95 THEN 1 ELSE 0 END) AS hard_hits,
                SUM(CASE WHEN events = 'home_run' THEN 1 ELSE 0 END) AS home_runs,
                MAX(release_speed) AS max_velo,
                MIN(release_speed) AS min_velo
            FROM {source_table}
            WHERE game_pk = ? AND pitcher IS NOT NULL
            GROUP BY 1
            """,
            [int(game_pk)],
        ).fetchdf()

        pitcher_order = conn.execute(
            f"""
            SELECT
                pitcher AS pitcher_id,
                pitcher_team AS team,
                MIN(
                    inning * 100000
                    + CASE WHEN inning_topbot = 'Top' THEN 0 ELSE 50000 END
                    + at_bat_number * 100
                    + pitch_number
                ) AS first_pitch_seq
            FROM {source_table}
            WHERE game_pk = ? AND pitcher IS NOT NULL
            GROUP BY 1, 2
            """,
            [int(game_pk)],
        ).fetchdf()

    all_lines = load_pitcher_game_lines(year, data_dir)
    game_keys = pd.to_numeric(all_lines.get("game_pk"), errors="coerce") if not all_lines.empty else pd.Series(dtype=float)
    lines = all_lines[game_keys.eq(int(game_pk))].copy() if not all_lines.empty else pd.DataFrame()
    if not lines.empty:
        lines = lines.sort_values(["home_away", "team", "pitcher_name"], ascending=[False, True, True])
    selected_date = pd.to_datetime(game_df.iloc[0].get("game_date"), errors="coerce") if not game_df.empty else pd.NaT
    season_lines = all_lines.copy()
    if not season_lines.empty and pd.notna(selected_date):
        line_dates = pd.to_datetime(season_lines["game_date"], errors="coerce")
        season_lines = season_lines[line_dates.le(selected_date)]
    era_by_pitcher: dict[int, str] = {}
    if not season_lines.empty:
        season_lines["ip_float"] = season_lines["ip"].map(_ip_to_float)
        season_lines["earned_runs"] = pd.to_numeric(season_lines["earned_runs"], errors="coerce").fillna(0)
        grouped = season_lines.groupby("pitcher_id", dropna=True).agg({"ip_float": "sum", "earned_runs": "sum"}).reset_index()
        for row in grouped.to_dict(orient="records"):
            pitcher_id = int(row["pitcher_id"])
            ip_float = float(row["ip_float"] or 0)
            era_by_pitcher[pitcher_id] = _format_era((float(row["earned_runs"]) * 9 / ip_float) if ip_float > 0 else None)

    mix_by_pitcher: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in pitch_mix.to_dict(orient="records"):
        pitcher_id = int(row["pitcher_id"])
        label = _pitch_label(row.get("pitch_name"))
        mix_by_pitcher[pitcher_id].append({
            "pitch": label,
            "pitches": int(row.get("pitches") or 0),
            "color": PITCH_COLORS.get(label, "#9ca3af"),
        })

    hard_hit_by_pitcher = {
        int(row["pitcher_id"]): {
            "hard_hits": int(row.get("hard_hits") or 0),
            "home_runs": int(row.get("home_runs") or 0),
            "max_velo": round(float(row["max_velo"]), 1) if pd.notna(row.get("max_velo")) else None,
            "min_velo": round(float(row["min_velo"]), 1) if pd.notna(row.get("min_velo")) else None,
        }
        for row in hard_hit.to_dict(orient="records")
        if pd.notna(row.get("pitcher_id"))
    }

    first_pitch_by_pitcher = {
        int(row["pitcher_id"]): float(row.get("first_pitch_seq") or 0)
        for row in pitcher_order.to_dict(orient="records")
        if pd.notna(row.get("pitcher_id"))
    }
    starters_by_team: dict[str, int] = {}
    for row in pitcher_order.sort_values("first_pitch_seq").to_dict(orient="records"):
        team = str(row.get("team") or "")
        pitcher_id = int(row.get("pitcher_id") or 0)
        if team and pitcher_id and team not in starters_by_team:
            starters_by_team[team] = pitcher_id

    game = game_df.iloc[0].to_dict() if not game_df.empty else {"game_pk": int(game_pk)}
    home_team = str(game.get("home_team") or "")
    away_team = str(game.get("away_team") or "")
    teams: dict[str, dict[str, Any]] = {
        away_team: {"team": away_team, "home_away": "away", "pitchers": []},
        home_team: {"team": home_team, "home_away": "home", "pitchers": []},
    }

    for row in lines.to_dict(orient="records"):
        pitcher_id = int(row.get("pitcher_id") or 0)
        team = str(row.get("team") or "")
        pitches = int(row.get("pitches") or 0)
        hard = hard_hit_by_pitcher.get(pitcher_id, {})
        pitcher_payload = {
            "pitcher_id": pitcher_id,
            "name": row.get("pitcher_name"),
            "team": team,
            "role": "SP" if starters_by_team.get(team) == pitcher_id else "RP",
            "ip": row.get("ip"),
            "hits": int(row.get("hits") or 0),
            "runs": int(row.get("runs") or 0),
            "earned_runs": int(row.get("earned_runs") or 0),
            "walks": int(row.get("walks") or 0),
            "strikeouts": int(row.get("strikeouts") or 0),
            "home_runs": int(hard.get("home_runs") or 0),
            "pitches": pitches,
            "batters_faced": int(row.get("batters_faced") or 0),
            "era": era_by_pitcher.get(pitcher_id, "-"),
            "pitch_mix": mix_by_pitcher.get(pitcher_id, []),
            "hard_hits": int(hard.get("hard_hits") or 0),
            "max_velo": hard.get("max_velo"),
            "min_velo": hard.get("min_velo"),
            "first_pitch_seq": first_pitch_by_pitcher.get(pitcher_id, 0),
        }
        teams.setdefault(team, {"team": team, "home_away": row.get("home_away"), "pitchers": []})["pitchers"].append(pitcher_payload)

    for team in teams.values():
        team["pitchers"].sort(key=lambda pitcher: float(pitcher.get("first_pitch_seq") or 0))

    team_list = [teams[key] for key in [away_team, home_team] if key in teams and teams[key]["pitchers"]]
    return {
        "year": int(year),
        "game": game,
        "game_pk": int(game_pk),
        "teams": team_list,
        "warnings": [],
    }
