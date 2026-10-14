from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from app.api.schemas.performance_state import PerformanceStateV2Slice14AuditResponse
from app.services import performance_state_v2_slice14_service as service


def test_calibration_and_cluster_bootstrap_are_pitcher_aware() -> None:
    rows = pd.DataFrame({
        "pitcher_id": np.repeat(np.arange(20), 5),
        "actual": np.tile([0, 0, 0, 0, 1], 20),
    })
    probabilities = np.tile([0.05, 0.10, 0.15, 0.20, 0.80], 20)
    calibration = service._calibration(rows["actual"].to_numpy(), probabilities)
    bootstrap = service._cluster_bootstrap(rows, probabilities, 0.20, samples=20)
    assert calibration["slope"] is not None
    assert bootstrap["successful_samples"] == 20
    assert bootstrap["average_precision_delta_95_interval"][0] > 0
    assert bootstrap["brier_delta_95_interval"][1] < 0


def test_slice14_artifacts_are_independent_and_unique_when_built() -> None:
    root = Path(__file__).resolve().parents[2] / "data"
    path = service.slice14_audit_path(root)
    if not path.exists():
        return
    audit = service.get_performance_state_v2_slice14_audit(root)
    PerformanceStateV2Slice14AuditResponse(**audit)
    assert audit["dataset_status"] == "current"
    assert audit["slice14b"]["training_years"] == [2023, 2024, 2025]
    assert audit["slice14b"]["diagnostic_year"] == 2026
    assert audit["slice14b"]["prospective_untouched_year"] == 2027
    with duckdb.connect() as connection:
        rows, unique_rows = connection.execute(
            "SELECT count(*), count(DISTINCT (pitcher_id, role, game_pk, target)) FROM read_parquet(?)",
            [str(service.slice14_prediction_path(root))],
        ).fetchone()
    assert rows == unique_rows
    assert rows == audit["prediction_rows"]
