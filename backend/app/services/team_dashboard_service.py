from __future__ import annotations

from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from typing import Any
from urllib.parse import urlencode

import duckdb
import pandas as pd

from app.api.schemas.common import AnalysisResponse, BatterLeaderboardRow, ResponseMeta, TablePayload
from app.api.schemas.teams import (
    TeamBullpenRow,
    TeamDashboardResponse,
    TeamDashboardSummary,
    TeamIdentity,
    TeamImpactPlay,
    TeamNextGame,
    TeamOutingRow,
    TeamRosterPlayer,
    TeamRotationRow,
    TeamSeasonRecord,
    TeamStarterGame,
    TeamStarterOption,
    TeamPitchVideoResponse,
    TeamPitchVideoRow,
)
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path
from app.services.batter_service import list_batter_leaderboard
from app.services.game_line_service import load_pitcher_game_lines
from app.services.pitcher_service import list_pitcher_leaderboard
from app.services.rotation_service import (
    build_bullpen_availability_table,
    build_game_log_rows,
    build_starter_fatigue_inning_rows,
    filter_starter_rotation,
    load_starter_rotation_table,
    select_fatigue_game_pk,
)
from app.services.video_service import fetch_json


TEAM_CONFIG: dict[str, tuple[str, str, str]] = {
    "ATH": ("Athletics", "#003831", "#efb21e"),
    "AZ": ("Arizona Diamondbacks", "#a71930", "#000000"),
    "ATL": ("Atlanta Braves", "#ce1141", "#13274f"),
    "BAL": ("Baltimore Orioles", "#df4601", "#27251f"),
    "BOS": ("Boston Red Sox", "#bd3039", "#0c2340"),
    "CHC": ("Chicago Cubs", "#0e3386", "#cc3433"),
    "CIN": ("Cincinnati Reds", "#c6011f", "#27251f"),
    "CLE": ("Cleveland Guardians", "#e50022", "#00385d"),
    "COL": ("Colorado Rockies", "#33006f", "#c4ced4"),
    "CWS": ("Chicago White Sox", "#27251f", "#c4ced4"),
    "DET": ("Detroit Tigers", "#0c2340", "#fa4616"),
    "HOU": ("Houston Astros", "#002d62", "#eb6e1f"),
    "KC": ("Kansas City Royals", "#004687", "#bd9b60"),
    "LAA": ("Los Angeles Angels", "#ba0021", "#003263"),
    "LAD": ("Los Angeles Dodgers", "#005a9c", "#ef3e42"),
    "MIA": ("Miami Marlins", "#00a3e0", "#ef3340"),
    "MIL": ("Milwaukee Brewers", "#12284b", "#ffc52f"),
    "MIN": ("Minnesota Twins", "#002b5c", "#d31145"),
    "NYM": ("New York Mets", "#002d72", "#ff5910"),
    "NYY": ("New York Yankees", "#0c2340", "#c4ced4"),
    "PHI": ("Philadelphia Phillies", "#e81828", "#002d72"),
    "PIT": ("Pittsburgh Pirates", "#27251f", "#fdb827"),
    "SD": ("San Diego Padres", "#2f241d", "#ffc425"),
    "SEA": ("Seattle Mariners", "#0c2c56", "#005c5c"),
    "SF": ("San Francisco Giants", "#fd5a1e", "#27251f"),
    "STL": ("St. Louis Cardinals", "#c41e3a", "#0c2340"),
    "TB": ("Tampa Bay Rays", "#092c5c", "#8fbce6"),
    "TEX": ("Texas Rangers", "#003278", "#c0111f"),
    "TOR": ("Toronto Blue Jays", "#134a8e", "#e8291c"),
    "WSH": ("Washington Nationals", "#ab0003", "#14225a"),
}

ROTATION_TEAM_ALIASES = {
    "AZ": "ARI",
    "CWS": "CHW",
    "KC": "KCR",
    "SD": "SDP",
    "SF": "SFG",
    "TB": "TBR",
    "WSH": "WSN",
}

MLB_TEAM_IDS = {
    "AZ": 109, "LAA": 108, "BAL": 110, "BOS": 111, "CHC": 112, "CIN": 113,
    "CLE": 114, "COL": 115, "DET": 116, "HOU": 117, "KC": 118, "LAD": 119,
    "WSH": 120, "NYM": 121, "ATH": 133, "PIT": 134, "SD": 135, "SEA": 136,
    "SF": 137, "STL": 138, "TB": 139, "TEX": 140, "TOR": 141, "MIN": 142,
    "PHI": 143, "ATL": 144, "CWS": 145, "MIA": 146, "NYY": 147, "MIL": 158,
}

_LIVE_CACHE_TTL_SECONDS = 900
_live_cache: dict[
    tuple[int, str],
    tuple[float, TeamSeasonRecord | None, TeamNextGame | None, list[TeamStarterGame]],
] = {}
_roster_cache: dict[tuple[int, str], tuple[float, set[int]]] = {}


def get_team_dashboard(year: int, team_id: str) -> TeamDashboardResponse:
    team_code = str(team_id).strip().upper()
    if team_code not in TEAM_CONFIG:
        raise ValueError(f"Unsupported MLB team: {team_code}")

    name, primary, secondary = TEAM_CONFIG[team_code]
    with ThreadPoolExecutor(max_workers=2) as executor:
        active_pitchers_future = executor.submit(load_team_active_pitcher_ids, year, team_code)
        live_context_future = executor.submit(load_team_live_context, year, team_code)
        pitching = list_pitcher_leaderboard(year=year, role="All", team=team_code)
        batting_payloads = list_batter_leaderboard(year=year, team=team_code)
        batting = [BatterLeaderboardRow(**row) for row in batting_payloads]
        recent_starter_ids = load_recent_team_starter_ids(year, team_code)
        outings = load_latest_team_outings(year, team_code)
        impact_plays = load_team_impact_plays(year, team_code)
        active_pitcher_ids = active_pitchers_future.result()
        season_record, next_game, official_starter_games = live_context_future.result()

    rotation = build_team_rotation(year, team_code, active_pitcher_ids, recent_starter_ids)
    bullpen = build_team_bullpen(year, team_code, active_pitcher_ids, recent_starter_ids)
    starter_games = load_team_starter_games(year, team_code, official_starter_games)
    data_as_of = latest_data_date(year)

    pitching_leaders = sorted(
        pitching,
        key=lambda row: (row.ip is not None, row.ip or 0, row.strikeouts or 0),
        reverse=True,
    )[:5]
    batting_leaders = sorted(
        batting,
        key=lambda row: (row.ops is not None, row.ops or 0, row.plate_appearances or 0),
        reverse=True,
    )[:5]
    roster = build_team_roster(pitching, batting)

    return TeamDashboardResponse(
        meta=ResponseMeta(year=year),
        team=TeamIdentity(
            team_id=team_code,
            name=name,
            year=year,
            primary_color=primary,
            secondary_color=secondary,
            data_as_of=data_as_of,
            logo_url=f"https://www.mlbstatic.com/team-logos/{MLB_TEAM_IDS[team_code]}.svg",
        ),
        summary=TeamDashboardSummary(
            pitchers=len(active_pitcher_ids) if active_pitcher_ids is not None else len(pitching),
            batters=len(batting),
            starters=len(rotation),
            relievers=len(bullpen),
        ),
        rotation=rotation,
        bullpen=bullpen,
        latest_outings=outings,
        pitching_leaders=pitching_leaders,
        batting_leaders=batting_leaders,
        roster=roster,
        impact_plays=impact_plays,
        season_record=season_record,
        next_game=next_game,
        starter_games=starter_games,
    )


def load_team_impact_plays(year: int, team_code: str, limit_per_unit: int = 6) -> list[TeamImpactPlay]:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return []
    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            if not {"pitches", "pitch_play_lookup"}.issubset(tables):
                return []
            player_joins = ""
            pitcher_name = "p.player_name"
            batter_name = "CAST(p.batter AS VARCHAR)"
            if "player_master" in tables:
                player_joins = """
                    LEFT JOIN player_master pitcher_player ON pitcher_player.player_id = p.pitcher
                    LEFT JOIN player_master batter_player ON batter_player.player_id = p.batter
                """
                pitcher_name = "coalesce(pitcher_player.player_name, p.player_name)"
                batter_name = "coalesce(batter_player.player_name, CAST(p.batter AS VARCHAR))"
            rows = conn.execute(
                f"""
                WITH team_pitches AS (
                    SELECT
                        p.*,
                        CASE WHEN p.home_team = ? THEN p.delta_home_win_exp ELSE -p.delta_home_win_exp END AS team_wpa
                    FROM pitches p
                    WHERE (p.home_team = ? OR p.away_team = ?)
                      AND p.delta_home_win_exp IS NOT NULL
                ), latest AS (
                    SELECT max(CAST(game_date AS DATE)) AS latest_date FROM team_pitches
                ), ranked AS (
                    SELECT
                        p.game_pk, CAST(p.game_date AS DATE) AS game_date, l.play_id, l.video_url,
                        CASE WHEN p.home_team = ? THEN p.away_team ELSE p.home_team END AS opponent,
                        CASE WHEN p.home_team = ? THEN 'Home' ELSE 'Away' END AS home_away,
                        p.inning, p.inning_topbot, {pitcher_name} AS pitcher_name,
                        {batter_name} AS batter_name, p.pitch_name, p.events, p.des,
                        p.team_wpa,
                        CASE WHEN p.batter_team = ? THEN 'Batter' ELSE 'Pitcher' END AS team_unit,
                        row_number() OVER (
                            PARTITION BY CASE WHEN p.batter_team = ? THEN 'Batter' ELSE 'Pitcher' END
                            ORDER BY p.team_wpa DESC, p.game_date DESC
                        ) AS unit_rank
                    FROM team_pitches p
                    CROSS JOIN latest
                    JOIN pitch_play_lookup l
                      ON l.game_pk = p.game_pk
                     AND l.at_bat_number = p.at_bat_number
                     AND l.pitch_number = p.pitch_number
                    {player_joins}
                    WHERE p.team_wpa > 0
                      AND CAST(p.game_date AS DATE) >= latest.latest_date - INTERVAL 14 DAY
                      AND l.play_id IS NOT NULL
                      AND l.video_url IS NOT NULL
                )
                SELECT game_pk, game_date, play_id, video_url, opponent, home_away,
                       inning, inning_topbot, pitcher_name, batter_name, pitch_name,
                       events, des, team_wpa, team_unit
                FROM ranked
                WHERE unit_rank <= ?
                ORDER BY team_unit, team_wpa DESC, game_date DESC
                """,
                [
                    team_code, team_code, team_code,
                    team_code, team_code, team_code, team_code,
                    max(0, limit_per_unit),
                ],
            ).fetchall()
    except duckdb.Error:
        return []

    return [
        TeamImpactPlay(
            game_pk=int(row[0]),
            game_date=str(row[1])[:10],
            play_id=str(row[2]),
            video_url=str(row[3]),
            opponent=str(row[4]),
            home_away=str(row[5]),
            inning=int(row[6]),
            inning_half=str(row[7]),
            pitcher_name=str(row[8] or "Unknown"),
            batter_name=str(row[9] or "Unknown"),
            pitch_name=clean_text(row[10]),
            event=clean_text(row[11]),
            description=str(row[12] or "Impact play"),
            team_wpa=round(float(row[13]), 3),
            team_unit=str(row[14]),
        )
        for row in rows
    ]


def load_team_live_context(
    year: int,
    team_code: str,
) -> tuple[TeamSeasonRecord | None, TeamNextGame | None, list[TeamStarterGame]]:
    cache_key = (int(year), team_code)
    cached = _live_cache.get(cache_key)
    now = monotonic()
    if cached and now - cached[0] < _LIVE_CACHE_TTL_SECONDS:
        return cached[1], cached[2], list(cached[3])

    team_mlb_id = MLB_TEAM_IDS[team_code]
    standings_url = (
        "https://statsapi.mlb.com/api/v1/standings?"
        + urlencode({
            "leagueId": "103,104",
            "season": int(year),
            "standingsTypes": "regularSeason",
            "hydrate": "team",
        })
    )
    today = datetime.now().date()
    schedule_url = (
        "https://statsapi.mlb.com/api/v1/schedule?"
        + urlencode({
            "sportId": 1,
            "teamId": team_mlb_id,
            "startDate": (today - timedelta(days=14)).isoformat(),
            "endDate": (today + timedelta(days=1)).isoformat(),
            "hydrate": "probablePitcher,team",
        })
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        standings_future = executor.submit(fetch_json, standings_url, timeout=8)
        schedule_future = executor.submit(fetch_json, schedule_url, timeout=8)

    try:
        standings = standings_future.result()
        record_payload = next(
            (
                team_record
                for division in standings.get("records", [])
                for team_record in division.get("teamRecords", [])
                if (team_record.get("team") or {}).get("id") == team_mlb_id
            ),
            None,
        )
        record = parse_team_record(record_payload)
    except Exception:
        record = None

    try:
        schedule = schedule_future.result()
        games = [game for date in schedule.get("dates", []) for game in date.get("games", [])]
        next_payload = next(
            (
                game for game in games
                if (game.get("status") or {}).get("abstractGameState") != "Final"
                and (game.get("status") or {}).get("detailedState") not in {"Postponed", "Cancelled"}
            ),
            None,
        )
        next_game = parse_next_game(next_payload, team_mlb_id)
        official_starter_games = [
            parsed
            for game in games
            if (parsed := parse_official_starter_game(game, team_mlb_id, team_code)) is not None
        ]
    except Exception:
        next_game = None
        official_starter_games = []

    _live_cache[cache_key] = (now, record, next_game, official_starter_games)
    return record, next_game, list(official_starter_games)


def parse_team_record(payload: dict[str, Any] | None) -> TeamSeasonRecord | None:
    if not payload:
        return None
    team = payload.get("team") or {}
    return TeamSeasonRecord(
        wins=int(payload.get("wins") or 0),
        losses=int(payload.get("losses") or 0),
        winning_percentage=str(payload.get("winningPercentage") or ".000"),
        division_name=clean_text((team.get("division") or {}).get("name")),
        division_rank=clean_text(payload.get("divisionRank")),
        games_back=clean_text(payload.get("gamesBack")),
        streak=clean_text((payload.get("streak") or {}).get("streakCode")),
    )


def parse_next_game(payload: dict[str, Any] | None, team_mlb_id: int) -> TeamNextGame | None:
    if not payload:
        return None
    teams = payload.get("teams") or {}
    is_home = ((teams.get("home") or {}).get("team") or {}).get("id") == team_mlb_id
    team_side = teams.get("home" if is_home else "away") or {}
    opponent_side = teams.get("away" if is_home else "home") or {}
    opponent = opponent_side.get("team") or {}
    return TeamNextGame(
        game_pk=int(payload.get("gamePk")),
        game_datetime=str(payload.get("gameDate") or ""),
        status=str((payload.get("status") or {}).get("detailedState") or "Scheduled"),
        opponent_name=str(opponent.get("name") or "TBD"),
        opponent_code=clean_text(opponent.get("abbreviation")),
        home_away="Home" if is_home else "Away",
        venue=clean_text((payload.get("venue") or {}).get("name")),
        team_probable_pitcher=clean_text((team_side.get("probablePitcher") or {}).get("fullName")),
        team_probable_pitcher_id=to_int((team_side.get("probablePitcher") or {}).get("id")),
        opponent_probable_pitcher=clean_text((opponent_side.get("probablePitcher") or {}).get("fullName")),
        opponent_probable_pitcher_id=to_int((opponent_side.get("probablePitcher") or {}).get("id")),
    )


def parse_official_starter_game(
    payload: dict[str, Any] | None,
    team_mlb_id: int,
    team_code: str,
) -> TeamStarterGame | None:
    if not payload:
        return None
    status_payload = payload.get("status") or {}
    status = str(status_payload.get("detailedState") or "Scheduled")
    if status in {"Postponed", "Cancelled"}:
        return None
    teams = payload.get("teams") or {}
    is_home = ((teams.get("home") or {}).get("team") or {}).get("id") == team_mlb_id
    team_side = teams.get("home" if is_home else "away") or {}
    opponent_side = teams.get("away" if is_home else "home") or {}
    opponent_team = opponent_side.get("team") or {}
    starters: list[TeamStarterOption] = []
    for side, code, label in (
        (team_side, team_code, "Team starter"),
        (opponent_side, clean_text(opponent_team.get("abbreviation")) or "OPP", "Opponent starter"),
    ):
        probable = side.get("probablePitcher") or {}
        pitcher_id = to_int(probable.get("id"))
        pitcher_name = clean_text(probable.get("fullName"))
        if pitcher_id is not None and pitcher_name:
            starters.append(
                TeamStarterOption(
                    team_code=code,
                    pitcher_id=pitcher_id,
                    pitcher_name=pitcher_name,
                    role_label=label,
                )
            )
    return TeamStarterGame(
        game_date=str(payload.get("officialDate") or payload.get("gameDate") or "")[:10],
        game_pk=to_int(payload.get("gamePk")),
        opponent=clean_text(opponent_team.get("abbreviation")) or str(opponent_team.get("name") or "TBD"),
        home_away="Home" if is_home else "Away",
        status=status,
        is_upcoming=str(status_payload.get("abstractGameState") or "") != "Final",
        has_pitch_data=False,
        starters=starters,
    )


def build_team_rotation(
    year: int,
    team_code: str,
    active_pitcher_ids: set[int] | None = None,
    recent_starter_ids: set[int] | None = None,
) -> list[TeamRotationRow]:
    raw = load_starter_rotation_table(year)
    legacy_team = ROTATION_TEAM_ALIASES.get(team_code, team_code)
    filtered = filter_starter_rotation(raw, team=legacy_team, min_gs=1, min_ip_per_gs=0) if not raw.empty else pd.DataFrame()
    rows: list[TeamRotationRow] = []
    for row in filtered.to_dict(orient="records"):
        player_id = to_int(row.get("MLBAMID"))
        if player_id is None:
            continue
        if active_pitcher_ids is not None and player_id not in active_pitcher_ids:
            continue
        if recent_starter_ids and player_id not in recent_starter_ids:
            continue
        rows.append(
            TeamRotationRow(
                player_id=player_id,
                name=str(row.get("Name") or "Unknown"),
                starts=to_int(row.get("GS")) or 0,
                innings=to_float(row.get("IP"), 1),
                qs_rate=clean_text(row.get("QS%")),
                game_score_avg=to_float(row.get("GmScA"), 1),
                pitches_per_start=to_float(row.get("Pit/GS"), 1),
                max_pitches=to_int(row.get("Max")),
            )
        )
    existing_ids = {row.player_id for row in rows}
    missing_ids = (recent_starter_ids or set()) - existing_ids
    if active_pitcher_ids is not None:
        missing_ids &= active_pitcher_ids
    rows.extend(load_team_starter_summaries(year, team_code, missing_ids))
    return sorted(rows, key=lambda row: (row.starts, row.innings or 0), reverse=True)


def build_team_bullpen(
    year: int,
    team_code: str,
    active_pitcher_ids: set[int] | None = None,
    recent_starter_ids: set[int] | None = None,
) -> list[TeamBullpenRow]:
    table = build_bullpen_availability_table(year=year, team=team_code)
    rows: list[TeamBullpenRow] = []
    for row in table.to_dict(orient="records"):
        player_id = to_int(row.get("MLBAMID"))
        if player_id is None:
            continue
        if active_pitcher_ids is not None and player_id not in active_pitcher_ids:
            continue
        if recent_starter_ids and player_id in recent_starter_ids:
            continue
        availability = to_int(row.get("Availability")) or 0
        status = "Ready" if availability >= 28 else "Monitor" if availability >= 15 else "Rest"
        rows.append(
            TeamBullpenRow(
                player_id=player_id,
                name=str(row.get("Name") or "Unknown"),
                throws=clean_text(row.get("Throws")),
                pitches_last_3=to_int(row.get("Pitches Last 3")) or 0,
                pitches_yesterday=to_int(row.get("Pitches Yesterday")) or 0,
                last_game=clean_text(row.get("Last Game")),
                availability=availability,
                status=status,
            )
        )
    return sorted(rows, key=lambda row: (status_order(row.status), -row.availability, row.name))


def load_team_active_pitcher_ids(year: int, team_code: str) -> set[int] | None:
    cache_key = (int(year), team_code)
    cached = _roster_cache.get(cache_key)
    now = monotonic()
    if cached and now - cached[0] < _LIVE_CACHE_TTL_SECONDS:
        return set(cached[1])
    try:
        payload = fetch_json(
            f"https://statsapi.mlb.com/api/v1/teams/{MLB_TEAM_IDS[team_code]}/roster?"
            + urlencode({"rosterType": "active", "season": int(year), "hydrate": "person"}),
            timeout=8,
        )
        pitcher_ids = {
            int(row["person"]["id"])
            for row in payload.get("roster", [])
            if (row.get("position") or {}).get("type") == "Pitcher"
            and (row.get("status") or {}).get("code") == "A"
            and (row.get("person") or {}).get("id") is not None
        }
    except Exception:
        return None
    _roster_cache[cache_key] = (now, pitcher_ids)
    return pitcher_ids


def load_recent_team_starter_ids(year: int, team_code: str, games: int = 15) -> set[int]:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return set()
    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            if "pitcher_game_lines" not in tables:
                return set()
            rows = conn.execute(
                """
                WITH ranked AS (
                    SELECT pitcher_id, game_pk, game_date, pitches,
                           row_number() OVER (
                               PARTITION BY game_pk
                               ORDER BY innings_to_outs DESC, pitches DESC, pitcher_id
                           ) AS pitcher_rank
                    FROM (
                        SELECT *,
                               CAST(floor(try_cast(ip AS DOUBLE)) AS INTEGER) * 3
                               + least(try_cast(split_part(CAST(ip AS VARCHAR), '.', 2) AS INTEGER), 2) AS innings_to_outs
                        FROM pitcher_game_lines
                        WHERE upper(trim(team)) = ?
                    )
                ), latest_games AS (
                    SELECT *
                    FROM ranked
                    WHERE pitcher_rank = 1
                    ORDER BY game_date DESC, game_pk DESC
                    LIMIT ?
                )
                SELECT pitcher_id
                FROM latest_games
                GROUP BY pitcher_id
                HAVING count(*) >= 2
                """,
                [team_code, max(1, games)],
            ).fetchall()
            return {int(row[0]) for row in rows if row[0] is not None}
    except duckdb.Error:
        return set()


def load_team_starter_summaries(year: int, team_code: str, pitcher_ids: set[int]) -> list[TeamRotationRow]:
    if not pitcher_ids:
        return []
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return []
    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            lines = conn.execute(
                "SELECT * FROM pitcher_game_lines WHERE upper(trim(team)) = ?",
                [team_code],
            ).fetchdf()
    except duckdb.Error:
        return []
    if lines.empty:
        return []
    lines["outs"] = lines["ip"].map(innings_to_outs)
    lines["pitches"] = pd.to_numeric(lines["pitches"], errors="coerce").fillna(0).astype(int)
    starters = (
        lines.sort_values(["game_pk", "outs", "pitches", "pitcher_id"], ascending=[True, False, False, True])
        .drop_duplicates("game_pk", keep="first")
    )
    starters["pitcher_id"] = pd.to_numeric(starters["pitcher_id"], errors="coerce")
    starters = starters[starters["pitcher_id"].isin(pitcher_ids)]
    results: list[TeamRotationRow] = []
    for pitcher_id, group in starters.groupby("pitcher_id"):
        total_outs = int(group["outs"].sum())
        results.append(
            TeamRotationRow(
                player_id=int(pitcher_id),
                name=str(group.iloc[-1].get("pitcher_name") or "Unknown"),
                starts=int(len(group)),
                innings=round(total_outs / 3, 1),
                pitches_per_start=round(float(group["pitches"].mean()), 1),
                max_pitches=int(group["pitches"].max()),
            )
        )
    return results


def get_team_starter_workload(
    year: int,
    team_code: str,
    pitcher_id: int,
    game_pk: int | None = None,
) -> AnalysisResponse:
    if team_code not in TEAM_CONFIG:
        raise ValueError(f"Unsupported MLB team: {team_code}")
    selected = pd.Series({"MLBAMID": int(pitcher_id)})
    warnings: list[str] = []
    game_log = build_game_log_rows(year, selected, warnings)
    game_scores = load_pitcher_game_scores(year, int(pitcher_id))
    for row in game_log:
        game_pk_value = to_int(row.get("game_pk"))
        row["game_score"] = game_scores.get(game_pk_value) if game_pk_value is not None else None
    start_game_pks, pitcher_name = load_pitcher_start_game_pks(year, int(pitcher_id))
    selected_game_pk = select_fatigue_game_pk(game_log, game_pk)
    fatigue_rows = build_starter_fatigue_inning_rows(year, selected, selected_game_pk)
    latest_start_game_pk = next(
        (
            int(float(row.get("game_pk") or 0))
            for row in reversed(game_log)
            if int(float(row.get("game_pk") or 0)) in start_game_pks
        ),
        None,
    )
    return AnalysisResponse(
        meta=ResponseMeta(year=year, warnings=warnings),
        charts={
            "selected_player": {"MLBAMID": int(pitcher_id), "Name": pitcher_name or str(pitcher_id)},
            "game_log": game_log,
            "selected_fatigue_game_pk": selected_game_pk,
            "latest_start_game_pk": latest_start_game_pk,
            "start_game_count": len(start_game_pks),
        },
        tables={
            "fatigue_by_inning": TablePayload(
                columns=[
                    {"key": column, "label": column}
                    for column in [
                        "Inning", "Pitches This Inning", "Cumulative Pitches", "Fastball Velo",
                        "Breaking Move", "Spin Rate", "Pregame Readiness", "Fatigue Score",
                    ]
                ],
                rows=fatigue_rows,
            )
        },
    )


def load_pitcher_game_scores(year: int, pitcher_id: int) -> dict[int, float]:
    lines = load_pitcher_game_lines(year, settings.data_dir)
    if lines.empty:
        return {}
    lines = lines[pd.to_numeric(lines["pitcher_id"], errors="coerce").eq(int(pitcher_id))]
    scores: dict[int, float] = {}
    for row in lines.to_dict(orient="records"):
        game_pk = to_int(row.get("game_pk"))
        if game_pk is None:
            continue
        score = calculate_game_score(
            {
                "outs": innings_to_outs(row.get("ip")),
                "hits": row.get("hits"),
                "runs": row.get("runs"),
                "earned_runs": row.get("earned_runs"),
                "walks": row.get("walks"),
                "strikeouts": row.get("strikeouts"),
            }
        )
        if score is not None:
            scores[game_pk] = score
    return scores


def load_pitcher_start_game_pks(year: int, pitcher_id: int) -> tuple[set[int], str | None]:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return set(), None
    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            rows = conn.execute(
                """
                WITH ranked AS (
                    SELECT pitcher_id, pitcher_name, game_pk, game_date, team, pitches,
                           row_number() OVER (
                               PARTITION BY game_pk, team
                               ORDER BY outs DESC, pitches DESC, pitcher_id
                           ) AS pitcher_rank
                    FROM (
                        SELECT *,
                               CAST(floor(try_cast(ip AS DOUBLE)) AS INTEGER) * 3
                               + least(try_cast(split_part(CAST(ip AS VARCHAR), '.', 2) AS INTEGER), 2) AS outs
                        FROM pitcher_game_lines
                    )
                )
                SELECT game_pk, pitcher_name
                FROM ranked
                WHERE pitcher_rank = 1 AND pitcher_id = ?
                ORDER BY game_date, game_pk
                """,
                [int(pitcher_id)],
            ).fetchall()
    except duckdb.Error:
        return set(), None
    return {int(row[0]) for row in rows}, (str(rows[-1][1]) if rows else None)


def load_team_starter_games(
    year: int,
    team_code: str,
    official_games: list[TeamStarterGame] | None = None,
    recent_limit: int = 3,
) -> list[TeamStarterGame]:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    results: list[TeamStarterGame] = []
    if db_path.exists():
        try:
            with duckdb.connect(str(db_path), read_only=True) as conn:
                rows = conn.execute(
                    """
                    WITH recent_games AS (
                        SELECT line.game_pk, max(line.game_date) AS game_date
                        FROM pitcher_game_lines line
                        WHERE upper(trim(line.team)) = ?
                        GROUP BY line.game_pk
                        ORDER BY game_date DESC, line.game_pk DESC
                        LIMIT ?
                    ), ranked AS (
                        SELECT line.game_pk, line.game_date, line.team, line.pitcher_id, line.pitcher_name,
                               game.home_team, game.away_team,
                               row_number() OVER (
                                   PARTITION BY line.game_pk, line.team
                                   ORDER BY outs DESC, line.pitches DESC, line.pitcher_id
                               ) AS pitcher_rank
                        FROM (
                            SELECT *,
                                   CAST(floor(try_cast(ip AS DOUBLE)) AS INTEGER) * 3
                                   + least(try_cast(split_part(CAST(ip AS VARCHAR), '.', 2) AS INTEGER), 2) AS outs
                            FROM pitcher_game_lines
                        ) line
                        JOIN recent_games recent ON recent.game_pk = line.game_pk
                        LEFT JOIN games game ON game.game_pk = line.game_pk
                    )
                    SELECT game_pk, game_date, team, pitcher_id, pitcher_name, home_team, away_team
                    FROM ranked
                    WHERE pitcher_rank = 1
                    ORDER BY game_date DESC, game_pk DESC, team
                    """,
                    [team_code, max(0, recent_limit)],
                ).fetchall()
            grouped: dict[int, list[tuple[Any, ...]]] = {}
            for row in rows:
                grouped.setdefault(int(row[0]), []).append(row)
            ordered_games = sorted(grouped.values(), key=lambda game_rows: (str(game_rows[0][1]), int(game_rows[0][0])))
            for game_rows in ordered_games:
                row = game_rows[0]
                home_team, away_team = clean_text(row[5]), clean_text(row[6])
                is_home = home_team == team_code
                starter_options = [
                    TeamStarterOption(
                        team_code=str(starter_row[2]),
                        pitcher_id=int(starter_row[3]),
                        pitcher_name=str(starter_row[4] or "Unknown"),
                        role_label="Team starter" if str(starter_row[2]) == team_code else "Opponent starter",
                    )
                    for starter_row in sorted(game_rows, key=lambda item: str(item[2]) != team_code)
                ]
                results.append(
                    TeamStarterGame(
                        game_date=str(row[1])[:10],
                        game_pk=int(row[0]),
                        opponent=str(away_team if is_home else home_team or "—"),
                        home_away="Home" if is_home else "Away",
                        status="Final",
                        has_pitch_data=True,
                        starters=starter_options,
                    )
                )
        except duckdb.Error:
            results = []

    local_by_game_pk = {game.game_pk: game for game in results if game.game_pk is not None}
    latest_local_date = max((game.game_date for game in results), default="")
    for official in official_games or []:
        local = local_by_game_pk.get(official.game_pk)
        if local is not None:
            known_ids = {starter.pitcher_id for starter in local.starters}
            local.starters.extend(starter for starter in official.starters if starter.pitcher_id not in known_ids)
            continue
        if not latest_local_date or official.game_date > latest_local_date:
            results.append(official)
    return sorted(results, key=lambda game: (game.game_date, game.game_pk or 0))


def get_team_starter_pitch_videos(
    year: int,
    pitcher_id: int,
    game_pk: int,
    limit: int = 6,
) -> TeamPitchVideoResponse:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return TeamPitchVideoResponse(
            meta=ResponseMeta(year=year), pitcher_id=pitcher_id, pitcher_name=str(pitcher_id), game_pk=game_pk
        )
    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            if not {"pitches", "pitch_play_lookup"}.issubset(tables):
                raise duckdb.Error("Pitch video tables unavailable")
            frame = conn.execute(
                """
                SELECT p.game_date, p.player_name, p.pitch_name, p.release_speed, p.des,
                       l.play_id, l.video_url, p.at_bat_number, p.pitch_number
                FROM pitches p
                JOIN pitch_play_lookup l
                  ON l.game_pk = p.game_pk
                 AND l.at_bat_number = p.at_bat_number
                 AND l.pitch_number = p.pitch_number
                WHERE p.game_pk = ? AND p.pitcher = ?
                  AND l.play_id IS NOT NULL AND l.video_url IS NOT NULL
                ORDER BY p.at_bat_number, p.pitch_number
                """,
                [int(game_pk), int(pitcher_id)],
            ).fetchdf()
    except duckdb.Error:
        frame = pd.DataFrame()
    if frame.empty:
        return TeamPitchVideoResponse(
            meta=ResponseMeta(year=year), pitcher_id=pitcher_id, pitcher_name=str(pitcher_id), game_pk=game_pk
        )
    frame["pitch_name"] = frame["pitch_name"].map(normalize_team_pitch_name)
    counts = frame.groupby("pitch_name", dropna=False).size().sort_values(ascending=False).head(max(0, limit))
    total = int(len(frame))
    rows: list[TeamPitchVideoRow] = []
    for pitch_name, pitch_count in counts.items():
        pitch_rows = frame[frame["pitch_name"].eq(pitch_name)].copy()
        representative = pitch_rows.sort_values("release_speed", ascending=False, na_position="last").iloc[0]
        rows.append(
            TeamPitchVideoRow(
                pitch_name=str(pitch_name),
                pitch_count=int(pitch_count),
                usage_pct=round(int(pitch_count) / total * 100, 1),
                release_speed=to_float(representative.get("release_speed"), 1),
                description=clean_text(representative.get("des")),
                play_id=str(representative["play_id"]),
                video_url=str(representative["video_url"]),
            )
        )
    pitcher_name = clean_text(frame.iloc[0].get("player_name")) or str(pitcher_id)
    if "," in pitcher_name:
        last, first = [part.strip() for part in pitcher_name.split(",", 1)]
        pitcher_name = f"{first} {last}".strip()
    return TeamPitchVideoResponse(
        meta=ResponseMeta(year=year),
        pitcher_id=pitcher_id,
        pitcher_name=pitcher_name,
        game_pk=game_pk,
        game_date=str(frame.iloc[0].get("game_date") or "")[:10] or None,
        pitches=rows,
    )


def normalize_team_pitch_name(value: object) -> str:
    text = str(value or "Unknown").strip()
    aliases = {
        "4-Seam Fastball": "Four-Seam",
        "Four-Seam Fastball": "Four-Seam",
        "4-Seam": "Four-Seam",
        "Split-Finger": "Splitter",
        "Knuckle Curve": "Curveball",
    }
    return aliases.get(text, text)


def load_latest_team_outings(year: int, team_code: str, limit: int = 5) -> list[TeamOutingRow]:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return []
    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            if "pitcher_game_lines" not in tables:
                return []
            lines = conn.execute(
                "SELECT * FROM pitcher_game_lines WHERE upper(trim(team)) = ?",
                [team_code],
            ).fetchdf()
            games = conn.execute("SELECT game_pk, home_team, away_team FROM games").fetchdf() if "games" in tables else pd.DataFrame()
    except duckdb.Error:
        return []
    if lines.empty:
        return []

    lines["outs"] = lines["ip"].map(innings_to_outs)
    for column in ["game_pk", "pitcher_id", "hits", "runs", "earned_runs", "walks", "strikeouts", "pitches"]:
        lines[column] = pd.to_numeric(lines.get(column), errors="coerce").fillna(0).astype(int)
    starters = (
        lines.sort_values(
            ["game_pk", "outs", "pitches", "pitcher_id"],
            ascending=[True, False, False, True],
        )
        .drop_duplicates(subset=["game_pk"], keep="first")
        .sort_values(["game_date", "game_pk"], ascending=[False, False])
        .head(max(0, limit))
    )
    game_lookup: dict[int, dict[str, Any]] = {}
    if not games.empty:
        game_lookup = {int(row["game_pk"]): row for row in games.to_dict(orient="records")}

    outings: list[TeamOutingRow] = []
    for row in starters.to_dict(orient="records"):
        game_pk = int(row["game_pk"])
        game = game_lookup.get(game_pk, {})
        home_team = clean_text(game.get("home_team"))
        away_team = clean_text(game.get("away_team"))
        opponent = away_team if home_team == team_code else home_team
        outings.append(
            TeamOutingRow(
                game_pk=game_pk,
                game_date=str(row.get("game_date") or "")[:10],
                pitcher_id=int(row["pitcher_id"]),
                pitcher_name=str(row.get("pitcher_name") or "Unknown"),
                opponent=opponent,
                home_away=clean_text(row.get("home_away")),
                ip=clean_text(row.get("ip")),
                hits=int(row["hits"]),
                runs=int(row["runs"]),
                earned_runs=int(row["earned_runs"]),
                walks=int(row["walks"]),
                strikeouts=int(row["strikeouts"]),
                pitches=int(row["pitches"]),
                game_score=calculate_game_score(row),
            )
        )
    return outings


def build_team_roster(pitching: list[Any], batting: list[BatterLeaderboardRow]) -> list[TeamRosterPlayer]:
    roster = [
        TeamRosterPlayer(
            player_id=row.player_id,
            name=row.name,
            team=row.team,
            group="Pitcher",
            role=row.role,
            games=row.games,
            starts=row.starts,
        )
        for row in pitching
    ]
    roster.extend(
        TeamRosterPlayer(
            player_id=row.player_id,
            name=row.name,
            team=row.team,
            group="Batter",
            role="Batter",
            games=row.games,
        )
        for row in batting
    )
    return sorted(roster, key=lambda row: (row.group, row.name))


def latest_data_date(year: int) -> str | None:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return None
    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            if "games" not in tables:
                return None
            value = conn.execute("SELECT max(game_date) FROM games").fetchone()[0]
            return str(value)[:10] if value else None
    except duckdb.Error:
        return None


def innings_to_outs(value: object) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    try:
        whole, _, fraction = text.partition(".")
        return int(float(whole or 0)) * 3 + min(max(int((fraction or "0")[:1]), 0), 2)
    except (TypeError, ValueError):
        return 0


def calculate_game_score(row: dict[str, Any]) -> float | None:
    outs = int(row.get("outs", 0) or 0)
    if outs <= 0:
        return None
    hits = int(row.get("hits", 0) or 0)
    runs = int(row.get("runs", 0) or 0)
    earned_runs = int(row.get("earned_runs", 0) or 0)
    walks = int(row.get("walks", 0) or 0)
    strikeouts = int(row.get("strikeouts", 0) or 0)
    return float(
        50
        + outs
        + max(0, (outs // 3) - 4) * 2
        + strikeouts
        - hits * 2
        - earned_runs * 4
        - max(0, runs - earned_runs) * 2
        - walks
    )


def status_order(status: str) -> int:
    return {"Ready": 0, "Monitor": 1, "Rest": 2}.get(status, 3)


def clean_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text if text and text.lower() not in {"nan", "none"} else None


def to_int(value: object) -> int | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(numeric) else int(numeric)


def to_float(value: object, digits: int = 1) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(numeric) else round(float(numeric), digits)
