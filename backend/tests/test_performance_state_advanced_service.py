from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from app.api.schemas.performance_state import (
    PerformanceStateLeaderboardResponse,
    PerformanceStateOverviewResponse,
    PerformanceStateShadowResponse,
    PitcherPerformanceStatesResponse,
)
from app.services import performance_state_advanced_service as advanced
from app.services import performance_state_forecast_service as forecast
from app.services.performance_state_service import (
    filtered_state_path,
    get_performance_state_overview,
    get_pitcher_performance_states,
)


def _volatility_rows() -> pd.DataFrame:
    return pd.DataFrame({
        "pitcher_id": [1, 1, 1, 2, 2],
        "role": ["SP"] * 5,
        "calendar_days_since_prior": [np.nan, 5.0, 5.0, np.nan, 80.0],
        advanced.VOLATILITY_SIGNAL: [0.5, -1.0, 0.25, 0.3, -0.4],
    })


def test_gas_forecast_is_causal_and_long_gap_resets():
    rows = _volatility_rows()
    parameters = np.array([0.2, 0.15, 0.9, 8.0])
    original = advanced._gas_forecasts(rows, parameters)
    changed = rows.copy()
    changed.loc[len(changed) - 1, advanced.VOLATILITY_SIGNAL] = -20.0
    revised = advanced._gas_forecasts(changed, parameters)
    np.testing.assert_allclose(original, revised)
    assert original[0] == original[3] == original[4]


def test_long_gap_transition_returns_stationary_prior():
    transition = np.array([[0.90, 0.10], [0.25, 0.75]])
    powered = advanced._gap_transition(transition, 180.0, 5.0)
    np.testing.assert_allclose(powered[0], powered[1])
    np.testing.assert_allclose(powered.sum(axis=1), np.ones(2))


def test_caviar_missing_shock_does_not_poison_future_forecasts():
    rows = _volatility_rows()
    rows.loc[1, advanced.VOLATILITY_SIGNAL] = np.nan
    forecasts = advanced._caviar_forecasts(
        rows,
        np.array([0.10, 0.80, 0.20]),
        "sav",
        initial_quantile=1.5,
    )
    assert np.isfinite(forecasts).all()
    assert forecasts[2] == forecasts[1]


def test_real_slice4_6_artifacts_and_api_schemas():
    root = Path(__file__).resolve().parents[2] / "data"
    audit = advanced.get_performance_state_advanced_audit(root)
    assert audit["dataset_status"] == "current"
    assert audit["slice4"]["roles"]["SP"]["selected_states"] in range(2, 6)
    assert audit["slice6"]["roles"]["SP"]["converged"] is True

    overview = PerformanceStateOverviewResponse(**get_performance_state_overview(root))
    assert overview.advanced_model_version == advanced.ADVANCED_MODEL_VERSION
    assert overview.slice4 and overview.slice5 and overview.slice6

    path = advanced.advanced_state_path(2026, root)
    with duckdb.connect() as connection:
        count, unique_count, pitcher_id = connection.execute(
            "SELECT count(*), count(DISTINCT (pitcher_id, role, game_pk)), min(pitcher_id) "
            "FROM read_parquet(?)",
            [str(path)],
        ).fetchone()
    assert count == unique_count
    player = PitcherPerformanceStatesResponse(
        **get_pitcher_performance_states(2026, int(pitcher_id), data_dir=root)
    )
    assert player.rows
    assert player.rows[0].gas_variance_forecast is not None


def test_real_slice7_artifacts_and_player_tail_fields():
    root = Path(__file__).resolve().parents[2] / "data"
    audit = advanced.get_performance_state_tail_audit(root)
    assert audit["dataset_status"] == "current"
    assert audit["roles"]["SP"]["development_clusters"] >= 100
    assert audit["roles"]["RP"]["selected_caviar"] in {"sav", "asymmetric_slope"}

    path = advanced.tail_state_path(2026, root)
    with duckdb.connect() as connection:
        count, unique_count, pitcher_id = connection.execute(
            "SELECT count(*), count(DISTINCT (pitcher_id, role, game_pk)), min(pitcher_id) "
            "FROM read_parquet(?)",
            [str(path)],
        ).fetchone()
    assert count == unique_count
    player = PitcherPerformanceStatesResponse(
        **get_pitcher_performance_states(2026, int(pitcher_id), data_dir=root)
    )
    assert player.rows
    assert player.rows[0].evt_extreme_probability is not None


def test_slice8_feature_contract_is_pregame_and_role_specific():
    features = [
        feature
        for layer in forecast.FEATURE_LAYERS.values()
        for feature in layer
    ]
    assert not any("filtered" in feature for feature in features)
    assert not any("innovation" in feature for feature in features)
    assert "regime_prior_collapse" in features
    assert "gas_har_variance_forecast" in features

    rows = pd.DataFrame({
        "role": ["SP", "SP", "RP"],
        "lag_process_collapse": [False, True, True],
        "return_to_baseline": [False, True, True],
        "game_date": pd.to_datetime(["2025-04-01", "2025-04-02", "2025-04-03"]),
        "game_pk": [1, 2, 3],
        "pitcher_id": [1, 1, 1],
    })
    eligible = forecast._eligible_rows(rows, "SP", "return_to_baseline")
    assert eligible["game_pk"].tolist() == [2]


def test_real_slice8_9_artifacts_and_api_schemas():
    root = Path(__file__).resolve().parents[2] / "data"
    audit = forecast.get_performance_state_forecast_audit(root)
    assert audit["dataset_status"] == "current"
    assert audit["slice8"]["roles"]["SP"]["process_collapse"]["selected_primary_layer"]
    assert audit["slice9"]["roles"]["RP"]["return_to_baseline"]["external_rows"] > 0
    assert audit["freeze_audit"]["test_year_used_for_selection_or_calibration"] is False
    assert audit["slice9"]["roles"]["RP"]["return_to_baseline"]["excess_recovery_diagnostic"]
    assert audit["prospective_release_decision"] == "keep_research_only"

    path = forecast.forecast_state_path(2026, root)
    with duckdb.connect() as connection:
        count, unique_count, pitcher_id = connection.execute(
            "SELECT count(*), count(DISTINCT (pitcher_id, role, game_pk)), min(pitcher_id) "
            "FROM read_parquet(?)",
            [str(path)],
        ).fetchone()
    assert count == unique_count
    player = PitcherPerformanceStatesResponse(
        **get_pitcher_performance_states(2026, int(pitcher_id), data_dir=root)
    )
    assert player.rows
    assert player.rows[0].process_collapse_probability is not None
    assert player.rows[0].wpa is not None
    assert player.rows[0].re24 is not None

    overview = PerformanceStateOverviewResponse(**get_performance_state_overview(root))
    assert overview.forecast_model_version == forecast.FORECAST_MODEL_VERSION
    assert overview.slice8 and overview.slice9

    leaderboard = PerformanceStateLeaderboardResponse(
        **forecast.get_performance_state_leaderboard(
            year=2026,
            role="SP",
            target="process_collapse",
            minimum_forecasts=5,
            data_dir=root,
        )
    )
    assert leaderboard.rows
    assert leaderboard.rows[0].latest_probability >= leaderboard.rows[-1].latest_probability
    assert leaderboard.validation["release_gate"]["passed"] is True


def test_slice11_shadow_ledger_preserves_frozen_probabilities(tmp_path):
    root = tmp_path
    derived = root / "derived"
    derived.mkdir()
    forecasts = pd.DataFrame({
        "year": [2026], "pitcher_id": [1], "role": ["SP"], "game_pk": [10],
        "game_date": pd.to_datetime(["2026-04-01"]),
        "process_collapse_probability": [0.25], "process_collapse_alert": [True],
        "result_collapse_probability": [np.nan], "result_collapse_alert": [False],
        "return_to_baseline_probability": [np.nan], "return_to_baseline_alert": [False],
        "strong_rebound_probability": [np.nan], "strong_rebound_alert": [False],
    })
    states = pd.DataFrame({
        "year": [2026], "pitcher_id": [1], "role": ["SP"], "game_pk": [10],
        "game_date": pd.to_datetime(["2026-04-01"]), "pitcher_name": ["Test Pitcher"],
        "team": ["TST"], "process_collapse": [True], "result_collapse": [False],
        "return_to_baseline": [False], "strong_rebound": [False],
    })
    forecast._write_parquet_atomic(forecasts, forecast.forecast_state_path(2026, root))
    forecast._write_parquet_atomic(states, filtered_state_path(2026, root))
    first = forecast.refresh_performance_state_shadow(root, 2026)
    assert first["ledger_rows"] == 1
    assert first["observation_mode"] == "historical_backfill"

    forecasts["process_collapse_probability"] = 0.75
    forecast._write_parquet_atomic(forecasts, forecast.forecast_state_path(2026, root))
    second = forecast.refresh_performance_state_shadow(root, 2026)
    assert second["appended_rows"] == 0
    assert second["probability_conflicts_preserved"] == 1
    with duckdb.connect() as connection:
        frozen = connection.execute(
            "SELECT probability FROM read_parquet(?)", [str(forecast.shadow_ledger_path(root))]
        ).fetchone()[0]
    assert frozen == 0.25


def test_real_slice11_shadow_artifacts_and_schema():
    root = Path(__file__).resolve().parents[2] / "data"
    audit = PerformanceStateShadowResponse(**forecast.get_performance_state_shadow_audit(root))
    assert audit.ledger_rows == 44384
    assert audit.prospective_rows == 0
    assert audit.integration_gate["eligible"] is False
    path = forecast.shadow_ledger_path(root)
    with duckdb.connect() as connection:
        count, unique_count = connection.execute(
            "SELECT count(*), count(DISTINCT (year, pitcher_id, role, game_pk, target)) FROM read_parquet(?)",
            [str(path)],
        ).fetchone()
    assert count == unique_count
