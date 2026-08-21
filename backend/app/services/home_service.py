from __future__ import annotations

import duckdb

from app.api.schemas.common import ResponseMeta
from app.api.schemas.home import HomeRecommendationsResponse, HomeVideoRecommendation
from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path


TEAM_SEARCH_NAMES = {
    "ATH": "Athletics A's", "AZ": "Arizona Diamondbacks D-backs", "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles", "BOS": "Boston Red Sox", "CHC": "Chicago Cubs",
    "CIN": "Cincinnati Reds", "CLE": "Cleveland Guardians", "COL": "Colorado Rockies",
    "CWS": "Chicago White Sox", "DET": "Detroit Tigers", "HOU": "Houston Astros",
    "KC": "Kansas City Royals", "LAA": "Los Angeles Angels", "LAD": "Los Angeles Dodgers",
    "MIA": "Miami Marlins", "MIL": "Milwaukee Brewers", "MIN": "Minnesota Twins",
    "NYM": "New York Mets", "NYY": "New York Yankees", "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates", "SD": "San Diego Padres", "SEA": "Seattle Mariners",
    "SF": "San Francisco Giants", "STL": "St Louis Cardinals", "TB": "Tampa Bay Rays",
    "TEX": "Texas Rangers", "TOR": "Toronto Blue Jays", "WSH": "Washington Nationals",
}


def get_home_video_recommendations(year: int = 2026) -> HomeRecommendationsResponse:
    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return HomeRecommendationsResponse(
            meta=ResponseMeta(year=year, warnings=[f"Season database not found: {db_path}"])
        )

    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            if not {"pitches", "pitch_play_lookup"}.issubset(tables):
                return HomeRecommendationsResponse(
                    meta=ResponseMeta(year=year, warnings=["Pitch or video lookup table is unavailable."])
                )
            has_players = "player_master" in tables
            joins = "" if not has_players else """
                LEFT JOIN player_master pitcher_player ON pitcher_player.player_id = p.pitcher
                LEFT JOIN player_master batter_player ON batter_player.player_id = p.batter
            """
            pitcher_name = "p.player_name" if not has_players else "coalesce(pitcher_player.player_name, p.player_name)"
            batter_name = "CAST(p.batter AS VARCHAR)" if not has_players else "coalesce(batter_player.player_name, CAST(p.batter AS VARCHAR))"
            frame = conn.execute(
                f"""
                WITH eligible AS (
                    SELECT DISTINCT
                        p.game_pk,
                        CAST(p.game_date AS DATE) AS game_date,
                        l.play_id,
                        l.video_url,
                        p.home_team,
                        p.away_team,
                        p.inning,
                        p.inning_topbot,
                        {pitcher_name} AS pitcher_name,
                        {batter_name} AS batter_name,
                        p.pitch_name,
                        p.events,
                        p.des,
                        abs(p.delta_home_win_exp) AS wpa
                    FROM pitches p
                    JOIN pitch_play_lookup l
                      ON l.game_pk = p.game_pk
                     AND l.at_bat_number = p.at_bat_number
                     AND l.pitch_number = p.pitch_number
                    {joins}
                    WHERE l.play_id IS NOT NULL
                      AND trim(CAST(l.play_id AS VARCHAR)) NOT IN ('', 'None', 'nan', 'NaN')
                      AND l.video_url IS NOT NULL
                      AND trim(CAST(l.video_url AS VARCHAR)) NOT IN ('', 'None', 'nan', 'NaN')
                ), latest AS (
                    SELECT max(game_date) AS latest_date FROM eligible
                ), recent_pool AS (
                    SELECT e.*
                    FROM eligible e, latest
                    WHERE e.game_date >= latest_date - INTERVAL 13 DAY
                    ORDER BY e.wpa DESC NULLS LAST
                    LIMIT 100
                ), recent_pick AS (
                    SELECT *, 'Recent high WPA' AS recommendation_source, 1 AS source_order
                    FROM recent_pool
                    ORDER BY random()
                    LIMIT 6
                ), month_pool AS (
                    SELECT e.*
                    FROM eligible e, latest
                    WHERE date_trunc('month', e.game_date) = date_trunc('month', latest.latest_date)
                      AND e.play_id NOT IN (SELECT play_id FROM recent_pick)
                    ORDER BY e.wpa DESC NULLS LAST
                    LIMIT 200
                ), month_pick AS (
                    SELECT *, 'Top plays this data month' AS recommendation_source, 2 AS source_order
                    FROM month_pool
                    ORDER BY random()
                    LIMIT 4
                ), random_pick AS (
                    SELECT *, 'From the archive' AS recommendation_source, 3 AS source_order
                    FROM eligible
                    WHERE play_id NOT IN (SELECT play_id FROM recent_pick)
                      AND play_id NOT IN (SELECT play_id FROM month_pick)
                    ORDER BY random()
                    LIMIT 2
                ), initial AS (
                    SELECT * FROM recent_pick
                    UNION ALL SELECT * FROM month_pick
                    UNION ALL SELECT * FROM random_pick
                ), fallback AS (
                    SELECT *, 'From the archive' AS recommendation_source, 4 AS source_order
                    FROM eligible
                    WHERE play_id NOT IN (SELECT play_id FROM initial)
                    ORDER BY random()
                    LIMIT (SELECT greatest(0, 12 - count(*)) FROM initial)
                ), final AS (
                    SELECT * FROM initial
                    UNION ALL SELECT * FROM fallback
                )
                SELECT f.*, latest.latest_date
                FROM final f
                CROSS JOIN latest
                ORDER BY source_order, game_date DESC
                """
            ).fetchdf()
    except duckdb.Error as exc:
        return HomeRecommendationsResponse(
            meta=ResponseMeta(year=year, warnings=[f"Video recommendations unavailable: {exc}"])
        )

    if frame.empty:
        return HomeRecommendationsResponse(
            meta=ResponseMeta(year=year, warnings=["No videos were available for recommendation."])
        )

    latest_date = str(frame.iloc[0]["latest_date"])[:10]
    videos = [
        HomeVideoRecommendation(
            game_pk=int(row.game_pk),
            game_date=str(row.game_date)[:10],
            play_id=str(row.play_id),
            video_url=str(row.video_url),
            home_team=str(row.home_team),
            away_team=str(row.away_team),
            inning=int(row.inning) if row.inning is not None else None,
            inning_half=str(row.inning_topbot) if row.inning_topbot is not None else None,
            pitcher_name=str(row.pitcher_name or "Unknown pitcher"),
            batter_name=str(row.batter_name or "Unknown batter"),
            pitch_name=str(row.pitch_name) if row.pitch_name is not None else None,
            event=str(row.events) if row.events is not None else None,
            description=str(row.des or "MLB pitch video"),
            wpa=round(float(row.wpa), 3) if row.wpa is not None else None,
            recommendation_source=str(row.recommendation_source),
        )
        for row in frame.itertuples(index=False)
    ]
    return HomeRecommendationsResponse(
        meta=ResponseMeta(year=year),
        latest_data_date=latest_date,
        videos=videos,
    )


def search_home_videos(query: str, year: int = 2026, limit: int = 12) -> HomeRecommendationsResponse:
    terms = [term for term in query.casefold().split() if term]
    if not terms:
        return HomeRecommendationsResponse(meta=ResponseMeta(year=year))

    db_path = get_season_duckdb_path(year, settings.data_dir)
    if not db_path.exists():
        return HomeRecommendationsResponse(
            meta=ResponseMeta(year=year, warnings=[f"Season database not found: {db_path}"])
        )

    try:
        with duckdb.connect(str(db_path), read_only=True) as conn:
            tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
            if not {"pitches", "pitch_play_lookup"}.issubset(tables):
                return HomeRecommendationsResponse(
                    meta=ResponseMeta(year=year, warnings=["Pitch or video lookup table is unavailable."])
                )
            has_players = "player_master" in tables
            joins = "" if not has_players else """
                LEFT JOIN player_master pitcher_player ON pitcher_player.player_id = p.pitcher
                LEFT JOIN player_master batter_player ON batter_player.player_id = p.batter
            """
            pitcher_name = "p.player_name" if not has_players else "coalesce(pitcher_player.player_name, p.player_name)"
            batter_name = "CAST(p.batter AS VARCHAR)" if not has_players else "coalesce(batter_player.player_name, CAST(p.batter AS VARCHAR))"
            home_team_name = "CASE p.home_team " + " ".join(
                "WHEN '{}' THEN '{}'".format(code, name.replace("'", "''")) for code, name in TEAM_SEARCH_NAMES.items()
            ) + " ELSE p.home_team END"
            away_team_name = "CASE p.away_team " + " ".join(
                "WHEN '{}' THEN '{}'".format(code, name.replace("'", "''")) for code, name in TEAM_SEARCH_NAMES.items()
            ) + " ELSE p.away_team END"
            search_text = f"""
                lower(concat_ws(' ',
                    {pitcher_name}, {batter_name}, p.home_team, p.away_team,
                    {home_team_name}, {away_team_name},
                    p.pitch_name, replace(p.events, '_', ' '), p.des
                ))
            """
            filters = " AND ".join([f"{search_text} LIKE ?" for _ in terms])
            parameters = [f"%{term}%" for term in terms]
            parameters.append(limit)
            frame = conn.execute(
                f"""
                WITH eligible AS (
                    SELECT DISTINCT
                        p.game_pk,
                        CAST(p.game_date AS DATE) AS game_date,
                        l.play_id,
                        l.video_url,
                        p.home_team,
                        p.away_team,
                        p.inning,
                        p.inning_topbot,
                        {pitcher_name} AS pitcher_name,
                        {batter_name} AS batter_name,
                        p.pitch_name,
                        p.events,
                        p.des,
                        abs(p.delta_home_win_exp) AS wpa
                    FROM pitches p
                    JOIN pitch_play_lookup l
                      ON l.game_pk = p.game_pk
                     AND l.at_bat_number = p.at_bat_number
                     AND l.pitch_number = p.pitch_number
                    {joins}
                    WHERE l.play_id IS NOT NULL
                      AND trim(CAST(l.play_id AS VARCHAR)) NOT IN ('', 'None', 'nan', 'NaN')
                      AND l.video_url IS NOT NULL
                      AND trim(CAST(l.video_url AS VARCHAR)) NOT IN ('', 'None', 'nan', 'NaN')
                      AND {filters}
                )
                SELECT *, 'Search result' AS recommendation_source,
                       max(game_date) OVER () AS latest_date
                FROM eligible
                ORDER BY wpa DESC NULLS LAST, game_date DESC
                LIMIT ?
                """,
                parameters,
            ).fetchdf()
    except duckdb.Error as exc:
        return HomeRecommendationsResponse(
            meta=ResponseMeta(year=year, warnings=[f"Video search unavailable: {exc}"])
        )

    if frame.empty:
        return HomeRecommendationsResponse(meta=ResponseMeta(year=year))

    latest_date = str(frame.iloc[0]["latest_date"])[:10]
    videos = [
        HomeVideoRecommendation(
            game_pk=int(row.game_pk),
            game_date=str(row.game_date)[:10],
            play_id=str(row.play_id),
            video_url=str(row.video_url),
            home_team=str(row.home_team),
            away_team=str(row.away_team),
            inning=int(row.inning) if row.inning is not None else None,
            inning_half=str(row.inning_topbot) if row.inning_topbot is not None else None,
            pitcher_name=str(row.pitcher_name or "Unknown pitcher"),
            batter_name=str(row.batter_name or "Unknown batter"),
            pitch_name=str(row.pitch_name) if row.pitch_name is not None else None,
            event=str(row.events) if row.events is not None else None,
            description=str(row.des or "MLB pitch video"),
            wpa=round(float(row.wpa), 3) if row.wpa is not None else None,
            recommendation_source="Search result",
        )
        for row in frame.itertuples(index=False)
    ]
    return HomeRecommendationsResponse(
        meta=ResponseMeta(year=year),
        latest_data_date=latest_date,
        videos=videos,
    )
