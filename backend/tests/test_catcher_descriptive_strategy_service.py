from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from app.services.catcher_descriptive_strategy_service import (
    build_catcher_descriptive_slice8_strategy_bridge,
    get_catcher_descriptive_strategy_bridge,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_build_strategy_bridge_preserves_research_only_boundaries(tmp_path: Path) -> None:
    derived = tmp_path / "derived"
    derived.mkdir(parents=True)
    decisions_path = derived / "player_archetype_slice6c_decision_values_2026.parquet"
    diagnostics_path = derived / "player_archetype_slice6d_decision_diagnostics_2026.parquet"
    pd.DataFrame(
        [
            {"decision_id": "a", "catcher_id": 10, "pitcher_id": 100},
            {"decision_id": "b", "catcher_id": 10, "pitcher_id": 100},
            {"decision_id": "c", "catcher_id": 20, "pitcher_id": 200},
        ]
    ).to_parquet(decisions_path, index=False)
    pd.DataFrame(
        [
            {
                "propensity_threshold": 0.025,
                "decision_id": "a",
                "catcher_id": 10,
                "count_tier": "FirstPitch",
                "chosen_supported": True,
                "normalized_entropy": 0.8,
                "effective_supported_choices": 3.0,
                "top_supported_probability": 0.5,
                "supported_deviation_gain": 0.002,
                "chosen_gap_vs_best_supported": 0.001,
                "observed_choice_is_model_minimum": True,
                "deviation_exceeds_noise_floor": False,
            },
            {
                "propensity_threshold": 0.025,
                "decision_id": "c",
                "catcher_id": 20,
                "count_tier": "PitcherAhead",
                "chosen_supported": False,
                "normalized_entropy": 0.9,
                "effective_supported_choices": 4.0,
                "top_supported_probability": 0.4,
                "supported_deviation_gain": 0.003,
                "chosen_gap_vs_best_supported": None,
                "observed_choice_is_model_minimum": False,
                "deviation_exceeds_noise_floor": False,
            },
        ]
    ).to_parquet(diagnostics_path, index=False)
    (derived / "player_archetype_slice6c.json").write_text(
        json.dumps(
            {
                "contract_version": "player_archetype_slice6c_supported_value_v1",
                "status": "ready",
                "audit": {"decisions": 3},
                "artifacts": {"decision_values_2026_sha256": _sha256(decisions_path)},
            }
        ),
        encoding="utf-8",
    )
    (derived / "player_archetype_slice6d.json").write_text(
        json.dumps(
            {
                "contract_version": "player_archetype_slice6d_game_theory_diagnostics_v1",
                "status": "ready",
                "threshold_sensitivity": [{"propensity_threshold": 0.025, "decisions": 2}],
                "artifacts": {"decision_diagnostics_sha256": _sha256(diagnostics_path)},
            }
        ),
        encoding="utf-8",
    )

    payload = build_catcher_descriptive_slice8_strategy_bridge(tmp_path)

    assert payload["release_gate_passed"] is True
    assert payload["publication_status"] == "research_only_no_leaderboard"
    assert payload["summary"]["total_decisions"] == 3
    assert payload["summary"]["supported_set_decisions"] == 2
    assert payload["release_gate"]["leaderboard_enabled"] is False
    assert payload["release_gate"]["composite_score_enabled"] is False
    row = next(item for item in payload["rows"] if item["catcher_id"] == 10)
    assert row["supported_set_coverage_pct"] == pytest.approx(50.0)
    assert row["mean_normalized_entropy"] == pytest.approx(0.8)
    assert row["deviations_exceeding_noise_floor"] == 0
    assert "rank" not in row

    response = get_catcher_descriptive_strategy_bridge(2026, 10, tmp_path)
    assert response["status"] == "limited"
    assert response["row"]["catcher_id"] == 10


def test_strategy_bridge_does_not_impute_other_seasons(tmp_path: Path) -> None:
    response = get_catcher_descriptive_strategy_bridge(2025, 10, tmp_path)

    assert response["status"] == "unavailable"
    assert response["row"] is None
    assert "2026 only" in response["reason"]
