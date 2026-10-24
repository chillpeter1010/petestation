from __future__ import annotations

from collections import defaultdict
from typing import Any

import duckdb
import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table
from app.services.game_line_service import load_pitcher_game_lines
from app.services.pitch_location_score_service import load_pitch_location_scores
from app.services.pitch_stuff_cache_service import load_pitch_stuff_scores
from app.services.stamina_lab_service import load_pitch_stamina_state


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


def _safe_int(value: object) -> int:
    return 0 if value is None or pd.isna(value) else int(value)


def _clean_optional(value: object) -> Any:
    if value is None or pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def _usable_player_name(value: object) -> str | None:
    text = str(value or "").strip()
    lowered = text.lower()
    if not text or lowered in {"unknown", "unknown batter", "unknown pitcher", "none", "nan"}:
        return None
    if lowered.startswith(("player ", "batter ", "pitcher ")):
        return None
    return text


def list_games(
    year: int = 2026,
    date: str | None = None,
    team: str | None = None,
    limit: int = 100,
    data_dir=settings.data_dir,
) -> dict[str, Any]:
    db_path = get_season_duckdb_path(year, data_dir)
    if not db_path.exists():
        return {"year": int(year), "games": [], "latest_game_date": None, "warnings": [f"DuckDB not found: {db_path}"]}

    with duckdb.connect(str(db_path), read_only=True) as conn:
        tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
        if "games" not in tables:
            return {"year": int(year), "games": [], "latest_game_date": None, "warnings": ["games table not found"]}

        where = ["game_type = 'R'"]
        params: list[object] = []
        team_code = str(team or "").strip().upper()
        if team_code:
            where.append("(home_team = ? OR away_team = ?)")
            params.extend([team_code, team_code])
        latest = conn.execute(
            f"SELECT MAX(CAST(game_date AS DATE)) FROM games WHERE {' AND '.join(where)}",
            params,
        ).fetchone()[0]
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
        "team": team_code or None,
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

        player_names: dict[int, str] = {}
        if "game_player_lookup" in tables:
            for player_id, player_name in conn.execute(
                """
                SELECT player_id, any_value(player_name)
                FROM game_player_lookup
                WHERE game_pk = ? AND player_id IS NOT NULL
                GROUP BY player_id
                """,
                [int(game_pk)],
            ).fetchall():
                resolved_name = _usable_player_name(player_name)
                if player_id is not None and resolved_name:
                    player_names[int(player_id)] = resolved_name

        # The per-game lookup is intentionally sparse.  Use the same canonical
        # season player master as the public batter/pitcher leaderboards so a
        # missing game lookup never degrades a known player back to an ID.
        if "player_master" in tables:
            player_columns = {row[1] for row in conn.execute("PRAGMA table_info('player_master')").fetchall()}
            if {"player_id", "player_name"}.issubset(player_columns):
                for player_id, player_name in conn.execute(
                    "SELECT player_id, player_name FROM player_master WHERE player_id IS NOT NULL"
                ).fetchall():
                    resolved_name = _usable_player_name(player_name)
                    if resolved_name:
                        player_names[int(player_id)] = resolved_name

        inning_rows = conn.execute(
            f"""
            SELECT
                inning,
                inning_topbot,
                CASE
                    WHEN inning_topbot = 'Top' THEN greatest(0, max(post_away_score) - min(away_score))
                    ELSE greatest(0, max(post_home_score) - min(home_score))
                END AS runs
            FROM {source_table}
            WHERE game_pk = ?
            GROUP BY inning, inning_topbot
            ORDER BY inning, inning_topbot DESC
            """,
            [int(game_pk)],
        ).fetchdf()

        terminal_rows = conn.execute(
            f"""
            WITH ranked AS (
                SELECT *, row_number() OVER (
                    PARTITION BY game_pk, at_bat_number
                    ORDER BY pitch_number DESC
                ) AS terminal_rank
                FROM {source_table}
                WHERE game_pk = ?
            )
            SELECT * EXCLUDE (terminal_rank)
            FROM ranked
            WHERE terminal_rank = 1
              AND events IS NOT NULL
              AND lower(CAST(events AS VARCHAR)) <> 'truncated_pa'
            ORDER BY at_bat_number
            """,
            [int(game_pk)],
        ).fetchdf()

        all_game_pitches = conn.execute(
            f"""
            SELECT *
            FROM {source_table}
            WHERE game_pk = ?
            ORDER BY at_bat_number, pitch_number
            """,
            [int(game_pk)],
        ).fetchdf()

    if not all_game_pitches.empty:
        all_game_pitches = load_pitch_stamina_state(all_game_pitches, year=year, data_dir=data_dir)
        if "pitch_stuff_plus" not in all_game_pitches.columns or all_game_pitches["pitch_stuff_plus"].isna().all():
            all_game_pitches["pitch_stuff_plus"] = load_pitch_stuff_scores(all_game_pitches, data_dir)
        if "location_plus_pitch" not in all_game_pitches.columns or all_game_pitches["location_plus_pitch"].isna().all():
            all_game_pitches["location_plus_pitch"] = load_pitch_location_scores(all_game_pitches, data_dir)

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

    score_by_team = {
        away_team: _safe_int(pd.to_numeric(terminal_rows.get("post_away_score"), errors="coerce").max()) if not terminal_rows.empty else 0,
        home_team: _safe_int(pd.to_numeric(terminal_rows.get("post_home_score"), errors="coerce").max()) if not terminal_rows.empty else 0,
    }
    hits_by_team = {away_team: 0, home_team: 0}
    errors_by_team = {away_team: 0, home_team: 0}
    hit_events = {"single", "double", "triple", "home_run"}
    batting_rows: dict[str, dict[int, dict[str, Any]]] = {away_team: {}, home_team: {}}
    plays: list[dict[str, Any]] = []
    pitches_by_pa: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for row in all_game_pitches.to_dict(orient="records"):
        at_bat_number = _safe_int(row.get("at_bat_number"))
        play_id = str(row.get("play_id") or "").strip()
        video_url = str(row.get("video_url") or "").strip()
        if not video_url and play_id and play_id.lower() not in {"none", "nan", "null"}:
            video_url = f"https://baseballsavant.mlb.com/sporty-videos?playId={play_id}"
        pitches_by_pa[at_bat_number].append({
            "game_date": str(row.get("game_date") or "")[:10] or None,
            "game_pk": _safe_int(row.get("game_pk")),
            "at_bat_number": at_bat_number,
            "pitch_number": _safe_int(row.get("pitch_number")),
            "pitch_name": _pitch_label(row.get("pitch_name")),
            "pitch_type": _clean_optional(row.get("pitch_type")),
            "description": str(row.get("description") or ""),
            "events": _clean_optional(row.get("events")),
            "release_speed": round(float(row["release_speed"]), 1) if pd.notna(row.get("release_speed")) else None,
            "plate_x": round(float(row["plate_x"]), 3) if pd.notna(row.get("plate_x")) else None,
            "plate_z": round(float(row["plate_z"]), 3) if pd.notna(row.get("plate_z")) else None,
            "balls": _safe_int(row.get("balls")),
            "strikes": _safe_int(row.get("strikes")),
            "play_id": play_id or None,
            "video_url": video_url or None,
            "pitch_stuff_plus": _clean_optional(row.get("pitch_stuff_plus")),
            "location_plus_pitch": _clean_optional(row.get("location_plus_pitch")),
            "stamina_plus_trait": _clean_optional(row.get("stamina_plus_trait")),
            "stamina_expected_retention_delta": _clean_optional(row.get("stamina_expected_retention_delta")),
            "stamina_expected_stuff_plus": _clean_optional(row.get("stamina_expected_stuff_plus")),
            "stamina_reliability": _clean_optional(row.get("stamina_reliability")),
            "stamina_sample_label": _clean_optional(row.get("stamina_sample_label")),
        })

    excluded_ab_events = {
        "walk", "intent_walk", "hit_by_pitch", "sac_bunt", "sac_fly",
        "sac_fly_double_play", "catcher_interf",
    }
    for row in terminal_rows.to_dict(orient="records"):
        half = str(row.get("inning_topbot") or "")
        batting_team = away_team if half == "Top" else home_team
        fielding_team = home_team if half == "Top" else away_team
        batter_id = _safe_int(row.get("batter"))
        pitcher_id = _safe_int(row.get("pitcher"))
        event = str(row.get("events") or "").lower()
        if event in hit_events:
            hits_by_team[batting_team] = hits_by_team.get(batting_team, 0) + 1
        if event == "field_error":
            errors_by_team[fielding_team] = errors_by_team.get(fielding_team, 0) + 1

        batter = batting_rows.setdefault(batting_team, {}).setdefault(batter_id, {
            "player_id": batter_id,
            "name": player_names.get(batter_id, f"Player {batter_id}"),
            "team": batting_team,
            "first_pa": _safe_int(row.get("at_bat_number")),
            "pa": 0,
            "ab": 0,
            "hits": 0,
            "home_runs": 0,
            "walks": 0,
            "strikeouts": 0,
            "hard_hits": 0,
        })
        batter["pa"] += 1
        batter["ab"] += int(event not in excluded_ab_events)
        batter["hits"] += int(event in hit_events)
        batter["home_runs"] += int(event == "home_run")
        batter["walks"] += int(event in {"walk", "intent_walk"})
        batter["strikeouts"] += int(event in {"strikeout", "strikeout_double_play"})
        batter["hard_hits"] += int(pd.notna(row.get("launch_speed")) and float(row["launch_speed"]) >= 95)

        at_bat_number = _safe_int(row.get("at_bat_number"))
        plays.append({
            "at_bat_number": at_bat_number,
            "inning": _safe_int(row.get("inning")),
            "inning_half": half,
            "outs_before": _safe_int(row.get("outs_when_up")),
            "batter_id": batter_id,
            "batter_name": player_names.get(batter_id, f"Player {batter_id}"),
            "pitcher_id": pitcher_id,
            "pitcher_name": player_names.get(pitcher_id, f"Player {pitcher_id}"),
            "event": event.replace("_", " ").title(),
            "description": str(row.get("des") or event.replace("_", " ").title()),
            "away_score": _safe_int(row.get("post_away_score")),
            "home_score": _safe_int(row.get("post_home_score")),
            "pitches": pitches_by_pa.get(at_bat_number, []),
        })

    batting = []
    for code in [away_team, home_team]:
        hitters = sorted(batting_rows.get(code, {}).values(), key=lambda item: (item["first_pa"], item["name"]))
        for hitter in hitters:
            hitter["average"] = round(hitter["hits"] / hitter["ab"], 3) if hitter["ab"] else None
            hitter.pop("first_pa", None)
        batting.append({"team": code, "home_away": "away" if code == away_team else "home", "hitters": hitters})

    inning_map: dict[int, dict[str, int | None]] = {}
    for row in inning_rows.to_dict(orient="records"):
        inning = _safe_int(row.get("inning"))
        item = inning_map.setdefault(inning, {"inning": inning, "away": None, "home": None})
        item["away" if row.get("inning_topbot") == "Top" else "home"] = _safe_int(row.get("runs"))

    game.update({
        "away_score": score_by_team.get(away_team, 0),
        "home_score": score_by_team.get(home_team, 0),
        "status": "Final",
    })
    return {
        "year": int(year),
        "game": game,
        "game_pk": int(game_pk),
        "teams": team_list,
        "scoreboard": {
            "innings": list(inning_map.values()),
            "away": {"team": away_team, "runs": score_by_team.get(away_team, 0), "hits": hits_by_team.get(away_team, 0), "errors": errors_by_team.get(away_team, 0)},
            "home": {"team": home_team, "runs": score_by_team.get(home_team, 0), "hits": hits_by_team.get(home_team, 0), "errors": errors_by_team.get(home_team, 0)},
        },
        "batting": batting,
        "plays": list(reversed(plays)),
        "data_mode": "completed_statcast_snapshot",
        "warnings": [],
    }
