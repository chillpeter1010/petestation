from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings
from app.services.catcher_descriptive_ledger_service import slice1_root
from app.services.catcher_descriptive_metrics_service import (
    COUNT_COLUMNS,
    CONTRACT_VERSION as METRICS_CONTRACT_VERSION,
    MIN_RANKING_OUTS,
    RATE_MULTIPLIER,
    metrics_json_path,
    pair_parquet_path,
)


CONTRACT_VERSION = "catcher_descriptive_slice123_closeout_v1"
DEFAULT_YEARS = tuple(range(2021, 2027))
RATE_TOLERANCE = 0.0001
PER_IP_TOLERANCE = 0.000001


def closeout_root(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "research" / "catcher_descriptive" / "slice123_closeout"


def closeout_json_path(data_dir: Path | None = None) -> Path:
    return closeout_root(data_dir) / "catcher_descriptive_slice123_closeout.json"


def _max_abs_difference(left: pd.Series, right: pd.Series) -> float:
    difference = (pd.to_numeric(left, errors="coerce") - pd.to_numeric(right, errors="coerce")).abs()
    return float(difference.max()) if difference.notna().any() else 0.0


def _audit_year(year: int, root: Path) -> dict[str, Any]:
    yearly = slice1_root(root) / "yearly"
    status = json.loads((slice1_root(root) / "status" / f"catcher_ledger_{year}.json").read_text(encoding="utf-8"))
    ledger = pd.read_parquet(yearly / f"pitcher_catcher_ledger_{year}.parquet")
    controls = pd.read_parquet(yearly / f"pitcher_game_controls_{year}.parquet")
    metrics_payload = json.loads(metrics_json_path(year, root).read_text(encoding="utf-8"))
    metrics = pd.DataFrame(metrics_payload["rows"])
    pairs = pd.read_parquet(pair_parquet_path(year, root))

    checks: dict[str, bool] = {}
    summary = status.get("summary") or {}
    metric_differences = summary.get("metric_absolute_differences") or {}
    pitcher_team_differences = summary.get("ledger_to_pitcher_team_absolute_differences") or {}
    team_differences = summary.get("ledger_to_team_absolute_differences") or {}
    checks["ledger_completion_gate"] = status.get("status") == "completed" and bool(summary.get("completion_gate_passed"))
    checks["official_pitcher_game_reconciliation"] = (
        int(summary.get("reconciliation_rows") or 0) == int(summary.get("reconciliation_all_match_rows") or -1)
        and all(float(value) == 0 for value in metric_differences.values())
    )
    checks["pitcher_team_reconciliation"] = bool(pitcher_team_differences) and all(
        float(value) == 0 for value in pitcher_team_differences.values()
    )
    checks["team_reconciliation"] = bool(team_differences) and all(
        float(value) == 0 for value in team_differences.values()
    )
    ledger_key = ["season", "pitching_team_id", "pitcher_id", "catcher_id"]
    checks["ledger_unique_key"] = not ledger.duplicated(ledger_key).any()
    checks["metric_unique_key"] = not metrics.duplicated(["season", "catcher_id"]).any()
    checks["pair_unique_key"] = not pairs.duplicated(["season", "pitcher_id", "catcher_id"]).any()
    checks["metrics_contract"] = metrics_payload.get("contract_version") == METRICS_CONTRACT_VERSION

    supported_ledger = ledger.loc[ledger["catcher_id"].notna()].copy()
    ledger_pairs = supported_ledger.groupby(["season", "pitcher_id", "catcher_id"], as_index=False)[COUNT_COLUMNS].sum()
    pair_compare = ledger_pairs.merge(
        pairs[["season", "pitcher_id", "catcher_id", *COUNT_COLUMNS]],
        on=["season", "pitcher_id", "catcher_id"],
        how="outer",
        suffixes=("_ledger", "_pair"),
        indicator=True,
    )
    pair_count_differences = {
        column: _max_abs_difference(pair_compare[f"{column}_ledger"], pair_compare[f"{column}_pair"])
        for column in COUNT_COLUMNS
    }
    checks["pair_counts_reconcile_to_ledger"] = (
        pair_compare["_merge"].eq("both").all() and all(value == 0 for value in pair_count_differences.values())
    )

    catcher_totals = pairs.groupby("catcher_id", as_index=False)[COUNT_COLUMNS].sum()
    catcher_compare = metrics.merge(catcher_totals, on="catcher_id", suffixes=("_metric", "_pair"), how="outer", indicator=True)
    catcher_count_differences = {
        column: _max_abs_difference(catcher_compare[f"{column}_metric"], catcher_compare[f"{column}_pair"])
        for column in COUNT_COLUMNS
    }
    checks["catcher_counts_reconcile_to_pairs"] = (
        catcher_compare["_merge"].eq("both").all() and all(value == 0 for value in catcher_count_differences.values())
    )

    control_totals = controls.groupby(["season", "pitcher_id"], as_index=False).agg(
        pitcher_season_outs=("outs", "sum"),
        pitcher_season_runs=("runs", "sum"),
        pitcher_season_earned_runs=("earned_runs", "sum"),
    )
    pair_seasons = pairs[[
        "season", "pitcher_id", "pitcher_season_outs", "pitcher_season_runs", "pitcher_season_earned_runs"
    ]].drop_duplicates()
    season_compare = pair_seasons.merge(control_totals, on=["season", "pitcher_id"], how="outer", suffixes=("_pair", "_control"), indicator=True)
    season_total_differences = {
        column: _max_abs_difference(season_compare[f"{column}_pair"], season_compare[f"{column}_control"])
        for column in ["pitcher_season_outs", "pitcher_season_runs", "pitcher_season_earned_runs"]
    }
    checks["pitcher_season_controls_reconcile"] = (
        season_compare["_merge"].eq("both").all() and all(value == 0 for value in season_total_differences.values())
    )
    positive_out_pairs = pairs.loc[pairs["outs"] > 0]
    zero_out_pairs = pairs.loc[pairs["outs"] == 0]
    checks["positive_out_pitcher_season_rates_complete"] = not positive_out_pairs[[
        "pitcher_season_era", "pitcher_season_ra9", "pitcher_season_fip"
    ]].isna().any().any()
    checks["zero_out_pairs_have_zero_weight"] = bool(zero_out_pairs["outs"].eq(0).all())

    catcher_outs = pairs.groupby("catcher_id")["outs"].transform("sum")
    weight_sums = (pairs["outs"] / catcher_outs).groupby(pairs["catcher_id"]).sum()
    max_weight_sum_difference = float((weight_sums - 1.0).abs().max())
    checks["pitcher_mix_weights_sum_to_one"] = max_weight_sum_difference < 1e-12

    weighted = pairs.assign(
        weighted_t_era=pairs["pitcher_season_era"] * pairs["outs"],
        weighted_t_ra9=pairs["pitcher_season_ra9"] * pairs["outs"],
        weighted_t_fip=pairs["pitcher_season_fip"] * pairs["outs"],
    ).groupby("catcher_id", as_index=False).agg(
        outs=("outs", "sum"),
        weighted_t_era=("weighted_t_era", "sum"),
        weighted_t_ra9=("weighted_t_ra9", "sum"),
        weighted_t_fip=("weighted_t_fip", "sum"),
    )
    for column in ["t_era", "t_ra9", "t_fip"]:
        weighted[column] = weighted[f"weighted_{column}"] / weighted["outs"]
    formulas = metrics.merge(weighted[["catcher_id", "outs", "t_era", "t_ra9", "t_fip"]], on="catcher_id", suffixes=("_metric", "_audit"))
    formulas["c_era_audit"] = RATE_MULTIPLIER * formulas["earned_runs"] / formulas["outs_metric"]
    formulas["c_ra9_audit"] = RATE_MULTIPLIER * formulas["pitcher_charged_runs"] / formulas["outs_metric"]
    formulas["c_fip_audit"] = (
        3.0 * (
            13.0 * formulas["home_runs"]
            + 3.0 * (formulas["walks_total"] + formulas["hit_by_pitch"])
            - 2.0 * formulas["strikeouts"]
        ) / formulas["outs_metric"]
        + float(metrics_payload["fip_constant"])
    )
    formulas["c_save_run_audit"] = (
        (formulas["t_ra9_audit"] - formulas["c_ra9_audit"]) * formulas["outs_metric"] / RATE_MULTIPLIER
    )
    formulas["c_save_run_per_ip_audit"] = formulas["c_save_run_audit"] / (formulas["outs_metric"] / 3.0)
    formula_differences = {
        "c_era": _max_abs_difference(formulas["c_era"], formulas["c_era_audit"]),
        "c_ra9": _max_abs_difference(formulas["c_ra9"], formulas["c_ra9_audit"]),
        "c_fip": _max_abs_difference(formulas["c_fip"], formulas["c_fip_audit"]),
        "t_era": _max_abs_difference(formulas["t_era_metric"], formulas["t_era_audit"]),
        "t_ra9": _max_abs_difference(formulas["t_ra9_metric"], formulas["t_ra9_audit"]),
        "t_fip": _max_abs_difference(formulas["t_fip_metric"], formulas["t_fip_audit"]),
        "c_save_run": _max_abs_difference(formulas["c_save_run"], formulas["c_save_run_audit"]),
        "c_save_run_per_ip": _max_abs_difference(formulas["c_save_run_per_ip"], formulas["c_save_run_per_ip_audit"]),
    }
    checks["rate_formulas_reproduce"] = all(
        difference <= (PER_IP_TOLERANCE if column == "c_save_run_per_ip" else RATE_TOLERANCE)
        for column, difference in formula_differences.items()
    )
    checks["ranking_eligibility_exact"] = (
        metrics["ranking_eligible"].astype(bool) == metrics["outs"].ge(MIN_RANKING_OUTS)
    ).all()
    pair_c_save_run_audit = (
        (pairs["pitcher_season_ra9"] - pairs["c_ra9"]) * pairs["outs"] / RATE_MULTIPLIER
    )
    pair_c_save_run_per_ip_audit = pair_c_save_run_audit / (pairs["outs"] / 3.0)
    pair_formula_differences = {
        "c_save_run": _max_abs_difference(pairs["pair_c_save_run"], pair_c_save_run_audit),
        "c_save_run_per_ip": _max_abs_difference(pairs["pair_c_save_run_per_ip"], pair_c_save_run_per_ip_audit),
    }
    checks["pair_c_save_run_formulas_reproduce"] = all(value < 1e-12 for value in pair_formula_differences.values())
    checks["no_small_sample_annualization"] = not any(
        column.lower() in {"sr/yr", "sra/yr", "annualized_c_save_run"} for column in metrics.columns
    )

    checks = {name: bool(passed) for name, passed in checks.items()}
    failed_checks = [name for name, passed in checks.items() if not passed]
    return {
        "year": year,
        "status": "passed" if not failed_checks else "failed",
        "checks": checks,
        "failed_checks": failed_checks,
        "summary": {
            "games": int(summary.get("games") or 0),
            "pitcher_game_controls": int(summary.get("pitcher_game_control_rows") or 0),
            "ledger_rows": int(len(ledger)),
            "pair_rows": int(len(pairs)),
            "catchers": int(len(metrics)),
            "ranking_eligible_catchers": int(metrics["ranking_eligible"].sum()),
            "zero_out_pairs": int(len(zero_out_pairs)),
        },
        "max_absolute_differences": {
            "pair_counts": pair_count_differences,
            "catcher_counts": catcher_count_differences,
            "pitcher_season_controls": season_total_differences,
            "formulas": formula_differences,
            "pair_formulas": pair_formula_differences,
            "weight_sum": max_weight_sum_difference,
        },
    }


def build_catcher_descriptive_slice123_closeout(
    years: tuple[int, ...] = DEFAULT_YEARS,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    year_results = [_audit_year(year, root) for year in years]
    passed = all(result["status"] == "passed" for result in year_results)
    payload = {
        "contract_version": CONTRACT_VERSION,
        "metrics_contract_version": METRICS_CONTRACT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed else "failed",
        "years": list(years),
        "totals": {
            "games": sum(result["summary"]["games"] for result in year_results),
            "pitcher_game_controls": sum(result["summary"]["pitcher_game_controls"] for result in year_results),
            "ledger_rows": sum(result["summary"]["ledger_rows"] for result in year_results),
            "pair_rows": sum(result["summary"]["pair_rows"] for result in year_results),
            "catcher_seasons": sum(result["summary"]["catchers"] for result in year_results),
        },
        "year_results": year_results,
        "claim_language": "cSaveRun and all c/t differences are observed associations, not causal catcher value.",
    }
    path = closeout_json_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return payload
