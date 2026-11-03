from __future__ import annotations

import pandas as pd

from app.services.player_archetype_practical_tag_service import (
    classify_mechanics_tag,
    classify_platoon_strategy,
)


def _mechanics(rows: list[tuple[str, float, int]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["pitch_type", "arm_side_z", "pitch_count"])


def _strategy(rows: list[tuple[str, str, int]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["stand", "pitch_type", "pitch_count"])


def test_pronation_uses_supported_usage_weighted_family_shape():
    tag, status, evidence = classify_mechanics_tag(
        _mechanics([("FF", 0.8, 100), ("SL", 0.2, 50)])
    )

    assert (tag, status) == ("Pronation", "supported")
    assert evidence["pronation_strong_types"] == ["FF"]
    assert evidence["xor_conflict"] is False


def test_supination_uses_the_same_symmetric_family_rule():
    tag, status, evidence = classify_mechanics_tag(
        _mechanics([("SL", -0.9, 90), ("FF", -0.1, 120)])
    )

    assert (tag, status) == ("Supination", "supported")
    assert evidence["supination_strong_types"] == ["SL"]


def test_mechanics_xor_suppresses_conflicting_profiles():
    tag, status, evidence = classify_mechanics_tag(
        _mechanics([("FF", 0.8, 80), ("SI", 0.7, 60), ("SL", -0.8, 80), ("CU", -0.7, 60)])
    )

    assert tag is None
    assert status == "conflict_suppressed"
    assert evidence["xor_conflict"] is True


def test_platoon_strategy_labels_only_supported_side_specific_usage():
    tags, status, evidence = classify_platoon_strategy(
        _strategy([
            ("L", "CH", 35), ("L", "FF", 65),
            ("R", "CH", 5), ("R", "SL", 35), ("R", "FF", 60),
        ])
    )

    assert status == "supported"
    assert tags == ["LHB More Offspeed", "RHB More Breaking Balls"]
    assert evidence["tags"]["LHB More Offspeed"]["gap_pp"] == 30.0


def test_platoon_strategy_rejects_small_opponent_side_sample():
    tags, status, evidence = classify_platoon_strategy(
        _strategy([("L", "CH", 35), ("L", "FF", 65), ("R", "FF", 39)])
    )

    assert tags == []
    assert status == "insufficient"
    assert evidence["R_pitches"] == 39
