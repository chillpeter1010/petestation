from __future__ import annotations

import json

import pandas as pd
import pytest

from app.services.catcher_descriptive_ledger_service import slice1_root
from app.services.catcher_descriptive_closeout_service import build_catcher_descriptive_slice123_closeout
from app.services.catcher_descriptive_metrics_service import (
    _fip,
    _fip_constant,
    _prepare_pairs,
    build_catcher_descriptive_metrics,
    get_catcher_descriptive_detail,
    get_catcher_descriptive_paired_duo_leaderboard,
)


def test_derived_fip_constant_reproduces_official_league_era() -> None:
    controls = pd.DataFrame([{
        "outs": 27,
        "earned_runs": 4,
        "home_runs": 1,
        "walks_total": 3,
        "hit_by_pitch": 1,
        "strikeouts": 9,
    }])

    constant = _fip_constant(controls)

    assert _fip(1, 3, 1, 9, 27, constant) == pytest.approx(4.0)


def test_leave_catcher_out_pair_baseline_excludes_evaluated_catcher() -> None:
    rows = []
    for catcher_id, outs, runs, earned_runs in [(20, 30, 1, 1), (21, 60, 7, 6)]:
        rows.append({
            "season": 2021, "pitcher_id": 10, "catcher_id": catcher_id,
            "pitcher_name": "Pitcher", "catcher_name": f"Catcher {catcher_id}", "pitching_team_abbr": "TST",
            "games": 1, "outs": outs, "bf": 40, "home_runs": 1, "walks_unintentional": 2, "intentional_walks": 0,
            "walks_total": 2, "hit_by_pitch": 0, "strikeouts": 8, "runs_scored_while_pair": runs,
            "pitcher_charged_runs": runs, "earned_runs": earned_runs,
        })

    pairs = _prepare_pairs(pd.DataFrame(rows), constant=3.0).set_index("catcher_id")

    assert pairs.loc[20, "lco_outs"] == 60
    assert pairs.loc[20, "lco_earned_runs"] == 6
    assert pairs.loc[20, "lco_era"] == pytest.approx(2.7)
    assert bool(pairs.loc[20, "baseline_supported"]) is True
    assert pairs.loc[21, "lco_outs"] == 30


def test_build_preview_uses_all_outs_for_full_season_pitcher_mix(tmp_path) -> None:
    yearly = slice1_root(tmp_path) / "yearly"
    status_dir = slice1_root(tmp_path) / "status"
    yearly.mkdir(parents=True)
    status_dir.mkdir(parents=True)
    rows = []
    for catcher_id, outs, runs, earned_runs in [(20, 900, 100, 90), (21, 20, 2, 2)]:
        rows.append({
            "season": 2021, "pitching_team_id": 1, "pitching_team_abbr": "TST", "pitcher_id": 10,
            "catcher_id": catcher_id, "pitcher_name": "Pitcher", "catcher_name": f"Catcher {catcher_id}",
            "games": 50, "pa_rows": 1000, "outs": outs, "bf": 1000, "home_runs": 20,
            "walks_unintentional": 50, "intentional_walks": 2, "walks_total": 52, "hit_by_pitch": 5,
            "strikeouts": 200, "runs_scored_while_pair": runs, "pitcher_charged_runs": runs,
            "earned_runs": earned_runs, "display_ip": "300.0", "responsibility_catcher_available": True,
            "contract_version": "catcher_descriptive_slice1_ledger_v1",
        })
    pd.DataFrame(rows).to_parquet(yearly / "pitcher_catcher_ledger_2021.parquet", index=False)
    pd.DataFrame([
        {"game_pk": 1, "current_catcher_id": 20, "current_catcher_name": "Catcher 20", "pitching_team_abbr": "TST"},
        {"game_pk": 2, "current_catcher_id": 21, "current_catcher_name": "Catcher 21", "pitching_team_abbr": "TST"},
    ]).to_parquet(yearly / "pa_accounting_2021.parquet", index=False)
    pd.DataFrame([{
        "season": 2021, "pitcher_id": 10, "outs": 920, "bf": 2000, "runs": 102,
        "earned_runs": 92, "home_runs": 40, "walks_total": 104, "intentional_walks": 4,
        "hit_by_pitch": 10, "strikeouts": 400,
    }]).to_parquet(yearly / "pitcher_game_controls_2021.parquet", index=False)
    zero_differences = {
        "outs": 0, "bf": 0, "runs": 0, "earned_runs": 0, "home_runs": 0,
        "walks_total": 0, "intentional_walks": 0, "hit_by_pitch": 0, "strikeouts": 0,
    }
    (status_dir / "catcher_ledger_2021.json").write_text(json.dumps({
        "status": "completed", "summary": {
            "completion_gate_passed": True, "games": 2, "pitcher_game_control_rows": 1,
            "reconciliation_rows": 1, "reconciliation_all_match_rows": 1,
            "metric_absolute_differences": zero_differences,
            "ledger_to_pitcher_team_absolute_differences": zero_differences,
            "ledger_to_team_absolute_differences": zero_differences,
        }
    }), encoding="utf-8")

    payload = build_catcher_descriptive_metrics(2021, tmp_path)
    first = next(row for row in payload["rows"] if row["catcher_id"] == 20)
    detail = get_catcher_descriptive_detail(2021, 20, tmp_path)
    paired_duos = get_catcher_descriptive_paired_duo_leaderboard(2021, 120, tmp_path)

    assert first["outs"] == 900
    assert first["earned_runs"] == 90
    assert first["baseline_supported_outs"] == 0
    assert first["baseline_coverage_pct"] == 0.0
    assert first["baseline_status"] == "unavailable"
    assert first["ranking_eligible"] is True
    assert first["t_era"] == pytest.approx(27 * 92 / 920, abs=1e-4)
    assert first["t_ra9"] == pytest.approx(27 * 102 / 920, abs=1e-4)
    expected_c_save_run = (27 * 102 / 920 - 3.0) * 900 / 27
    assert first["c_save_run"] == pytest.approx(expected_c_save_run, abs=1e-4)
    assert first["c_save_run_per_ip"] == pytest.approx(expected_c_save_run / 300, abs=1e-6)
    assert first["lco_t_era"] is None
    assert detail["pitcher_pairs"][0]["pitcher_season_era"] == pytest.approx(27 * 92 / 920, abs=1e-4)
    assert detail["pitcher_pairs"][0]["c_save_run_per_ip"] == pytest.approx(expected_c_save_run / 300, abs=1e-6)
    assert detail["pitcher_pairs"][0]["lco_status"] == "unavailable"
    assert paired_duos["view"] == "paired_duo"
    assert paired_duos["qualification"] == {"minimum_pair_outs": 120, "minimum_pair_ip": 40.0}
    assert paired_duos["summary"]["pairs"] == 1
    assert paired_duos["rows"][0]["pair_key"] == "2021:10:20"
    assert paired_duos["rows"][0]["catcher_name"] == "Catcher 20"
    assert paired_duos["rows"][0]["pitcher_name"] == "Pitcher"
    assert paired_duos["rows"][0]["games"] == 50
    assert paired_duos["rows"][0]["home_runs"] == 20
    assert paired_duos["rows"][0]["t_era"] == pytest.approx(27 * 92 / 920, abs=1e-4)
    assert paired_duos["rows"][0]["c_save_run"] == pytest.approx(expected_c_save_run, abs=1e-4)

    all_paired_duos = get_catcher_descriptive_paired_duo_leaderboard(2021, 0, tmp_path)
    assert all_paired_duos["summary"]["pairs"] == 2

    closeout = build_catcher_descriptive_slice123_closeout((2021,), tmp_path)

    assert closeout["status"] == "passed"
    assert closeout["year_results"][0]["failed_checks"] == []
