from __future__ import annotations

import pandas as pd
import pytest

from app.services.catcher_descriptive_xera_service import (
    _aggregate_outputs,
    _apply_additive_calibration,
    _fit_additive_calibration,
    baseball_ip_to_outs,
)


def test_baseball_ip_is_converted_to_outs_and_invalid_tenths_are_rejected() -> None:
    assert baseball_ip_to_outs("6.1") == 19
    assert baseball_ip_to_outs(12.2) == 38
    assert baseball_ip_to_outs("7") == 21
    with pytest.raises(ValueError, match="Invalid baseball innings"):
        baseball_ip_to_outs("6.3")


def test_additive_calibration_preserves_expected_run_numerator() -> None:
    frame = pd.DataFrame(
        [
            {"season": 2021, "expected_woba_sum": 10.0, "bf": 30, "outs": 27, "official_xera": 4.0},
            {"season": 2022, "expected_woba_sum": 20.0, "bf": 60, "outs": 54, "official_xera": 4.0},
            {"season": 2023, "expected_woba_sum": 15.0, "bf": 45, "outs": 36, "official_xera": 5.0},
        ]
    )
    coefficients = _fit_additive_calibration(frame, ["expected_woba_sum", "bf", "outs"])
    predicted = _apply_additive_calibration(frame, coefficients)

    assert list(coefficients) == ["expected_woba_sum", "bf", "outs"]
    assert predicted.notna().all()
    expected_runs = sum(frame[name] * value for name, value in coefficients.items())
    assert (predicted * frame["outs"] / 27.0).to_numpy() == pytest.approx(expected_runs.to_numpy())


def test_pair_catcher_and_team_outputs_roll_up_the_same_pa_numerator() -> None:
    pa = pd.DataFrame(
        [
            {
                "season": 2025, "pitcher_id": 1, "pitcher_name": "Pitcher A", "current_catcher_id": 10,
                "current_catcher_name": "Catcher A", "pitching_team_id": 100, "pitching_team_abbr": "AAA",
                "game_pk": 1, "outs": 2, "bf": 1, "expected_woba_value": 0.2, "xera_expected_runs": 0.3,
                "fallback_bf": 0,
            },
            {
                "season": 2025, "pitcher_id": 1, "pitcher_name": "Pitcher A", "current_catcher_id": 10,
                "current_catcher_name": "Catcher A", "pitching_team_id": 100, "pitching_team_abbr": "AAA",
                "game_pk": 1, "outs": 1, "bf": 1, "expected_woba_value": 0.0, "xera_expected_runs": 0.1,
                "fallback_bf": 0,
            },
            {
                "season": 2025, "pitcher_id": 2, "pitcher_name": "Pitcher B", "current_catcher_id": 10,
                "current_catcher_name": "Catcher A", "pitching_team_id": 100, "pitching_team_abbr": "AAA",
                "game_pk": 2, "outs": 3, "bf": 1, "expected_woba_value": 0.0, "xera_expected_runs": 0.2,
                "fallback_bf": 0,
            },
        ]
    )
    pitchers = pd.DataFrame(
        [
            {"season": 2025, "pitcher_id": 1, "xera": 3.6},
            {"season": 2025, "pitcher_id": 2, "xera": 1.8},
        ]
    )

    ledger = pd.DataFrame(
        [
            {
                "season": 2025, "pitching_team_id": 100, "pitching_team_abbr": "AAA", "pitcher_id": 1,
                "pitcher_name": "Pitcher A", "catcher_id": 10, "catcher_name": "Catcher A", "games": 1,
                "outs": 3, "bf": 2,
            },
            {
                "season": 2025, "pitching_team_id": 100, "pitching_team_abbr": "AAA", "pitcher_id": 2,
                "pitcher_name": "Pitcher B", "catcher_id": 10, "catcher_name": "Catcher A", "games": 1,
                "outs": 3, "bf": 1,
            },
        ]
    )

    pairs, catchers, teams = _aggregate_outputs(pa, pitchers, ledger)

    assert pairs["outs"].sum() == catchers["outs"].sum() == teams["outs"].sum() == 6
    assert pairs["bf"].sum() == catchers["bf"].sum() == teams["bf"].sum() == 3
    assert pairs["xera_expected_runs"].sum() == pytest.approx(0.6)
    assert catchers.iloc[0]["xera_expected_runs"] == pytest.approx(0.6)
    assert teams.iloc[0]["xera_expected_runs"] == pytest.approx(0.6)
    assert catchers.iloc[0]["cxera"] == pytest.approx(2.7)
    assert catchers.iloc[0]["txera"] == pytest.approx(2.7)
    assert catchers.iloc[0]["x_runs_vs_mix"] == pytest.approx(0.0)
