import duckdb
import pandas as pd

from scripts import build_decision_preparation as preparation


def test_ability_asof_excludes_same_time_and_future_and_preserves_switch_hitter(tmp_path, monkeypatch):
    monkeypatch.setattr(preparation, "OUT", tmp_path)
    conn = duckdb.connect()
    features = pd.DataFrame([
        {"year": 2024, "game_pk": 1, "decision_id": f"d{t}", "decision_at": t,
         "outgoing_pitcher_id": 10, "batter_id": 20, "role": "SP"}
        for t in (100.0, 101.0, 102.0)
    ])
    conn.register("input_features", features)
    conn.execute("CREATE TABLE decision_features AS SELECT * FROM input_features")
    monkeypatch.setattr(preparation, "connect", lambda year: conn)
    hands = pd.DataFrame([
        {"game_pk": 1, "player_id": 10, "listed_throws": "L", "listed_bats": "L"},
        {"game_pk": 1, "player_id": 20, "listed_throws": "R", "listed_bats": "S"},
    ])
    hands.to_parquet(tmp_path / "listed_hands_2024.parquet", index=False)
    history = []
    for actor, player_id, role, splits in (("pitcher", 10, "SP", ("All", "R")), ("batter", 20, "BAT", ("All", "L"))):
        for split in splits:
            for time, pa_n, k_n, hr_n in ((100.0, 1, 1, 0), (101.0, 2, 1, 1), (200.0, 3, 1, 2)):
                row = {"actor": actor, "player_id": player_id, "role": role, "split": split,
                       "available_at": time, "pa_n": pa_n,
                       **{f"{key}_n": 0 for key in preparation.OUTCOMES}}
                row.update(k_n=k_n, hr_n=hr_n)
                history.append(row)
    pd.DataFrame(history).to_parquet(tmp_path / "ability_history.parquet", index=False)
    references = pd.DataFrame([{
        "actor": actor, "role": role, "split": "All", "fold_id": "fixture", "train_cutoff": 50.,
        "latest_label_at": 49., "pa_n": 1, **{f"{key}_n": int(key == "other_out") for key in preparation.OUTCOMES},
    } for actor, role in (("pitcher", "SP"), ("batter", "BAT"))])
    references.to_parquet(tmp_path / "ability_references.parquet", index=False)
    monkeypatch.setattr(preparation, "FOLDS", [{"id": "fixture", "score_start": "1970-01-01", "score_end": "2025-01-01"}])
    preparation.ability_features(2024)
    result = pd.read_parquet(tmp_path / "player_ability_features_2024.parquet")
    for actor in ("pitcher", "batter"):
        rows = result[result.actor.eq(actor)].sort_values("decision_at")
        assert rows.own_all_n.tolist() == [0, 1, 2]
        assert rows.ability_status.tolist() == ["frozen_reference", "own_split", "own_split"]
        assert rows.k_rate.tolist() == [0, 1, .5]
        assert (rows.history_available_at < rows.decision_at).all()
    identity = pd.read_parquet(tmp_path / "decision_matchup_2024.parquet")
    assert identity.expected_stand.tolist() == ["R", "R", "R"]
    assert identity.listed_bats.tolist() == ["S", "S", "S"]


def test_boundary_cleaning_uses_predecision_runner_event_and_flags_intent_walk(tmp_path, monkeypatch):
    monkeypatch.setattr(preparation, "OUT", tmp_path)
    conn = duckdb.connect()
    frames = {
        "decision_features": [{"year": 2024, "game_pk": 1, "decision_id": "d1", "role": "SP", "decision_at": 100.,
                               "inning": 1, "half": "top", "outs": 1, "base_state": 0}],
        "decisions": [{"game_pk": 1, "decision_id": "d1", "at_bat_number": 1, "event_index": 1,
                       "outcome_key": "p1", "inning": 1, "half": "top", "outs": 1, "base_state": 0,
                       "home_score": 0, "away_score": 0}],
        "events": [
            {"game_pk": 1, "at_bat_number": 1, "event_index": 0, "event_id": "e0", "event_type": "pickoff_caught_stealing_2b",
             "home_score_after": 0, "away_score_after": 0, "outs_before": 0, "base_state_before": 1},
            {"game_pk": 1, "at_bat_number": 1, "event_index": 1, "event_id": "e1", "event_type": "intent_walk",
             "home_score_after": 0, "away_score_after": 0, "outs_before": 1, "base_state_before": 0},
        ],
        "plays": [
            {"game_pk": 1, "at_bat_number": 1, "outcome_key": "p1", "inning": 1, "half": "top", "scheduled_innings": 9,
             "outs_before": 0, "base_state_before": 1, "home_score_before": 0, "away_score_before": 0,
             "home_score_after": 0, "away_score_after": 0, "outs_after": 1, "base_state_after": 1,
             "zero_pitch": True, "event_type": "intent_walk", "is_complete": True, "mid_pa_change": False,
             "runner_index_missing": False, "end_time": "1970-01-01T00:02:00Z"},
            {"game_pk": 1, "at_bat_number": 2, "outcome_key": "p2", "inning": 1, "half": "top", "scheduled_innings": 9,
             "outs_before": 1, "base_state_before": 1, "home_score_before": 0, "away_score_before": 0,
             "home_score_after": 0, "away_score_after": 0, "outs_after": 3, "base_state_after": 0,
             "zero_pitch": False, "event_type": "double_play", "is_complete": True, "mid_pa_change": False,
             "runner_index_missing": False, "end_time": "1970-01-01T00:03:00Z"},
        ],
        "decision_labels": [{"decision_id": "d1", "observed_action": "continue", "incoming_pitcher_id": 10,
                             "next_pa_defense_wpa": .2, "next_pa_source_defense_re24": .5, "half_defense_wpa": .3}],
        "context_features": [{"decision_id": "d1", "research_home_we": None, "research_re": None, "context_model_id": None}],
    }
    for name, rows in frames.items():
        conn.register("frame", pd.DataFrame(rows))
        conn.execute(f"CREATE TABLE {name} AS SELECT * FROM frame")
    monkeypatch.setattr(preparation, "connect", lambda year: conn)
    preparation.clean_labels(2024)
    result = pd.read_parquet(tmp_path / "clean_labels_2024.parquet").iloc[0]
    assert result.review_reason == "predecision_runner_event"
    assert result.changed_start and result.transition_valid and result.half_valid
    assert not result.organic_pa_eligible
    assert pd.isna(result.comparable_source_pa_wpa)
    assert result.runs_to_pa_end == 0
    assert result.outs == 1


def test_signal_adapter_excludes_current_pitch_and_carries_original_intervals(tmp_path, monkeypatch):
    monkeypatch.setattr(preparation, "OUT", tmp_path)
    conn = duckdb.connect()
    time = 1700000100.
    frame = pd.DataFrame([{
        "year": 2024, "game_pk": 1, "decision_id": "d1", "role": "SP", "decision_at": time,
        "current_pitches": 40, "appearance_id": "a1", "outgoing_pitcher_id": 10,
        "quality_plus": 95., "physical_plus": 98., "command_plus": 101., "prefix_status": "three_signals_available",
    }])
    conn.register("frame", frame)
    conn.execute("CREATE TABLE decision_features AS SELECT * FROM frame")
    state = {"decision_id": "d1", "reliability": .4, "prefix_pitches": 40,
             "state_observed_at": time-1, "state_model_id": "state_fixture", "state_train_cutoff": time-1000}
    for signal, value in (("quality", 95.), ("physical", 98.), ("command", 101.)):
        state[f"{signal}_low"] = value-3
        state[f"{signal}_high"] = value+3
    conn.register("frame", pd.DataFrame([state]))
    conn.execute("CREATE TABLE decision_states AS SELECT * FROM frame")
    pitches = [{
        "appearance_id": "a1", "pitcher_id": 10, "plus_model_id": "plus_fixture", "plus_train_cutoff": time-1000,
        "observed_at": observed, "research_stuff_plus": value, "research_location_plus": value+1,
        "source_valid": True, "alignment_status": "validated_order", "roster_pitcher": True,
        "source_batter_consistent": True,
    } for observed, value in ((time-10, 80.), (time, 999.), (time+10, 2000.))]
    conn.register("frame", pd.DataFrame(pitches))
    conn.execute("CREATE TABLE pitch_features AS SELECT * FROM frame")
    monkeypatch.setattr(preparation, "connect", lambda year: conn)
    preparation.signal_features(2024)
    row = pd.read_parquet(tmp_path / "signal_features_2024.parquet").iloc[0]
    assert row.stuff_n == row.location_n == 1
    assert row.prior_prefix_stuff == 80.
    assert row.prior_prefix_location == 81.
    assert row.quality_low == 92.
    assert row.quality_high == 98.
    assert row.reliability == .4
