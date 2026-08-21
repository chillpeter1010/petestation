from app.services.pitching_export_service import get_pitching_overview, get_pitching_pitcher


def test_pitching_overview_and_pitcher_exports_are_readable() -> None:
    overview = get_pitching_overview(year=2026, minimum_pitches=125, minimum_innings=5)
    assert overview.total_pitchers > 0
    assert overview.rows[0].pitching_plus >= overview.rows[-1].pitching_plus
    assert overview.public_candidate in overview.candidates
    assert 2026 in overview.available_years
    assert all(row.innings_pitched >= 5 for row in overview.rows)
    assert overview.rows[0].pitch_type_scores
    assert sum(item.count for item in overview.distribution) == overview.total_pitchers

    detail = get_pitching_pitcher(year=2026, pitcher_id=overview.rows[0].pitcher_id)
    assert detail.pitcher.pitcher_id == overview.rows[0].pitcher_id
    assert detail.pitch_types
    assert detail.outings
