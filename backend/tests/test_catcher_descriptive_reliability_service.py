from __future__ import annotations

import json

import pandas as pd
import pytest

from app.services.catcher_descriptive_metrics_service import (
    get_catcher_descriptive_leaderboard,
    metrics_json_path,
    pair_parquet_path,
)
from app.services.catcher_descriptive_reliability_service import (
    CONTRACT_VERSION,
    build_catcher_descriptive_slice4_reliability,
    reliability_parquet_path,
)


def _write_metric_sources(tmp_path) -> None:
    values = {
        2021: [(1, "One", 0.10), (2, "Two", -0.10), (3, "Small", 0.20)],
        2022: [(1, "One", 0.11), (2, "Two", -0.09), (3, "Small", -0.20)],
    }
    for year, catchers in values.items():
        rows = []
        pairs = []
        for catcher_id, catcher_name, per_ip in catchers:
            outs = 1_000 if catcher_id != 3 else 240
            c_save_run = per_ip * (outs / 3.0)
            rows.append({
                "season": year,
                "catcher_id": catcher_id,
                "catcher_name": catcher_name,
                "outs": outs,
                "display_ip": f"{outs // 3}.{outs % 3}",
                "c_save_run": round(c_save_run, 4),
                "c_save_run_per_ip": per_ip,
                "ranking_eligible": outs >= 900,
            })
            shares = [400, 300, 300] if outs == 1_000 else [120, 60, 60]
            expected_runs = 4.0 * outs / 27.0
            actual_runs = expected_runs - c_save_run
            for index, pair_outs in enumerate(shares, start=1):
                pairs.append({
                    "season": year,
                    "pitcher_id": catcher_id * 10 + index,
                    "pitcher_name": f"Pitcher {catcher_id}-{index}",
                    "catcher_id": catcher_id,
                    "catcher_name": catcher_name,
                    "outs": pair_outs,
                    "pitcher_charged_runs": actual_runs * pair_outs / outs,
                    "pitcher_season_ra9": 4.0,
                })
        metric_path = metrics_json_path(year, tmp_path)
        metric_path.parent.mkdir(parents=True, exist_ok=True)
        metric_path.write_text(json.dumps({
            "contract_version": "test",
            "source_contract_version": "test",
            "publication_status": "single_season_preview",
            "year": year,
            "generated_at_utc": "2026-10-20T00:00:00+00:00",
            "fip_constant": 3.1,
            "fip_constant_method": "test",
            "pitcher_mix_method": "test",
            "lco_diagnostic_method": "test",
            "qualification": {},
            "summary": {},
            "warnings": [],
            "rows": rows,
        }), encoding="utf-8")
        pd.DataFrame(pairs).to_parquet(pair_parquet_path(year, tmp_path), index=False)


def test_slice4_builds_adjacent_and_dominant_pair_diagnostics(tmp_path) -> None:
    _write_metric_sources(tmp_path)

    payload = build_catcher_descriptive_slice4_reliability((2021, 2022), tmp_path)
    row = next(item for item in payload["rows"] if item["season"] == 2021 and item["catcher_id"] == 1)

    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["cross_year"]["pooled"]["adjacent_pairs"] == 2
    assert payload["cross_year"]["release_gate_passed"] is False
    assert row["dominant_pitcher_id"] == 11
    assert row["dominant_pair_outs"] == 400
    assert row["non_dominant_outs"] == 600
    assert row["dominant_pair_delta_c_save_run_per_ip"] == pytest.approx(0.0, abs=1e-6)
    assert row["dominant_pair_sensitivity_status"] == "stable"
    assert row["adjacent_eligible_season_count"] == 1
    assert row["reliability_tier"] == "limited"
    assert row["reliability_reasons"] == ["cross_year_release_gate_failed"]
    assert reliability_parquet_path(tmp_path).exists()


def test_slice4_marks_small_samples_unavailable_and_merges_into_leaderboard(tmp_path) -> None:
    _write_metric_sources(tmp_path)
    build_catcher_descriptive_slice4_reliability((2021, 2022), tmp_path)

    leaderboard = get_catcher_descriptive_leaderboard(2021, data_dir=tmp_path)
    qualified = next(item for item in leaderboard["rows"] if item["catcher_id"] == 1)
    small = next(item for item in leaderboard["rows"] if item["catcher_id"] == 3)

    assert leaderboard["reliability"]["release_gate_passed"] is False
    assert qualified["reliability_tier"] == "limited"
    assert qualified["without_dominant_c_save_run_per_ip"] == pytest.approx(0.10, abs=1e-6)
    assert small["reliability_tier"] == "unavailable"
    assert "below_300_catcher_innings" in small["reliability_reasons"]
