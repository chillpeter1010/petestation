from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from app.api.schemas.performance_state import (
    PerformanceStateOverviewResponse,
    PitcherPerformanceStatesResponse,
)
from app.services import performance_state_service as service


def _label_rows() -> pd.DataFrame:
    rows = []
    for year in (2025, 2026):
        for role in ("SP", "RP"):
            for pitcher_id in (1, 2):
                for appearance in range(1, 7):
                    value = float(appearance - 3) + (0.2 if pitcher_id == 2 else 0.0)
                    rows.append({
                        "year": year,
                        "pitcher_id": pitcher_id,
                        "role": role,
                        "game_pk": year * 1000 + pitcher_id * 100 + appearance + (0 if role == "SP" else 50),
                        "game_date": pd.Timestamp(year, 3, appearance + pitcher_id),
                        "mean_stuff_plus": 100 + value,
                        "mean_location_plus": 100 + value / 2,
                        "first10_stuff_plus": 100 + value,
                        "first10_location_plus": 100 + value / 2,
                        "first20_stuff_plus": 100 + value,
                        "first20_location_plus": 100 + value / 2,
                        "re24_per_pa": value / 10,
                        "wpa_li_per_pa": value / 100,
                        "game_score_proxy": 50 + value if role == "SP" else np.nan,
                    })
    return pd.DataFrame(rows)


def test_labels_keep_role_histories_separate_and_features_are_lagged():
    frame, _, _ = service._add_labels_and_history(_label_rows(), 2025)
    ordered = frame.sort_values(["pitcher_id", "role", "game_date", "game_pk"])
    first_rows = ordered.groupby(["pitcher_id", "role"]).head(1)
    assert first_rows["lag_process_score"].isna().all()
    assert first_rows["process_ma5"].isna().all()
    second_rows = ordered.groupby(["pitcher_id", "role"]).nth(1)
    assert second_rows["lag_process_score"].notna().all()
    assert set(frame["role"]) == {"SP", "RP"}


def test_state_filter_is_causal_with_respect_to_future_observations():
    base = np.array([0.2, -0.1, 0.3, 0.0], dtype=float)
    changed = base.copy()
    changed[-1] = -10.0
    args = (np.full(4, 80.0), np.full(4, 4.0), 0.85, 0.10, 0.50, 80.0)
    first = service._filter_sequence(base, *args)
    second = service._filter_sequence(changed, *args)
    np.testing.assert_allclose(first[0][:-1], second[0][:-1])
    np.testing.assert_allclose(first[2][:-1], second[2][:-1])


def test_calendar_gap_decays_prior_state_and_long_gap_can_reset():
    observations = np.array([1.0, 0.0], dtype=float)
    pitches = np.full(2, 80.0)
    elapsed_days = np.array([np.nan, 180.0])
    fixed = service._filter_sequence(
        observations, pitches, elapsed_days, 0.95, 0.03, 0.50, 80.0, "fixed_appearance_with_60d_reset"
    )
    calendar = service._filter_sequence(
        observations, pitches, elapsed_days, 0.95, 0.03, 0.50, 80.0, "calendar_decay"
    )
    reset = service._filter_sequence(
        observations, pitches, elapsed_days, 0.95, 0.03, 0.50, 80.0, "calendar_decay_with_60d_reset"
    )
    assert fixed[0][1] == 0.0
    assert abs(calendar[0][1]) < 0.20
    assert reset[0][1] == 0.0


def test_calendar_gap_is_derived_across_seasons_without_rest_fill():
    frame, _, _ = service._add_labels_and_history(_label_rows(), 2025)
    first_2026 = (
        frame[frame["year"].eq(2026)]
        .sort_values(["pitcher_id", "role", "game_date", "game_pk"])
        .groupby(["pitcher_id", "role"])
        .head(1)
    )
    assert first_2026["calendar_days_since_prior"].gt(300).all()


def test_real_slice0_3_artifacts_match_api_schemas():
    root = Path(__file__).resolve().parents[2] / "data"
    overview = PerformanceStateOverviewResponse(**service.get_performance_state_overview(root))
    assert overview.status == "research_only"
    assert overview.development_year == 2025
    assert overview.test_year == 2026
    assert overview.slice3["version"] == service.STATE_MODEL_VERSION
    assert overview.slice3a["version"] == "performance_state_slice3a_protocol_repair_v1"

    state_path = service.filtered_state_path(2026, root)
    with duckdb.connect() as connection:
        pitcher_id = connection.execute(
            "SELECT pitcher_id FROM read_parquet(?) ORDER BY pitcher_id LIMIT 1", [str(state_path)]
        ).fetchone()[0]
    player = PitcherPerformanceStatesResponse(
        **service.get_pitcher_performance_states(2026, int(pitcher_id), data_dir=root)
    )
    assert player.rows
    assert set(player.roles).issubset({"SP", "RP"})
