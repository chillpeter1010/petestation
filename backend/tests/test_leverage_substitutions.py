import pandas as pd
import pytest

from app.services.leverage_lab_service import _pitching_moves, _team_pitching_rows


def test_entry_buckets_use_first_li_exact_edges_and_complete_stint_values():
    pa = pd.DataFrame([
        (1, "SDP", 10, 1001, .4, .10, 1.0),
        (1, "SDP", 20, 2001, 1.0, .10, .50),
        (1, "SDP", 20, 3001, 3.0, .20, .25),
        (1, "SDP", 30, 4001, 2.0, -.10, -.25),
        (1, "SDP", 20, 5001, 2.1, .05, .15),
        (1, "SDP", 40, 6001, .9, None, None),
        (1, "NYY", 50, 7001, .3, .40, 2.0),
    ], columns=["game_pk", "pitcher_team", "pitcher", "pa_seq", "entry_li", "pa_wpa", "complete_pa_re24"])

    moves = _pitching_moves(pa)
    assert moves["pitcher"].tolist() == [20, 30, 20, 40]
    [team] = _team_pitching_rows(moves)
    assert team["team"] == "SD"
    assert team["moves"] == 4
    assert team["wpa_n"] == team["re24_n"] == 3
    assert team["wpa"] == pytest.approx(.25)
    assert team["re24"] == pytest.approx(.65)
    assert team["entry_wpa_low"] is None
    assert team["entry_wpa_low_moves"] == 1
    assert team["entry_wpa_mid"] == pytest.approx(.20)
    assert team["entry_wpa_mid_moves"] == 2
    assert team["entry_wpa_high"] == pytest.approx(.05)
