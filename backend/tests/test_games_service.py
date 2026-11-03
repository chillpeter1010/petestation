from pathlib import Path

import duckdb

from app.services.games_service import _official_batting, _official_pitcher_eras, get_game_pitching, list_games


def _build_game_db(data_dir: Path) -> None:
    season_dir = data_dir / "MLB2026"
    season_dir.mkdir(parents=True)
    db_path = season_dir / "mlb_2026.duckdb"
    with duckdb.connect(str(db_path)) as conn:
        conn.execute("""
            CREATE TABLE games (
                game_pk BIGINT, game_date VARCHAR, home_team VARCHAR, away_team VARCHAR,
                game_type VARCHAR, total_pitches BIGINT, total_plate_appearances BIGINT
            )
        """)
        conn.execute("INSERT INTO games VALUES (10, '2026-07-01', 'SEA', 'LAA', 'R', 4, 2), (11, '2026-07-02', 'NYY', 'BOS', 'R', 1, 1)")
        conn.execute("""
            CREATE TABLE pitches (
                game_pk BIGINT, pitcher BIGINT, batter BIGINT, pitcher_team VARCHAR,
                pitch_name VARCHAR, launch_speed DOUBLE, events VARCHAR, release_speed DOUBLE,
                inning BIGINT, inning_topbot VARCHAR, at_bat_number BIGINT, pitch_number BIGINT,
                post_away_score BIGINT, away_score BIGINT, post_home_score BIGINT, home_score BIGINT,
                description VARCHAR, plate_x DOUBLE, plate_z DOUBLE, balls BIGINT, strikes BIGINT,
                outs_when_up BIGINT, on_1b BIGINT, on_2b BIGINT, on_3b BIGINT, des VARCHAR
            )
        """)
        conn.execute("""
            INSERT INTO pitches VALUES
            (10, 100, 200, 'SEA', 'Four-Seam Fastball', NULL, NULL, 95.0, 1, 'Top', 1, 1, 0, 0, 0, 0, 'called_strike', 0.1, 2.6, 0, 0, 0, NULL, NULL, NULL, NULL),
            (10, 100, 200, 'SEA', 'Slider', NULL, 'strikeout', 87.0, 1, 'Top', 1, 2, 0, 0, 0, 0, 'swinging_strike', -0.2, 2.1, 0, 1, 0, NULL, NULL, NULL, 'Away Hitter strikes out swinging.'),
            (10, 101, 201, 'LAA', 'Four-Seam Fastball', 101.0, NULL, 96.0, 1, 'Bot', 2, 1, 0, 0, 0, 0, 'foul', 0.0, 3.0, 0, 0, 0, NULL, NULL, NULL, NULL),
            (10, 101, 201, 'LAA', 'Four-Seam Fastball', 101.0, 'home_run', 97.0, 1, 'Bot', 2, 2, 0, 0, 1, 0, 'hit_into_play', 0.3, 2.8, 0, 1, 0, NULL, NULL, NULL, 'Home Hitter homers.')
        """)
        conn.execute("CREATE TABLE game_player_lookup (game_pk BIGINT, player_id BIGINT, player_name VARCHAR, role VARCHAR)")
        conn.execute("INSERT INTO game_player_lookup VALUES (10,100,'Home Pitcher','pitcher'),(10,101,'Away Pitcher','pitcher'),(10,200,'Away Hitter','batter'),(10,201,'Home Hitter','batter')")
        conn.execute("CREATE TABLE player_master (player_id BIGINT, player_name VARCHAR)")
        conn.execute("INSERT INTO player_master VALUES (100,'Canonical Home Pitcher'),(101,'Canonical Away Pitcher'),(200,'Canonical Away Hitter'),(201,'Canonical Home Hitter')")
        conn.execute("""
            CREATE TABLE pitcher_game_lines (
                game_pk BIGINT, game_date VARCHAR, team VARCHAR, home_away VARCHAR,
                pitcher_id BIGINT, pitcher_name VARCHAR, ip VARCHAR, hits BIGINT, runs BIGINT,
                earned_runs BIGINT, walks BIGINT, strikeouts BIGINT, pitches BIGINT, batters_faced BIGINT
            )
        """)
        conn.execute("INSERT INTO pitcher_game_lines VALUES (10,'2026-07-01','SEA','home',100,'Home Pitcher','1.0',0,0,0,0,1,2,1),(10,'2026-07-01','LAA','away',101,'Away Pitcher','1.0',1,1,1,0,0,2,1)")


def test_list_games_filters_team_and_uses_team_latest_date(tmp_path):
    _build_game_db(tmp_path)

    payload = list_games(year=2026, team="sea", data_dir=tmp_path)

    assert payload["team"] == "SEA"
    assert payload["latest_game_date"] == "2026-07-01"
    assert [row["game_pk"] for row in payload["games"]] == [10]


def test_game_detail_builds_scoreboard_box_and_feed(tmp_path):
    _build_game_db(tmp_path)

    payload = get_game_pitching(year=2026, game_pk=10, data_dir=tmp_path, allow_official_fetch=False)

    assert payload["scoreboard"]["away"] == {"team": "LAA", "runs": 0, "hits": 0, "errors": 0}
    assert payload["scoreboard"]["home"] == {"team": "SEA", "runs": 1, "hits": 1, "errors": 0}
    assert payload["scoreboard"]["innings"] == [{"inning": 1, "away": 0, "home": 1}]
    assert payload["batting"][1]["hitters"][0]["name"] == "Canonical Home Hitter"
    assert payload["batting"][1]["hitters"][0]["home_runs"] == 1
    assert payload["plays"][0]["description"] == "Home Hitter homers."
    assert len(payload["plays"][0]["pitches"]) == 2


def test_game_detail_uses_player_master_when_game_lookup_is_missing(tmp_path):
    _build_game_db(tmp_path)
    db_path = tmp_path / "MLB2026" / "mlb_2026.duckdb"
    with duckdb.connect(str(db_path)) as conn:
        conn.execute("DELETE FROM game_player_lookup WHERE role = 'batter'")

    payload = get_game_pitching(year=2026, game_pk=10, data_dir=tmp_path, allow_official_fetch=False)

    assert payload["batting"][0]["hitters"][0]["name"] == "Canonical Away Hitter"
    assert payload["batting"][1]["hitters"][0]["name"] == "Canonical Home Hitter"
    assert payload["plays"][0]["batter_name"] == "Canonical Home Hitter"


def test_official_batting_order_groups_substitutes_and_keeps_zero_pa_players():
    payload = {
        "teams": {
            "away": {
                "team": {"abbreviation": "HOU"},
                "players": {
                    "ID1": {
                        "person": {"id": 1, "fullName": "Starter Two"},
                        "battingOrder": "200",
                        "position": {"abbreviation": "DH"},
                        "stats": {"batting": {"plateAppearances": 4, "atBats": 4, "hits": 1}},
                        "seasonStats": {"batting": {"avg": ".277"}},
                    },
                    "ID2": {
                        "person": {"id": 2, "fullName": "Replacement Two"},
                        "battingOrder": "201",
                        "position": {"abbreviation": "DH"},
                        "stats": {"batting": {"plateAppearances": 1, "atBats": 1, "hits": 0}},
                    },
                    "ID3": {
                        "person": {"id": 3, "fullName": "Starter Four"},
                        "battingOrder": "400",
                        "position": {"abbreviation": "2B"},
                        "stats": {"batting": {"plateAppearances": 5, "atBats": 5, "hits": 1}},
                    },
                    "ID4": {
                        "person": {"id": 4, "fullName": "Defensive Replacement"},
                        "battingOrder": "401",
                        "position": {"abbreviation": "2B"},
                        "stats": {"batting": {"plateAppearances": 0, "atBats": 0, "hits": 0}},
                    },
                },
            },
            "home": {"team": {"abbreviation": "ATH"}, "players": {}},
        }
    }

    batting = _official_batting(payload, {1: 2})

    assert [row["player_id"] for row in batting[0]["hitters"]] == [1, 2, 3, 4]
    assert batting[0]["hitters"][0]["lineup_slot"] == 2
    assert batting[0]["hitters"][1]["is_substitute"] is True
    assert batting[0]["hitters"][3]["pa"] == 0
    assert batting[0]["hitters"][0]["hard_hits"] == 2
    assert batting[0]["hitters"][0]["average"] == 0.277


def test_official_pitcher_eras_use_season_stats():
    payload = {
        "teams": {
            "away": {
                "pitchers": [10, 11],
                "players": {
                    "ID10": {"seasonStats": {"pitching": {"era": "3.82"}}},
                    "ID11": {"seasonStats": {"pitching": {"era": "-.--"}}},
                },
            },
            "home": {"pitchers": [], "players": {}},
        }
    }

    assert _official_pitcher_eras(payload) == {10: "3.82"}
