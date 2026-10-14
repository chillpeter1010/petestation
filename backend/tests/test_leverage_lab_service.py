import pandas as pd
import pytest

from app.api.schemas.leverage import LeverageScenarioRequest, LeverageStateInput
from app.services import leverage_lab_service


def _state(*, inning, score_diff, outs, base_state, win_expectancy, li, samples=100):
    return {
        "inning": inning,
        "inning_topbot": "Top",
        "score_diff": score_diff,
        "outs": outs,
        "base_state": base_state,
        "win_expectancy": win_expectancy,
        "li": li,
        "samples": samples,
    }


def test_calculate_scenario_returns_endpoint_metrics_and_sd_md(monkeypatch):
    bundle = {
        "states": pd.DataFrame([
            _state(inning=8, score_diff=0, outs=1, base_state=1, win_expectancy=0.50, li=2.4),
            _state(inning=9, score_diff=-1, outs=2, base_state=0, win_expectancy=0.20, li=0.4),
        ]),
        "run_states": pd.DataFrame([
            {"outs": 1, "base_state": 1, "run_expectancy": 0.52},
            {"outs": 2, "base_state": 0, "run_expectancy": 0.10},
        ]),
        "runs_per_win": 10.0,
        "data_as_of": "2026-09-13",
    }
    monkeypatch.setattr(leverage_lab_service, "_bundle", lambda year: bundle)
    request = LeverageScenarioRequest(
        year=2026,
        entry=LeverageStateInput(
            inning=8, half="Top", outs=1, runner_first=True,
            fielding_score=2, opponent_score=2,
        ),
        exit=LeverageStateInput(
            inning=9, half="Top", outs=2,
            fielding_score=2, opponent_score=3,
        ),
    )

    result = leverage_lab_service.calculate_scenario(request)
    metrics = {row["key"]: row["value"] for row in result["metrics"]}

    assert metrics["wpa"] == pytest.approx(-0.309)
    assert metrics["re24"] == pytest.approx(-0.58)
    assert metrics["rew"] == pytest.approx(-0.058)
    assert metrics["gmli"] == pytest.approx(2.4)
    assert metrics["exli"] == pytest.approx(0.4)
    assert metrics["result"] == "Meltdown"
    assert metrics["inli"] is None
    assert result["data_as_of"] == "2026-09-13"


def test_calculate_scenario_rejects_score_rollback(monkeypatch):
    monkeypatch.setattr(leverage_lab_service, "_bundle", lambda year: {})
    request = LeverageScenarioRequest(
        year=2026,
        entry=LeverageStateInput(inning=8, half="Top", outs=0, fielding_score=1, opponent_score=3),
        exit=LeverageStateInput(inning=9, half="Top", outs=0, fielding_score=1, opponent_score=2),
    )

    with pytest.raises(ValueError, match="cannot be lower"):
        leverage_lab_service.calculate_scenario(request)


def test_validation_reports_exact_regression_for_all_supported_metrics():
    metrics = [
        "wpa", "negative_wpa", "positive_wpa", "re24", "pli", "inli", "gmli", "exli", "pulls",
        "wpa_li", "clutch", "shutdowns", "meltdowns",
    ]
    values = [1.0, 2.0, 3.0]
    local = pd.DataFrame({"player_id": [1, 2, 3], **{metric: values for metric in metrics}})
    reference = local.copy()

    result = leverage_lab_service._validation(local, reference)

    assert {row["metric"] for row in result} == set(metrics)
    assert all(row["correlation"] == pytest.approx(1.0) for row in result)
    assert all(row["r_squared"] == pytest.approx(1.0) for row in result)
    assert all(row["mae"] == pytest.approx(0.0) for row in result)
