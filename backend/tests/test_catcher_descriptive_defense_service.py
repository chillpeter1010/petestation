from __future__ import annotations

import json

import pandas as pd
import pytest

from app.services.catcher_descriptive_defense_service import (
    CONTRACT_VERSION,
    build_catcher_descriptive_slice6_defense,
    canonical_team_ledger_path,
    defense_catcher_parquet_path,
    defense_team_parquet_path,
)
from app.services.catcher_descriptive_metrics_service import (
    get_catcher_descriptive_leaderboard,
    metrics_json_path,
)


def _write_sources(tmp_path) -> None:
    source = pd.DataFrame(
        [
            {
                "Season": 2021, "Name": "Catcher One", "Team": "ARI", "Pos": "C", "Inn": 200.0,
                "rSZ": 2, "rCERA": 1, "rSB": 1, "rGFP": 0, "DRS": 4, "FRM": 1.5, "FRV": 2,
                "Def": 7.0, "NameASCII": "Catcher One", "PlayerId": 10, "MLBAMID": 1,
            },
            {
                "Season": 2021, "Name": "Catcher One", "Team": "BOS", "Pos": "C", "Inn": 133.1,
                "rSZ": 1, "rCERA": 0, "rSB": 0, "rGFP": 1, "DRS": 2, "FRM": 0.5, "FRV": 1,
                "Def": 3.0, "NameASCII": "Catcher One", "PlayerId": 10, "MLBAMID": 1,
            },
            {
                "Season": 2021, "Name": "Catcher Two", "Team": "BOS", "Pos": "C", "Inn": 80.0,
                "rSZ": 0, "rCERA": 0, "rSB": -1, "rGFP": 0, "DRS": -1, "FRM": 0.0, "FRV": 0,
                "Def": 0.0, "NameASCII": "Catcher Two", "PlayerId": 20, "MLBAMID": 2,
            },
            {
                "Season": 2022, "Name": "Catcher One", "Team": "ARI", "Pos": "C", "Inn": 330.0,
                "rSZ": 3, "rCERA": 1, "rSB": 0, "rGFP": 1, "DRS": 5, "FRM": 2.0, "FRV": 3,
                "Def": 8.0, "NameASCII": "Catcher One", "PlayerId": 10, "MLBAMID": 1,
            },
        ]
    )
    source.to_csv(tmp_path / "catcher_2021_2026_drs.csv", index=False, encoding="utf-8-sig")
    frv_source = source[
        ["Season", "Name", "Team", "Pos", "Inn", "FRV", "NameASCII", "PlayerId", "MLBAMID"]
    ].copy()
    frv_source["G"] = [30, 20, 10, 50]
    frv_source["GS"] = [25, 15, 5, 45]
    frv_source["Throwing"] = [1, 0, -1, 1]
    frv_source["Blocking"] = [0, 0, 0, 1]
    frv_source["Framing"] = [1, 1, 1, 1]
    frv_source["Arm"] = None
    frv_source["Range"] = None
    frv_source["Inf DP"] = 0
    frv_source["1B Rec"] = None
    frv_source = frv_source[
        [
            "Season", "Name", "Team", "Pos", "G", "GS", "Inn", "Throwing", "Blocking",
            "Framing", "Arm", "Range", "Inf DP", "1B Rec", "FRV", "NameASCII", "PlayerId", "MLBAMID",
        ]
    ]
    frv_source.to_csv(tmp_path / "catcher_2021_2026_frv_statcast.csv", index=False, encoding="utf-8-sig")
    ledger = pd.DataFrame(
        [
            {"season": 2021, "pitching_team_id": 109, "pitching_team_abbr": "AZ", "catcher_id": 1,
             "catcher_name": "Catcher One", "outs": 600, "display_ip": "200.0"},
            {"season": 2021, "pitching_team_id": 111, "pitching_team_abbr": "BOS", "catcher_id": 1,
             "catcher_name": "Catcher One", "outs": 400, "display_ip": "133.1"},
            {"season": 2021, "pitching_team_id": 111, "pitching_team_abbr": "BOS", "catcher_id": 2,
             "catcher_name": "Catcher Two", "outs": 240, "display_ip": "80.0"},
            {"season": 2022, "pitching_team_id": 109, "pitching_team_abbr": "AZ", "catcher_id": 1,
             "catcher_name": "Catcher One", "outs": 990, "display_ip": "330.0"},
        ]
    )
    path = canonical_team_ledger_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_parquet(path, index=False)


def test_slice6_reconciles_team_keys_and_aggregates_multi_team_catcher(tmp_path) -> None:
    _write_sources(tmp_path)

    payload = build_catcher_descriptive_slice6_defense((2021, 2022), tmp_path)
    row = next(item for item in payload["rows"] if item["season"] == 2021 and item["catcher_id"] == 1)

    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["release_gate_passed"] is True
    assert payload["reconciliation"]["matched_rows"] == 4
    assert payload["reconciliation"]["source_only_rows"] == 0
    assert payload["reconciliation"]["canonical_only_rows"] == 0
    assert row["teams"] == "AZ, BOS"
    assert row["canonical_outs"] == 1_000
    assert row["drs"] == 6.0
    assert row["rsz"] == 3.0
    assert row["frv"] == 3.0
    assert row["throwing"] == 1.0
    assert row["blocking"] == 0.0
    assert row["framing"] == 2.0
    assert row["frv_status"] == "available"
    assert row["drs_status"] == "available"
    assert payload["cross_source_reconciliation"]["exact_frv_rows"] == 4
    assert defense_team_parquet_path(tmp_path).exists()
    assert defense_catcher_parquet_path(tmp_path).exists()


def test_slice6_merges_season_defense_without_changing_existing_metrics(tmp_path) -> None:
    _write_sources(tmp_path)
    build_catcher_descriptive_slice6_defense((2021, 2022), tmp_path)
    path = metrics_json_path(2021, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "contract_version": "test",
                "source_contract_version": "test",
                "publication_status": "single_season_preview",
                "year": 2021,
                "generated_at_utc": "2026-10-20T00:00:00+00:00",
                "fip_constant": 3.1,
                "fip_constant_method": "test",
                "pitcher_mix_method": "test",
                "lco_diagnostic_method": "test",
                "qualification": {},
                "summary": {},
                "warnings": [],
                "rows": [
                    {"season": 2021, "catcher_id": 1, "catcher_name": "Catcher One", "outs": 1_000,
                     "display_ip": "333.1", "c_save_run": 8.0, "ranking_eligible": True}
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = get_catcher_descriptive_leaderboard(2021, data_dir=tmp_path)
    row = payload["rows"][0]

    assert row["c_save_run"] == 8.0
    assert row["drs"] == 6.0
    assert row["frv"] == 3.0
    assert row["throwing"] == 1.0
    assert row["frv_status"] == "available"
    assert payload["defense"]["park_factor_status"] == "deferred_by_user"
    assert payload["defense"]["paired_duo_status"] == "unavailable_season_level_only"


def test_slice6_rejects_cross_source_frv_mismatch(tmp_path) -> None:
    _write_sources(tmp_path)
    path = tmp_path / "catcher_2021_2026_frv_statcast.csv"
    frame = pd.read_csv(path, encoding="utf-8-sig")
    frame.loc[0, "FRV"] += 1
    frame.to_csv(path, index=False, encoding="utf-8-sig")

    with pytest.raises(ValueError, match="FRV export do not match"):
        build_catcher_descriptive_slice6_defense((2021, 2022), tmp_path)
