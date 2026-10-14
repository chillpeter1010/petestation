import duckdb
import pandas as pd
import pytest

from app.services import wpa_service


def test_plate_appearance_wpa_uses_next_pa_boundary_not_pitch_deltas(monkeypatch, tmp_path):
    db_path = tmp_path / "2026.duckdb"
    with duckdb.connect(str(db_path)) as conn:
        conn.execute("""
            CREATE TABLE pitches (
                game_pk BIGINT, at_bat_number BIGINT, pitch_number BIGINT, game_type VARCHAR,
                home_win_exp DOUBLE, post_home_score INTEGER, post_away_score INTEGER
            )
        """)
        conn.executemany("INSERT INTO pitches VALUES (?, ?, ?, ?, ?, ?, ?)", [
            (1, 1, 1, "R", 0.50, 0, 0),
            (1, 1, 2, "R", 0.70, 0, 0),
            (1, 2, 1, "R", 0.42, 0, 0),
            (1, 2, 2, "R", 0.60, 1, 0),
        ])
    monkeypatch.setattr(wpa_service, "get_season_duckdb_path", lambda *_: db_path)
    wpa_service._cached_plate_appearance_wpa.cache_clear()

    result = wpa_service.load_plate_appearance_wpa(2026, tmp_path)

    assert result.loc[result["at_bat_number"].eq(1), "pa_home_wpa"].iloc[0] == pytest.approx(-0.08)
    assert result.loc[result["at_bat_number"].eq(2), "pa_home_wpa"].iloc[0] == pytest.approx(0.58)


def test_attach_wpa_sets_opposite_pitcher_and_batter_values(monkeypatch, tmp_path):
    monkeypatch.setattr(
        wpa_service,
        "load_plate_appearance_wpa",
        lambda *_: pd.DataFrame([{"game_pk": 1, "at_bat_number": 7, "pa_home_wpa": 0.12}]),
    )
    pitches = pd.DataFrame([{
        "game_pk": 1, "at_bat_number": 7, "inning_topbot": "Top",
        "home_team": "HME", "away_team": "AWY",
    }])

    result = wpa_service.attach_plate_appearance_wpa(pitches, 2026, tmp_path)

    assert result.iloc[0]["pitcher_wpa"] == pytest.approx(0.1123296)
    assert result.iloc[0]["batter_wpa"] == pytest.approx(-0.1123296)


def test_one_wpa_value_per_pa_prevents_pitch_level_duplication():
    frame = pd.DataFrame([
        {"game_pk": 1, "at_bat_number": 2, "pitcher_wpa": 0.2},
        {"game_pk": 1, "at_bat_number": 2, "pitcher_wpa": 0.2},
        {"game_pk": 1, "at_bat_number": 3, "pitcher_wpa": -0.1},
    ])

    assert wpa_service.one_wpa_value_per_pa(frame, "pitcher_wpa").sum() == 0.1
