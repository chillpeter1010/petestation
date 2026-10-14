from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from app.api.schemas.performance_state import PerformanceStateV2AuditResponse
from app.services import performance_state_v2_service as service


def test_eligibility_separates_position_players_openers_and_bulk_relief() -> None:
    frame = pd.DataFrame({
        "year": [2024] * 4,
        "pitcher_id": [1, 2, 3, 4],
        "game_pk": [11, 12, 13, 14],
        "role": ["RP", "SP", "SP", "RP"],
        "pitches": [12, 32, 88, 52],
        "plate_appearances": [3, 8, 24, 14],
        "stuff_pitches": [12, 32, 88, 52],
        "location_pitches": [12, 32, 88, 52],
    })
    result = service._add_eligibility(frame, {1}, {1: 100})
    assert result.set_index("pitcher_id").loc[1, "eligibility_exclusion"] == "position_player_pitching"
    assert result.set_index("pitcher_id").loc[2, "appearance_type"] == "opener_like"
    assert result.set_index("pitcher_id").loc[3, "appearance_type"] == "traditional_starter"
    assert result.set_index("pitcher_id").loc[4, "appearance_type"] == "bulk_reliever"


def test_fold_targets_split_onset_from_persistence() -> None:
    frame = pd.DataFrame({
        "lag_process_collapse": [False, True, True, False],
        "onset_process_collapse": [True, False, False, False],
        "persistent_process_collapse": [False, True, False, False],
    })
    onset = service._target_rows(frame, "onset_process_collapse")
    persistent = service._target_rows(frame, "persistent_process_collapse")
    assert len(onset) == 2
    assert len(persistent) == 2
    assert not onset["lag_process_collapse"].any()
    assert persistent["lag_process_collapse"].all()


def test_real_multiseason_artifacts_are_unique_and_temporal() -> None:
    root = Path(__file__).resolve().parents[2] / "data"
    audit = service.get_performance_state_v2_audit(root)
    PerformanceStateV2AuditResponse(**audit)
    assert audit["dataset_status"] in {"current", "stale"}
    if audit["dataset_status"] == "stale":
        assert any(
            warning.startswith("Source datasets changed after build for:")
            for warning in audit["slice13"]["warnings"]
        )
    assert audit["slice12"]["v1_artifacts_overwritten"] is False
    assert [fold["test_year"] for fold in audit["slice13"]["folds"]] == [2024, 2025, 2026]
    for fold in audit["slice13"]["folds"]:
        assert max(fold["train_years"]) < fold["test_year"]
    for year in service.YEARS:
        path = service.v2_warehouse_path(year, root)
        with duckdb.connect() as connection:
            count, unique_count = connection.execute(
                "SELECT count(*), count(DISTINCT (pitcher_id, role, game_pk)) FROM read_parquet(?)",
                [str(path)],
            ).fetchone()
        assert count == unique_count
        assert count == audit["slice12"]["coverage"][str(year)]["rows"]


def test_real_fold_predictions_keep_targets_and_cohorts_separate() -> None:
    root = Path(__file__).resolve().parents[2] / "data"
    for year in (2024, 2025, 2026):
        path = service.v2_fold_predictions_path(year, root)
        with duckdb.connect() as connection:
            targets, cohorts, years = connection.execute(
                "SELECT count(DISTINCT target), count(DISTINCT cohort), list(DISTINCT year) FROM read_parquet(?)",
                [str(path)],
            ).fetchone()
        assert targets == len(service.TARGETS)
        assert cohorts == 2
        assert years == [year]
