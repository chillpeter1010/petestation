from __future__ import annotations

import pandas as pd

from app.services.arm_angle_backfill_service import (
    KEY_COLUMNS,
    apply_official_arm_angles,
    get_arm_angle_backfill_contract,
)


def test_arm_angle_backfill_only_fills_exact_null_matches() -> None:
    cached = pd.DataFrame(
        [
            {"game_pk": 1, "at_bat_number": 1, "pitch_number": 1, "pitcher": 10, "batter": 20, "game_date": "2026-01-01", "arm_angle": None, "release_speed": 95.0},
            {"game_pk": 1, "at_bat_number": 1, "pitch_number": 2, "pitcher": 10, "batter": 20, "game_date": "2026-01-01", "arm_angle": 42.0, "release_speed": 96.0},
        ]
    )
    official = cached.copy()
    official["arm_angle"] = [41.5, 99.0]

    updated, patch = apply_official_arm_angles(cached, official)

    assert updated["arm_angle"].tolist() == [41.5, 42.0]
    assert updated["release_speed"].tolist() == cached["release_speed"].tolist()
    assert len(patch) == 1
    assert patch.iloc[0][KEY_COLUMNS].tolist() == cached.iloc[0][KEY_COLUMNS].tolist()


def test_arm_angle_backfill_contract_preserves_rows_and_uses_official_values() -> None:
    contract = get_arm_angle_backfill_contract()
    assert contract["status"] == "ready"
    assert contract["patched_rows"] == 184_493
    assert contract["before"]["pitches"] == contract["after"]["pitches"] == 716_544
    assert contract["before"]["coverage_pct"] == 73.58
    assert contract["after"]["coverage_pct"] > 99.0
    assert contract["rules"]["non_synthetic"].startswith("Release coordinates were not used")
