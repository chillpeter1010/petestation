import duckdb
import pandas as pd
import pytest

from app.services import pitch_matchup_service as service


def row(**changes):
    return dict(pitcher=1, batter=2, game_pk=7, at_bat_number=1, pitch_number=1, balls=0, strikes=1,
                stand="R", p_throws="L", pitch_type="FF", pitch_name="4-Seam", description="swinging_strike", events="",
                release_speed=95, zone=5, plate_x=0, plate_z=2.5, sz_bot=1.5, sz_top=3.5,
                launch_speed=None, woba_value=None, woba_denom=None) | changes


def aggregate(rows, **changes):
    options = dict(year=2026, pitcher_id=1, batter_id=2, batter_side="R", pitcher_hand="L", balls=0, strikes=1)
    return service.aggregate_matchup(pd.DataFrame(rows), **(options | changes))


def test_two_sides_are_season_splits_not_head_to_head_and_mix_denominators():
    rows = [row(), row(at_bat_number=2, pitch_type="SL", pitch_name="Slider", description="foul"),
            row(at_bat_number=3, batter=3, description="called_strike"),
            row(at_bat_number=4, pitcher=9, description="hit_into_play", events="single", launch_speed=100, woba_value=.9, woba_denom=1),
            row(at_bat_number=5, stand="L", p_throws="R"), row(at_bat_number=6, balls=1)]
    result = aggregate(rows)
    assert result["pitcher"]["summary"]["pitches"] == 3
    assert result["batter"]["summary"]["pitches"] == 3
    assert result["pitcher"]["summary"]["whiff_pct"] == 50
    assert result["batter"]["summary"]["avg"] == 1
    assert result["batter"]["summary"]["hard_hit_pct"] == 100
    assert result["batter"]["summary"]["woba"] == pytest.approx(.9)
    assert sum(p["usage_pct"] for p in result["pitcher"]["pitches"]) == pytest.approx(100)
    assert result["pitcher"]["summary"]["denominators"]["swings"] == 2


def test_pa_terminal_chosen_before_count_filter_and_duplicate_outcomes_not_repeated():
    result = aggregate([row(events="single", description="hit_into_play", launch_speed=99, woba_value=.9, woba_denom=1),
                        row(pitch_number=2, balls=1, events="single", description="hit_into_play", launch_speed=100, woba_value=.9, woba_denom=1)])
    assert result["batter"]["summary"]["pitches"] == 1
    assert result["batter"]["summary"]["avg"] is None
    assert result["batter"]["summary"]["hard_hit_pct"] is None


def test_missing_values_and_unknown_hands_do_not_become_zero_rates():
    result = aggregate([row(description="ball", release_speed=None)])
    summary = result["batter"]["summary"]
    assert summary["swing_pct"] == 0
    assert summary["contact_pct"] is None and summary["whiff_pct"] is None
    assert summary["velocity"] is None and summary["woba"] is None
    assert aggregate([row()], batter_side="unknown")["pitcher"]["status"] == "unknown_hand"
    assert aggregate([row()], pitcher_hand="unknown")["batter"]["status"] == "unknown_hand"
    assert aggregate([])["batter"]["status"] == "no_data"


def test_name_lookup_rejects_id_placeholders_and_uses_local_names(tmp_path, monkeypatch):
    path = tmp_path / "season.duckdb"
    with duckdb.connect(str(path)) as conn:
        conn.execute("CREATE TABLE player_master(player_id BIGINT,player_name VARCHAR)")
        conn.execute("INSERT INTO player_master VALUES (1,'Pitcher 1'),(2,'Smith, John')")
        conn.execute("CREATE TABLE game_player_lookup(player_id BIGINT,player_name VARCHAR)")
        conn.execute("INSERT INTO game_player_lookup VALUES (1,'Real Pitcher'),(2,'Batter 2')")
    monkeypatch.setattr(service, "get_season_duckdb_path", lambda *args: path)
    assert service.resolve_replay_names(2026, (1, 2)) == {1:"Real Pitcher",2:"John Smith"}


def test_outcome_missing_tracking_and_non_ab_preserved():
    result = aggregate([row(description="ball", events="walk", woba_value=.69, woba_denom=1),
                        row(at_bat_number=2, description="hit_into_play", events="field_out", launch_speed=None)])
    summary = result["batter"]["summary"]
    assert summary["avg"] == 0 and summary["denominators"]["ab"] == 1
    assert summary["woba"] == .69
    assert summary["hard_hit_pct"] is None and summary["denominators"]["tracked_bbe"] == 0


def test_nonfinite_tracking_does_not_leak_invalid_json_numbers():
    result = aggregate([row(events="single",description="hit_into_play",launch_speed=float("inf"),woba_value=float("inf"),woba_denom=1,release_speed=float("inf"))])
    summary=result["batter"]["summary"]
    assert summary["velocity"] is None and summary["woba"] is None and summary["hard_hit_pct"] is None
