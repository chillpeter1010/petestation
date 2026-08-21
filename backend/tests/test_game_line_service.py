from app.services.game_line_service import clean_pitcher_game_line, parse_pitcher_game_line


def test_parse_pitcher_game_line_reads_official_pitching_stats():
    payload = {
        "teams": {
            "home": {
                "players": {
                    "ID123": {
                        "person": {"fullName": "Test Pitcher"},
                        "stats": {
                            "pitching": {
                                "inningsPitched": "5.1",
                                "hits": 6,
                                "runs": 2,
                                "earnedRuns": 1,
                                "baseOnBalls": 3,
                                "strikeOuts": 7,
                                "pitchesThrown": 91,
                                "battersFaced": 24,
                            }
                        },
                    }
                }
            },
            "away": {"players": {}},
        }
    }

    line = clean_pitcher_game_line(parse_pitcher_game_line(payload, 123))

    assert line["ip"] == "5.1"
    assert line["earned_runs"] == 1
    assert line["pitches"] == 91
    assert line["batters_faced"] == 24


def test_parse_pitcher_game_line_returns_none_when_pitcher_is_missing():
    assert parse_pitcher_game_line({"teams": {"home": {"players": {}}, "away": {"players": {}}}}, 999) is None
