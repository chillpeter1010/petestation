from app.services.team_dashboard_service import (
    ROTATION_TEAM_ALIASES,
    TEAM_CONFIG,
    calculate_game_score,
    get_team_dashboard,
    innings_to_outs,
    parse_official_starter_game,
)


def test_team_config_covers_all_mlb_teams():
    assert len(TEAM_CONFIG) == 30
    assert ROTATION_TEAM_ALIASES["SF"] == "SFG"


def test_innings_and_game_score_helpers():
    assert innings_to_outs("6.2") == 20
    score = calculate_game_score(
        {"outs": 18, "hits": 4, "runs": 2, "earned_runs": 2, "walks": 1, "strikeouts": 7}
    )
    assert score == 62.0


def test_team_dashboard_builds_current_sections():
    response = get_team_dashboard(year=2026, team_id="AZ")

    assert response.team.team_id == "AZ"
    assert response.summary.pitchers > 0
    assert response.rotation
    assert response.latest_outings
    assert response.pitching_leaders
    assert response.batting_leaders
    assert response.roster


def test_parse_official_starter_game_keeps_game_without_statcast_data():
    game = parse_official_starter_game(
        {
            "gamePk": 824404,
            "officialDate": "2026-08-02",
            "status": {"abstractGameState": "Final", "detailedState": "Final"},
            "teams": {
                "away": {
                    "team": {"id": 109, "abbreviation": "AZ"},
                    "probablePitcher": {"id": 518876, "fullName": "Merrill Kelly"},
                },
                "home": {
                    "team": {"id": 114, "abbreviation": "CLE"},
                    "probablePitcher": {"id": 668909, "fullName": "Gavin Williams"},
                },
            },
        },
        team_mlb_id=109,
        team_code="AZ",
    )

    assert game is not None
    assert game.game_date == "2026-08-02"
    assert game.has_pitch_data is False
    assert game.is_upcoming is False
    assert [starter.pitcher_name for starter in game.starters] == ["Merrill Kelly", "Gavin Williams"]
