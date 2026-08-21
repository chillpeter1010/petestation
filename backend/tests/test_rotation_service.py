from app.services.rotation_service import get_bullpen_role_response, get_starter_rotation_response


def test_starter_rotation_response_has_rotation_rows():
    response = get_starter_rotation_response(year=2025)

    assert response.meta.year == 2025
    assert response.tables["rotation"].rows
    assert response.summary[0].key == "starters"
    assert response.summary[0].value > 0


def test_starter_rotation_team_filter_limits_rows():
    response = get_starter_rotation_response(year=2025, team="SFG")

    rows = response.tables["rotation"].rows
    assert rows
    assert {row["Tm"] for row in rows} == {"SFG"}


def test_starter_rotation_selected_player_builds_workload_and_game_log():
    response = get_starter_rotation_response(year=2025, player_id=657277)

    selected = response.charts["selected_player"]
    assert selected["Name"] == "Logan Webb"
    assert response.tables["workload"].rows
    assert response.tables["pitch_profile"].rows
    assert "game_log" in response.tables


def test_bullpen_role_response_has_rows_and_usage():
    response = get_bullpen_role_response(year=2025)

    assert response.tables["bullpen"].rows
    assert response.tables["role_usage"].rows
    assert response.tables["tactical"].rows
    assert response.tables["role_board"].rows
    assert response.tables["usage_timing"].rows
    assert response.tables["stability"].rows
    assert "availability" in response.tables
    assert response.summary[0].key == "relievers"


def test_bullpen_role_derived_views_include_legacy_role_fields():
    response = get_bullpen_role_response(year=2025, team="BOS")

    tactical_row = response.tables["tactical"].rows[0]
    role_row = response.tables["role_board"].rows[0]
    timing_row = response.tables["usage_timing"].rows[0]
    stability_row = response.tables["stability"].rows[0]
    assert "PrimaryRole" in tactical_row
    assert "TacticalTags" in tactical_row
    assert "RoleScore" in role_row
    assert "HighLev%" in timing_row
    assert "RoleConsistency" in stability_row


def test_bullpen_availability_uses_2026_workload_slice():
    response = get_bullpen_role_response(year=2025, team="BOS")

    assert response.charts["availability_year"] == 2026
    assert response.tables["availability"].rows
    availability_row = response.tables["availability"].rows[0]
    assert "Pitches Last 3" in availability_row
    assert "Availability" in availability_row


def test_bullpen_role_team_filter_limits_rows():
    response = get_bullpen_role_response(year=2025, team="BOS")

    rows = response.tables["bullpen"].rows
    assert rows
    assert {row["Team"] for row in rows} == {"BOS"}
