from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings
from app.services.catcher_descriptive_ledger_service import CONTRACT_VERSION as LEDGER_CONTRACT_VERSION
from app.services.catcher_descriptive_ledger_service import slice1_root


CONTRACT_VERSION = "catcher_descriptive_slice23_preview_v3"
MIN_RANKING_OUTS = 900
MIN_BASELINE_OUTS = 90
MIN_LCO_PITCHER_OUTS = 30
MIN_AVAILABLE_BASELINE_COVERAGE = 0.95
RATE_MULTIPLIER = 27.0

COUNT_COLUMNS = [
    "outs",
    "bf",
    "home_runs",
    "walks_unintentional",
    "intentional_walks",
    "walks_total",
    "hit_by_pitch",
    "strikeouts",
    "runs_scored_while_pair",
    "pitcher_charged_runs",
    "earned_runs",
]


def slice23_root(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "research" / "catcher_descriptive" / "slice23_preview"


def metrics_json_path(year: int, data_dir: Path | None = None) -> Path:
    return slice23_root(data_dir) / f"catcher_descriptive_metrics_{int(year)}.json"


def metrics_parquet_path(year: int, data_dir: Path | None = None) -> Path:
    return slice23_root(data_dir) / f"catcher_descriptive_metrics_{int(year)}.parquet"


def pair_parquet_path(year: int, data_dir: Path | None = None) -> Path:
    return slice23_root(data_dir) / f"pitcher_catcher_expected_baselines_{int(year)}.parquet"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _atomic_write_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def _rate(numerator: float | int, outs: float | int) -> float | None:
    return float(numerator) * RATE_MULTIPLIER / float(outs) if float(outs) > 0 else None


def _fip(
    home_runs: float | int,
    walks: float | int,
    hit_by_pitch: float | int,
    strikeouts: float | int,
    outs: float | int,
    constant: float,
) -> float | None:
    if float(outs) <= 0:
        return None
    component = 13.0 * float(home_runs) + 3.0 * (float(walks) + float(hit_by_pitch)) - 2.0 * float(strikeouts)
    return 3.0 * component / float(outs) + float(constant)


def _display_ip(outs: int) -> str:
    return f"{int(outs) // 3}.{int(outs) % 3}"


def _round(value: float | None, digits: int = 4) -> float | None:
    return round(float(value), digits) if value is not None and pd.notna(value) else None


def _fip_constant(controls: pd.DataFrame) -> float:
    outs = float(controls["outs"].sum())
    if outs <= 0:
        raise ValueError("Cannot derive the FIP constant without official outs")
    league_era = RATE_MULTIPLIER * float(controls["earned_runs"].sum()) / outs
    component = (
        13.0 * float(controls["home_runs"].sum())
        + 3.0 * (float(controls["walks_total"].sum()) + float(controls["hit_by_pitch"].sum()))
        - 2.0 * float(controls["strikeouts"].sum())
    )
    return league_era - 3.0 * component / outs


def _require_completed_ledger(year: int, root: Path) -> tuple[Path, Path, Path]:
    status_path = slice1_root(root) / "status" / f"catcher_ledger_{int(year)}.json"
    if not status_path.exists():
        raise FileNotFoundError(f"Catcher ledger status is unavailable for {int(year)}")
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("status") != "completed" or not (status.get("summary") or {}).get("completion_gate_passed"):
        raise ValueError(f"Catcher ledger for {int(year)} has not passed its reconciliation gate")
    yearly = slice1_root(root) / "yearly"
    ledger_path = yearly / f"pitcher_catcher_ledger_{int(year)}.parquet"
    pa_path = yearly / f"pa_accounting_{int(year)}.parquet"
    controls_path = yearly / f"pitcher_game_controls_{int(year)}.parquet"
    for path in (ledger_path, pa_path, controls_path):
        if not path.exists():
            raise FileNotFoundError(f"Required Slice 1 artifact is unavailable: {path}")
    return ledger_path, pa_path, controls_path


def _prepare_pairs(
    ledger: pd.DataFrame,
    constant: float,
    controls: pd.DataFrame | None = None,
) -> pd.DataFrame:
    supported = ledger.loc[ledger["catcher_id"].notna()].copy()
    for column in COUNT_COLUMNS:
        supported[column] = pd.to_numeric(supported[column], errors="coerce").fillna(0)
    pairs = (
        supported.groupby(["season", "pitcher_id", "catcher_id"], as_index=False)
        .agg(
            pitcher_name=("pitcher_name", "first"),
            catcher_name=("catcher_name", "first"),
            teams=("pitching_team_abbr", lambda values: ", ".join(sorted(set(values.dropna().astype(str))))),
            games=("games", "sum"),
            **{column: (column, "sum") for column in COUNT_COLUMNS},
        )
    )
    pitcher_totals = (
        pairs.groupby(["season", "pitcher_id"], as_index=False)[COUNT_COLUMNS]
        .sum()
        .rename(columns={column: f"pitcher_total_{column}" for column in COUNT_COLUMNS})
    )
    pairs = pairs.merge(pitcher_totals, on=["season", "pitcher_id"], how="left")
    if controls is None:
        season_totals = pitcher_totals.rename(
            columns={f"pitcher_total_{column}": f"pitcher_season_{column}" for column in COUNT_COLUMNS}
        )
        season_totals["pitcher_season_runs"] = season_totals["pitcher_season_pitcher_charged_runs"]
    else:
        season_totals = controls.groupby(["season", "pitcher_id"], as_index=False).agg(
            pitcher_season_outs=("outs", "sum"),
            pitcher_season_bf=("bf", "sum"),
            pitcher_season_runs=("runs", "sum"),
            pitcher_season_earned_runs=("earned_runs", "sum"),
            pitcher_season_home_runs=("home_runs", "sum"),
            pitcher_season_walks_total=("walks_total", "sum"),
            pitcher_season_intentional_walks=("intentional_walks", "sum"),
            pitcher_season_hit_by_pitch=("hit_by_pitch", "sum"),
            pitcher_season_strikeouts=("strikeouts", "sum"),
        )
    pairs = pairs.merge(season_totals, on=["season", "pitcher_id"], how="left")
    for column in COUNT_COLUMNS:
        pairs[f"lco_{column}"] = pairs[f"pitcher_total_{column}"] - pairs[column]
    pairs["baseline_supported"] = pairs["lco_outs"] >= MIN_LCO_PITCHER_OUTS
    pairs["display_ip"] = pairs["outs"].astype(int).map(_display_ip)
    pairs["c_era"] = pairs.apply(lambda row: _rate(row["earned_runs"], row["outs"]), axis=1)
    pairs["c_ra9"] = pairs.apply(lambda row: _rate(row["pitcher_charged_runs"], row["outs"]), axis=1)
    pairs["c_fip"] = pairs.apply(
        lambda row: _fip(row["home_runs"], row["walks_total"], row["hit_by_pitch"], row["strikeouts"], row["outs"], constant),
        axis=1,
    )
    pairs["lco_era"] = pairs.apply(lambda row: _rate(row["lco_earned_runs"], row["lco_outs"]), axis=1)
    pairs["lco_ra9"] = pairs.apply(lambda row: _rate(row["lco_pitcher_charged_runs"], row["lco_outs"]), axis=1)
    pairs["lco_fip"] = pairs.apply(
        lambda row: _fip(
            row["lco_home_runs"], row["lco_walks_total"], row["lco_hit_by_pitch"], row["lco_strikeouts"], row["lco_outs"], constant
        ),
        axis=1,
    )
    pairs["pitcher_season_era"] = pairs.apply(
        lambda row: _rate(row["pitcher_season_earned_runs"], row["pitcher_season_outs"]), axis=1
    )
    pairs["pitcher_season_ra9"] = pairs.apply(
        lambda row: _rate(row["pitcher_season_runs"], row["pitcher_season_outs"]), axis=1
    )
    pairs["pitcher_season_fip"] = pairs.apply(
        lambda row: _fip(
            row["pitcher_season_home_runs"],
            row["pitcher_season_walks_total"],
            row["pitcher_season_hit_by_pitch"],
            row["pitcher_season_strikeouts"],
            row["pitcher_season_outs"],
            constant,
        ),
        axis=1,
    )
    pairs["pair_c_save_run"] = pairs.apply(
        lambda row: (row["pitcher_season_ra9"] - row["c_ra9"]) * row["outs"] / RATE_MULTIPLIER,
        axis=1,
    )
    pairs["pair_c_save_run_per_ip"] = pairs.apply(
        lambda row: row["pair_c_save_run"] / (row["outs"] / 3.0) if row["outs"] else None,
        axis=1,
    )
    pairs["lco_pair_c_save_run"] = pairs.apply(
        lambda row: (row["lco_ra9"] - row["c_ra9"]) * row["outs"] / RATE_MULTIPLIER
        if row["baseline_supported"]
        else None,
        axis=1,
    )
    return pairs


def build_catcher_descriptive_metrics(year: int, data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    ledger_path, pa_path, controls_path = _require_completed_ledger(year, root)
    ledger = pd.read_parquet(ledger_path)
    pa = pd.read_parquet(pa_path)
    controls = pd.read_parquet(controls_path)
    constant = _fip_constant(controls)
    pairs = _prepare_pairs(ledger, constant, controls)

    game_context = (
        pa.groupby("current_catcher_id", as_index=False)
        .agg(
            games=("game_pk", "nunique"),
            current_catcher_name=("current_catcher_name", "first"),
            current_teams=("pitching_team_abbr", lambda values: ", ".join(sorted(set(values.dropna().astype(str))))),
        )
        .rename(columns={"current_catcher_id": "catcher_id"})
    )
    game_lookup = {int(row.catcher_id): row for row in game_context.itertuples() if pd.notna(row.catcher_id)}

    rows: list[dict[str, Any]] = []
    for catcher_id, group in pairs.groupby("catcher_id", sort=False):
        catcher_id_int = int(catcher_id)
        counts = {column: int(group[column].sum()) for column in COUNT_COLUMNS}
        outs = counts["outs"]
        supported = group.loc[group["baseline_supported"]].copy()
        supported_outs = int(supported["outs"].sum())
        coverage = supported_outs / outs if outs else 0.0
        if supported_outs < MIN_BASELINE_OUTS:
            baseline_status = "unavailable"
        elif coverage < MIN_AVAILABLE_BASELINE_COVERAGE:
            baseline_status = "limited"
        else:
            baseline_status = "available"

        t_era = float((group["pitcher_season_era"] * group["outs"]).sum() / outs) if outs else None
        t_ra9 = float((group["pitcher_season_ra9"] * group["outs"]).sum() / outs) if outs else None
        t_fip = float((group["pitcher_season_fip"] * group["outs"]).sum() / outs) if outs else None
        c_era = _rate(counts["earned_runs"], outs)
        c_ra9 = _rate(counts["pitcher_charged_runs"], outs)
        c_save_run = (t_ra9 - c_ra9) * outs / RATE_MULTIPLIER if t_ra9 is not None and c_ra9 is not None else None
        c_save_run_per_ip = c_save_run / (outs / 3.0) if c_save_run is not None and outs else None
        lco_t_era = lco_t_ra9 = lco_t_fip = lco_supported_c_era = lco_supported_c_ra9 = lco_runs_vs_mix = None
        if supported_outs >= MIN_BASELINE_OUTS:
            lco_t_era = float((supported["lco_era"] * supported["outs"]).sum() / supported_outs)
            lco_t_ra9 = float((supported["lco_ra9"] * supported["outs"]).sum() / supported_outs)
            lco_t_fip = float((supported["lco_fip"] * supported["outs"]).sum() / supported_outs)
            lco_supported_c_era = _rate(supported["earned_runs"].sum(), supported_outs)
            lco_supported_c_ra9 = _rate(supported["pitcher_charged_runs"].sum(), supported_outs)
            lco_runs_vs_mix = (
                (lco_t_ra9 - lco_supported_c_ra9) * supported_outs / RATE_MULTIPLIER
                if lco_supported_c_ra9 is not None
                else None
            )

        context = game_lookup.get(catcher_id_int)
        team_codes = sorted({code for value in group["teams"] for code in str(value).split(", ") if code})
        if context is not None:
            team_codes = sorted(set(team_codes) | {code for code in str(context.current_teams).split(", ") if code})
        team = team_codes[0] if len(team_codes) == 1 else f"{len(team_codes)} Tms"
        max_pitcher_share = float(group["outs"].max() / outs) if outs else None
        ranking_eligible = bool(outs >= MIN_RANKING_OUTS)
        rows.append(
            {
                "season": int(year),
                "catcher_id": catcher_id_int,
                "catcher_name": str(group["catcher_name"].dropna().iloc[0]) if group["catcher_name"].notna().any() else (str(context.current_catcher_name) if context is not None else f"Catcher {catcher_id_int}"),
                "team": team,
                "teams": team_codes,
                "games": int(context.games) if context is not None else None,
                "pitchers": int(group["pitcher_id"].nunique()),
                "outs": outs,
                "display_ip": _display_ip(outs),
                **counts,
                "c_era": _round(c_era),
                "c_ra9": _round(c_ra9),
                "c_fip": _round(_fip(counts["home_runs"], counts["walks_total"], counts["hit_by_pitch"], counts["strikeouts"], outs, constant)),
                "baseline_supported_outs": supported_outs,
                "baseline_supported_ip": _display_ip(supported_outs),
                "baseline_coverage_pct": _round(coverage * 100.0, 2),
                "baseline_status": baseline_status,
                "t_era": _round(t_era),
                "t_ra9": _round(t_ra9),
                "t_fip": _round(t_fip),
                "c_save_run": _round(c_save_run),
                "c_save_run_per_ip": _round(c_save_run_per_ip, 6),
                "lco_supported_c_era": _round(lco_supported_c_era),
                "lco_supported_c_ra9": _round(lco_supported_c_ra9),
                "lco_t_era": _round(lco_t_era),
                "lco_t_ra9": _round(lco_t_ra9),
                "lco_t_fip": _round(lco_t_fip),
                "lco_c_save_run": _round(lco_runs_vs_mix),
                "max_pitcher_out_share_pct": _round(max_pitcher_share * 100.0 if max_pitcher_share is not None else None, 2),
                "sample_status": "available" if outs >= MIN_RANKING_OUTS else "limited",
                "ranking_eligible": ranking_eligible,
                "contract_version": CONTRACT_VERSION,
            }
        )

    rows.sort(
        key=lambda row: (
            not row["ranking_eligible"],
            -(row["c_save_run"] if row["c_save_run"] is not None else -999999),
            -row["outs"],
        )
    )
    rank = 0
    for row in rows:
        if row["ranking_eligible"] and row["c_save_run"] is not None:
            rank += 1
            row["rank"] = rank
        else:
            row["rank"] = None

    row_frame = pd.DataFrame(rows)
    _atomic_write_parquet(metrics_parquet_path(year, root), row_frame)
    _atomic_write_parquet(pair_parquet_path(year, root), pairs)
    payload = {
        "contract_version": CONTRACT_VERSION,
        "source_contract_version": LEDGER_CONTRACT_VERSION,
        "publication_status": "single_season_preview",
        "year": int(year),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "fip_constant": _round(constant, 6),
        "fip_constant_method": "official league ERA minus official league FIP component, using Slice 1 pitcher-game controls",
        "pitcher_mix_method": "full pitcher-season ERA, RA9 and FIP weighted by the catcher's actual outs with each pitcher",
        "lco_diagnostic_method": "leave-catcher-out pitcher-season rates; diagnostic only and excluded from main ranking eligibility",
        "qualification": {
            "minimum_ranking_outs": MIN_RANKING_OUTS,
            "minimum_ranking_ip": MIN_RANKING_OUTS / 3,
            "minimum_lco_aggregate_outs": MIN_BASELINE_OUTS,
            "minimum_lco_pitcher_outs": MIN_LCO_PITCHER_OUTS,
            "minimum_available_lco_coverage_pct": MIN_AVAILABLE_BASELINE_COVERAGE * 100.0,
        },
        "rows": rows,
        "summary": {
            "catchers": len(rows),
            "ranking_eligible_catchers": sum(bool(row["ranking_eligible"]) for row in rows),
            "available_baselines": sum(row["baseline_status"] == "available" for row in rows),
            "limited_baselines": sum(row["baseline_status"] == "limited" for row in rows),
            "unavailable_baselines": sum(row["baseline_status"] == "unavailable" for row in rows),
        },
        "warnings": [
            f"{int(year)} is single-season descriptive output; Slice 2 and Slice 3 passed the six-season closeout audit.",
            "All c/t differences are observed associations, not causal catcher value or catcher runs saved.",
            "Main t metrics use every catcher out and weight each pitcher's complete official season ERA, RA9 and FIP by the catcher's actual outs with that pitcher.",
            "cSaveRun is the former Runs vs pitcher mix: (tRA9 - cRA9) multiplied by catcher outs and divided by 27. It is descriptive and partially shares the catcher's own observed pitcher-season results.",
            "cSaveRun/IP divides cSaveRun by catcher innings (outs / 3); it is not annualized and is not a causal catcher-runs-saved rate.",
            "Leave-catcher-out rates and coverage are retained only as diagnostics; they do not control main ranking eligibility.",
            "Automatic extra-inning runners without a reach-PA catcher remain outside catcher R/ER totals and are not imputed.",
        ],
    }
    _atomic_write_json(metrics_json_path(year, root), payload)
    return payload


def get_catcher_descriptive_leaderboard(
    year: int,
    minimum_outs: int = 0,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    """Return the season leaderboard with versioned reliability, xERA, and defense sidecars."""
    path = metrics_json_path(year, data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Catcher descriptive metrics are unavailable for {int(year)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    from app.services.catcher_descriptive_reliability_service import get_catcher_descriptive_reliability_rows

    reliability_rows, reliability_payload = get_catcher_descriptive_reliability_rows(year, data_dir)
    reliability_fields = (
        "dominant_pitcher_id",
        "dominant_pitcher_name",
        "dominant_pair_outs",
        "dominant_pair_ip",
        "dominant_pair_out_share_pct",
        "non_dominant_outs",
        "non_dominant_ip",
        "without_dominant_c_ra9",
        "without_dominant_t_ra9",
        "without_dominant_c_save_run",
        "without_dominant_c_save_run_per_ip",
        "dominant_pair_delta_c_save_run_per_ip",
        "dominant_pair_sensitivity_status",
        "adjacent_eligible_seasons",
        "adjacent_eligible_season_count",
        "reliability_tier",
        "reliability_reasons",
    )
    for row in payload.get("rows", []):
        reliability = reliability_rows.get(int(row.get("catcher_id") or 0))
        if reliability:
            row.update({field: reliability.get(field) for field in reliability_fields})
    if reliability_payload is not None:
        payload["reliability"] = {
            "contract_version": reliability_payload["contract_version"],
            "generated_at_utc": reliability_payload["generated_at_utc"],
            "release_gate_passed": reliability_payload["cross_year"]["release_gate_passed"],
            "pooled_cross_year": reliability_payload["cross_year"]["pooled"],
            "tier_counts": reliability_payload["summary"]["reliability_tier_counts"],
        }
        payload.setdefault("warnings", []).extend(reliability_payload.get("warnings", []))
    from app.services.catcher_descriptive_xera_service import get_catcher_xera_rows

    xera_rows, xera_payload = get_catcher_xera_rows(year, data_dir)
    for row in payload.get("rows", []):
        xera = xera_rows.get(int(row.get("catcher_id") or 0))
        if xera:
            row.update(
                {
                    "cxera": _round(xera.get("cxera")),
                    "txera": _round(xera.get("txera")),
                    "x_runs_vs_mix": _round(xera.get("x_runs_vs_mix")),
                    "x_runs_vs_mix_per_ip": _round(xera.get("x_runs_vs_mix_per_ip"), 6),
                    "xera_expected_runs": _round(xera.get("xera_expected_runs"), 6),
                    "pitcher_mix_expected_runs": _round(xera.get("pitcher_mix_expected_runs"), 6),
                    "xera_source_coverage_pct": _round(xera.get("source_coverage_pct"), 4),
                    "xera_status": xera.get("xera_status"),
                    "xera_model_version": xera_payload.get("model_version") if xera_payload else None,
                }
            )
    if xera_payload is not None:
        payload["xera"] = {
            "contract_version": xera_payload["contract_version"],
            "model_version": xera_payload["model_version"],
            "built_at_utc": xera_payload["built_at_utc"],
            "release_gate_passed": xera_payload["release_gate_passed"],
            "selected_model": xera_payload["selected_model"],
            "evaluation": xera_payload["evaluation"],
            "source_coverage": xera_payload["source_coverage"],
            "definitions": xera_payload["definitions"],
            "warnings": xera_payload.get("warnings", []),
        }
        payload.setdefault("warnings", []).extend(xera_payload.get("warnings", []))
    from app.services.catcher_descriptive_defense_service import get_catcher_defense_rows

    defense_rows, defense_payload = get_catcher_defense_rows(year, data_dir)
    defense_fields = (
        "drs",
        "rsz",
        "rcera",
        "rsb",
        "rgfp",
        "frm",
        "frv",
        "throwing",
        "blocking",
        "framing",
        "defense_value",
        "drs_status",
        "frv_status",
        "source_innings_status",
        "source_display_ip",
        "outs_difference",
    )
    for row in payload.get("rows", []):
        defense = defense_rows.get(int(row.get("catcher_id") or 0))
        if defense:
            row.update({field: defense.get(field) for field in defense_fields})
    if defense_payload is not None:
        payload["defense"] = {
            "contract_version": defense_payload["contract_version"],
            "generated_at_utc": defense_payload["generated_at_utc"],
            "release_gate_passed": defense_payload["release_gate_passed"],
            "source_snapshot": defense_payload["source_snapshot"],
            "comparison_source_snapshot": defense_payload.get("comparison_source_snapshot"),
            "source_field_coverage": defense_payload.get("source_field_coverage", {}),
            "row_counts": defense_payload["row_counts"],
            "cross_source_reconciliation": defense_payload.get("cross_source_reconciliation", {}),
            "reconciliation": defense_payload["reconciliation"],
            "cross_year_diagnostics": defense_payload["cross_year_diagnostics"],
            "overlap_diagnostics": defense_payload.get("overlap_diagnostics", {}),
            "definitions": defense_payload["definitions"],
            "park_factor_status": "deferred_by_user",
            "paired_duo_status": "unavailable_season_level_only",
            "warnings": defense_payload.get("warnings", []),
        }
        payload.setdefault("warnings", []).extend(defense_payload.get("warnings", []))
    payload["rows"] = [row for row in payload.get("rows", []) if int(row.get("outs") or 0) >= int(minimum_outs)]
    payload["filters"] = {"minimum_outs": int(minimum_outs)}
    return payload


def get_catcher_descriptive_paired_duo_leaderboard(
    year: int,
    minimum_outs: int = 120,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    payload = get_catcher_descriptive_leaderboard(year, data_dir=data_dir)
    path = pair_parquet_path(year, data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Pitcher-catcher pair metrics are unavailable for {int(year)}")

    pairs = pd.read_parquet(path)
    from app.services.catcher_descriptive_xera_service import get_pair_xera_rows

    xera_rows = get_pair_xera_rows(year, data_dir)
    pairs = pairs.loc[pairs["outs"].astype(int) >= int(minimum_outs)].copy()
    pairs = pairs.sort_values(["pair_c_save_run", "outs"], ascending=[False, False], na_position="last")
    rows: list[dict[str, Any]] = []
    for rank, pair in enumerate(pairs.itertuples(), start=1):
        catcher_id = int(pair.catcher_id)
        pitcher_id = int(pair.pitcher_id)
        team_codes = sorted({code for code in str(pair.teams).split(", ") if code})
        row = {
                "rank": rank,
                "pair_key": f"{int(year)}:{pitcher_id}:{catcher_id}",
                "season": int(year),
                "catcher_id": catcher_id,
                "catcher_name": str(pair.catcher_name),
                "pitcher_id": pitcher_id,
                "pitcher_name": str(pair.pitcher_name),
                "team": team_codes[0] if len(team_codes) == 1 else f"{len(team_codes)} Tms",
                "teams": team_codes,
                "games": int(pair.games),
                "outs": int(pair.outs),
                "display_ip": str(pair.display_ip),
                "bf": int(pair.bf),
                "pitcher_charged_runs": int(pair.pitcher_charged_runs),
                "earned_runs": int(pair.earned_runs),
                "home_runs": int(pair.home_runs),
                "walks_total": int(pair.walks_total),
                "hit_by_pitch": int(pair.hit_by_pitch),
                "strikeouts": int(pair.strikeouts),
                "c_era": _round(pair.c_era),
                "c_ra9": _round(pair.c_ra9),
                "c_fip": _round(pair.c_fip),
                "t_era": _round(pair.pitcher_season_era),
                "t_ra9": _round(pair.pitcher_season_ra9),
                "t_fip": _round(pair.pitcher_season_fip),
                "c_save_run": _round(pair.pair_c_save_run),
                "c_save_run_per_ip": _round(pair.pair_c_save_run_per_ip, 6),
                "lco_outs": int(pair.lco_outs),
                "lco_display_ip": _display_ip(int(pair.lco_outs)),
                "lco_era": _round(pair.lco_era),
                "lco_ra9": _round(pair.lco_ra9),
                "lco_fip": _round(pair.lco_fip),
                "lco_c_save_run": _round(pair.lco_pair_c_save_run),
                "lco_status": "available" if bool(pair.baseline_supported) else "unavailable",
            }
        xera = xera_rows.get((pitcher_id, catcher_id))
        if xera:
            row.update(
                {
                    "xera": _round(xera.get("pair_xera")),
                    "pitcher_xera": _round(xera.get("pitcher_xera")),
                    "x_runs_vs_mix": _round(xera.get("x_runs_vs_pitcher_mix")),
                    "x_runs_vs_mix_per_ip": _round(xera.get("x_runs_vs_pitcher_mix_per_ip"), 6),
                    "xera_expected_runs": _round(xera.get("xera_expected_runs"), 6),
                    "xera_source_coverage_pct": _round(xera.get("source_coverage_pct"), 4),
                    "xera_status": xera.get("xera_status"),
                }
            )
        rows.append(row)

    return {
        "contract_version": payload["contract_version"],
        "publication_status": payload["publication_status"],
        "view": "paired_duo",
        "year": int(year),
        "generated_at_utc": payload["generated_at_utc"],
        "fip_constant": payload["fip_constant"],
        "qualification": {
            "minimum_pair_outs": int(minimum_outs),
            "minimum_pair_ip": int(minimum_outs) / 3,
        },
        "summary": {"pairs": len(rows)},
        "filters": {"minimum_outs": int(minimum_outs)},
        "rows": rows,
        "warnings": payload["warnings"],
    }


def get_catcher_descriptive_detail(
    year: int,
    catcher_id: int,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    payload = get_catcher_descriptive_leaderboard(year, data_dir=data_dir)
    row = next((item for item in payload.get("rows", []) if int(item.get("catcher_id") or 0) == int(catcher_id)), None)
    if row is None:
        raise KeyError(f"Catcher {int(catcher_id)} is unavailable for {int(year)}")
    pairs = pd.read_parquet(pair_parquet_path(year, data_dir))
    from app.services.catcher_descriptive_xera_service import get_pair_xera_rows

    xera_rows = get_pair_xera_rows(year, data_dir)
    pairs = pairs.loc[pairs["catcher_id"].astype(int) == int(catcher_id)].sort_values("outs", ascending=False)
    pair_rows = []
    for pair in pairs.itertuples():
        pair_row = {
                "pitcher_id": int(pair.pitcher_id),
                "pitcher_name": pair.pitcher_name,
                "teams": pair.teams,
                "outs": int(pair.outs),
                "display_ip": pair.display_ip,
                "bf": int(pair.bf),
                "pitcher_charged_runs": int(pair.pitcher_charged_runs),
                "earned_runs": int(pair.earned_runs),
                "c_era": _round(pair.c_era),
                "c_ra9": _round(pair.c_ra9),
                "c_fip": _round(pair.c_fip),
                "pitcher_season_era": _round(pair.pitcher_season_era),
                "pitcher_season_ra9": _round(pair.pitcher_season_ra9),
                "pitcher_season_fip": _round(pair.pitcher_season_fip),
                "lco_outs": int(pair.lco_outs),
                "lco_display_ip": _display_ip(int(pair.lco_outs)),
                "lco_era": _round(pair.lco_era),
                "lco_ra9": _round(pair.lco_ra9),
                "lco_fip": _round(pair.lco_fip),
                "c_save_run": _round(pair.pair_c_save_run),
                "c_save_run_per_ip": _round(pair.pair_c_save_run_per_ip, 6),
                "lco_c_save_run": _round(pair.lco_pair_c_save_run),
                "lco_status": "available" if bool(pair.baseline_supported) else "unavailable",
            }
        xera = xera_rows.get((int(pair.pitcher_id), int(pair.catcher_id)))
        if xera:
            pair_row.update(
                {
                    "xera": _round(xera.get("pair_xera")),
                    "pitcher_xera": _round(xera.get("pitcher_xera")),
                    "x_runs_vs_mix": _round(xera.get("x_runs_vs_pitcher_mix")),
                    "x_runs_vs_mix_per_ip": _round(xera.get("x_runs_vs_pitcher_mix_per_ip"), 6),
                    "xera_expected_runs": _round(xera.get("xera_expected_runs"), 6),
                    "xera_source_coverage_pct": _round(xera.get("source_coverage_pct"), 4),
                    "xera_status": xera.get("xera_status"),
                }
            )
        pair_rows.append(pair_row)
    return {
        "contract_version": payload["contract_version"],
        "publication_status": payload["publication_status"],
        "year": int(year),
        "catcher": row,
        "pitcher_pairs": pair_rows,
        "fip_constant": payload["fip_constant"],
        "qualification": payload["qualification"],
        "warnings": payload["warnings"],
    }
