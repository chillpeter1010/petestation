from datetime import date, timedelta

import duckdb

from app.services.home_service import get_home_video_recommendations, search_home_videos


def test_home_recommendations_returns_six_four_two_mix(tmp_path, monkeypatch):
    db_path = tmp_path / "season.duckdb"
    with duckdb.connect(str(db_path)) as conn:
        conn.execute("""
            CREATE TABLE pitches (
                game_pk BIGINT, game_date DATE, at_bat_number BIGINT, pitch_number BIGINT,
                pitcher BIGINT, batter BIGINT, player_name VARCHAR, home_team VARCHAR,
                away_team VARCHAR, inning BIGINT, inning_topbot VARCHAR, pitch_name VARCHAR,
                events VARCHAR, des VARCHAR, delta_home_win_exp DOUBLE
            )
        """)
        conn.execute("""
            CREATE TABLE pitch_play_lookup (
                game_pk BIGINT, at_bat_number BIGINT, pitch_number BIGINT,
                play_id VARCHAR, video_url VARCHAR
            )
        """)
        latest = date(2026, 7, 31)
        for index in range(30):
            game_date = latest - timedelta(days=index % 20)
            conn.execute(
                "INSERT INTO pitches VALUES (?, ?, ?, 1, 10, 20, 'Pitcher', 'AZ', 'PIT', 8, 'Top', 'Slider', 'single', ?, ?)",
                [1000 + index, game_date, index + 1, f"Play {index}", index / 100],
            )
            conn.execute(
                "INSERT INTO pitch_play_lookup VALUES (?, ?, 1, ?, ?)",
                [1000 + index, index + 1, f"play-{index}", f"https://example.com/{index}"],
            )

    monkeypatch.setattr("app.services.home_service.get_season_duckdb_path", lambda *_: db_path)
    payload = get_home_video_recommendations(2026)

    assert payload.latest_data_date == "2026-07-31"
    assert len(payload.videos) == 12
    sources = [video.recommendation_source for video in payload.videos]
    assert sources.count("Recent high WPA") == 6
    assert sources.count("Top plays this data month") == 4
    assert sources.count("From the archive") == 2
    assert len({video.play_id for video in payload.videos}) == 12


def test_home_video_search_matches_all_keywords(tmp_path, monkeypatch):
    db_path = tmp_path / "season.duckdb"
    with duckdb.connect(str(db_path)) as conn:
        conn.execute("""
            CREATE TABLE pitches (
                game_pk BIGINT, game_date DATE, at_bat_number BIGINT, pitch_number BIGINT,
                pitcher BIGINT, batter BIGINT, player_name VARCHAR, home_team VARCHAR,
                away_team VARCHAR, inning BIGINT, inning_topbot VARCHAR, pitch_name VARCHAR,
                events VARCHAR, des VARCHAR, delta_home_win_exp DOUBLE
            )
        """)
        conn.execute("""
            CREATE TABLE pitch_play_lookup (
                game_pk BIGINT, at_bat_number BIGINT, pitch_number BIGINT,
                play_id VARCHAR, video_url VARCHAR
            )
        """)
        conn.execute(
            "INSERT INTO pitches VALUES (1, '2026-07-31', 1, 1, 10, 20, 'Pitcher', 'AZ', 'PIT', 8, 'Top', 'Slider', 'home_run', 'A grand slam to left field', 0.42)"
        )
        conn.execute("INSERT INTO pitch_play_lookup VALUES (1, 1, 1, 'grand-slam-play', 'https://example.com/grand-slam')")

    monkeypatch.setattr("app.services.home_service.get_season_duckdb_path", lambda *_: db_path)
    payload = search_home_videos("grand slam", 2026)

    assert [video.play_id for video in payload.videos] == ["grand-slam-play"]
    assert payload.videos[0].recommendation_source == "Search result"
    assert [video.play_id for video in search_home_videos("diamondbacks", 2026).videos] == ["grand-slam-play"]
