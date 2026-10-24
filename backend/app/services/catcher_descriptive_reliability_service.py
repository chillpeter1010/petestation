from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from app.core.config import settings
from app.services.catcher_descriptive_metrics_service import (
    MIN_RANKING_OUTS,
    metrics_json_path,
    pair_parquet_path,
)


CONTRACT_VERSION = "catcher_descriptive_slice4_reliability_v1"
DEFAULT_YEARS = (2021, 2022, 2023, 2024, 2025, 2026)
MIN_ADJACENT_PAIRS = 100
MIN_RELIABILITY_CORRELATION = 0.20
MIN_NON_DOMINANT_OUTS = 600
MAX_DOMINANT_SENSITIVITY_PER_IP = 0.02
BOOTSTRAP_SAMPLES = 2_000
BOOTSTRAP_SEED = 20261020


def slice4_root(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "research" / "catcher_descriptive" / "slice4_reliability"


def reliability_json_path(data_dir: Path | None = None) -> Path:
    return slice4_root(data_dir) / "catcher_descriptive_slice4_reliability.json"


def reliability_parquet_path(data_dir: Path | None = None) -> Path:
    return slice4_root(data_dir) / "catcher_descriptive_slice4_reliability.parquet"


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: float | int | None, digits: int = 6) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _correlation(left: pd.Series, right: pd.Series, method: str) -> float | None:
    if len(left) < 3 or left.nunique() < 2 or right.nunique() < 2:
        return None
    value = left.corr(right, method=method)
    return _number(value)


def _correlation_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "adjacent_pairs": 0,
            "pearson": None,
            "spearman": None,
            "same_sign_pct": None,
            "mean_absolute_change_per_ip": None,
        }
    left = frame["c_save_run_per_ip_from"].astype(float)
    right = frame["c_save_run_per_ip_to"].astype(float)
    same_sign = ((left > 0) == (right > 0)).mean() * 100.0
    return {
        "adjacent_pairs": int(len(frame)),
        "pearson": _correlation(left, right, "pearson"),
        "spearman": _correlation(left, right, "spearman"),
        "same_sign_pct": _number(same_sign, 2),
        "mean_absolute_change_per_ip": _number((right - left).abs().mean()),
    }


def _cluster_bootstrap_pearson(frame: pd.DataFrame) -> dict[str, Any]:
    catcher_ids = frame["catcher_id"].drop_duplicates().astype(int).to_numpy()
    if len(catcher_ids) < 3:
        return {"samples": 0, "seed": BOOTSTRAP_SEED, "ci_level": 0.95, "low": None, "high": None}
    grouped = {int(catcher_id): group for catcher_id, group in frame.groupby("catcher_id")}
    generator = np.random.default_rng(BOOTSTRAP_SEED)
    correlations: list[float] = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sampled_ids = generator.choice(catcher_ids, size=len(catcher_ids), replace=True)
        sampled = pd.concat([grouped[int(catcher_id)] for catcher_id in sampled_ids], ignore_index=True)
        correlation = sampled["c_save_run_per_ip_from"].corr(sampled["c_save_run_per_ip_to"], method="pearson")
        if pd.notna(correlation):
            correlations.append(float(correlation))
    if not correlations:
        return {"samples": 0, "seed": BOOTSTRAP_SEED, "ci_level": 0.95, "low": None, "high": None}
    low, high = np.quantile(correlations, [0.025, 0.975])
    return {
        "samples": len(correlations),
        "seed": BOOTSTRAP_SEED,
        "ci_level": 0.95,
        "low": _number(low),
        "high": _number(high),
    }


def _load_sources(years: tuple[int, ...], root: Path) -> tuple[pd.DataFrame, dict[int, pd.DataFrame], list[dict[str, Any]]]:
    metric_rows: list[dict[str, Any]] = []
    pair_frames: dict[int, pd.DataFrame] = {}
    source_files: list[dict[str, Any]] = []
    for year in years:
        metric_path = metrics_json_path(year, root)
        pair_path = pair_parquet_path(year, root)
        for path in (metric_path, pair_path):
            if not path.exists():
                raise FileNotFoundError(f"Required Slice 2–3 artifact is unavailable: {path}")
            source_files.append({"path": str(path), "sha256": _sha256(path)})
        payload = json.loads(metric_path.read_text(encoding="utf-8"))
        metric_rows.extend(payload.get("rows", []))
        pair_frames[year] = pd.read_parquet(pair_path)
    metrics = pd.DataFrame(metric_rows)
    if metrics.duplicated(["season", "catcher_id"]).any():
        raise ValueError("Duplicate season-catcher keys in Slice 2–3 metrics")
    return metrics, pair_frames, source_files


def _build_adjacent_pairs(metrics: pd.DataFrame, years: tuple[int, ...]) -> pd.DataFrame:
    qualified = metrics.loc[metrics["ranking_eligible"].astype(bool)].copy()
    frames: list[pd.DataFrame] = []
    available_years = set(years)
    for year in years:
        if year + 1 not in available_years:
            continue
        left = qualified.loc[qualified["season"].astype(int) == year, ["catcher_id", "catcher_name", "c_save_run", "c_save_run_per_ip"]]
        right = qualified.loc[qualified["season"].astype(int) == year + 1, ["catcher_id", "catcher_name", "c_save_run", "c_save_run_per_ip"]]
        joined = left.merge(right, on="catcher_id", suffixes=("_from", "_to"))
        joined["from_year"] = year
        joined["to_year"] = year + 1
        frames.append(joined)
    if not frames:
        return pd.DataFrame(columns=[
            "catcher_id", "catcher_name_from", "catcher_name_to", "c_save_run_from", "c_save_run_to",
            "c_save_run_per_ip_from", "c_save_run_per_ip_to", "from_year", "to_year",
        ])
    return pd.concat(frames, ignore_index=True)


def _dominant_pair_result(metric: pd.Series, pairs: pd.DataFrame) -> dict[str, Any]:
    ordered = pairs.sort_values(["outs", "pitcher_id"], ascending=[False, True]).reset_index(drop=True)
    outs = int(ordered["outs"].sum())
    expected_outs = int(metric["outs"])
    if outs != expected_outs:
        raise ValueError(
            f"Pair outs do not reproduce catcher outs for {int(metric['season'])}/{int(metric['catcher_id'])}: {outs} != {expected_outs}"
        )
    dominant = ordered.iloc[0]
    remaining = ordered.iloc[1:]
    remaining_outs = int(remaining["outs"].sum())
    full_expected_runs = float((ordered["pitcher_season_ra9"] * ordered["outs"] / 27.0).sum())
    full_runs = float(ordered["pitcher_charged_runs"].sum())
    full_c_save_run = full_expected_runs - full_runs
    stored_c_save_run = float(metric["c_save_run"])
    if abs(full_c_save_run - stored_c_save_run) > 0.001:
        raise ValueError(
            f"Pair cSaveRun does not reproduce catcher row for {int(metric['season'])}/{int(metric['catcher_id'])}"
        )
    full_per_ip = full_c_save_run / (outs / 3.0) if outs else None
    without_c_ra9 = without_t_ra9 = without_c_save_run = without_per_ip = delta_per_ip = None
    sensitivity_status = "unavailable"
    if remaining_outs > 0:
        remaining_runs = float(remaining["pitcher_charged_runs"].sum())
        remaining_expected_runs = float((remaining["pitcher_season_ra9"] * remaining["outs"] / 27.0).sum())
        without_c_ra9 = 27.0 * remaining_runs / remaining_outs
        without_t_ra9 = 27.0 * remaining_expected_runs / remaining_outs
        without_c_save_run = remaining_expected_runs - remaining_runs
        without_per_ip = without_c_save_run / (remaining_outs / 3.0)
        delta_per_ip = without_per_ip - float(full_per_ip)
        if remaining_outs >= MIN_NON_DOMINANT_OUTS:
            sensitivity_status = "stable" if abs(delta_per_ip) <= MAX_DOMINANT_SENSITIVITY_PER_IP else "sensitive"
    return {
        "season": int(metric["season"]),
        "catcher_id": int(metric["catcher_id"]),
        "catcher_name": str(metric["catcher_name"]),
        "outs": outs,
        "display_ip": str(metric["display_ip"]),
        "ranking_eligible": bool(metric["ranking_eligible"]),
        "c_save_run": _number(full_c_save_run, 4),
        "c_save_run_per_ip": _number(full_per_ip),
        "dominant_pitcher_id": int(dominant["pitcher_id"]),
        "dominant_pitcher_name": str(dominant["pitcher_name"]),
        "dominant_pair_outs": int(dominant["outs"]),
        "dominant_pair_ip": f"{int(dominant['outs']) // 3}.{int(dominant['outs']) % 3}",
        "dominant_pair_out_share_pct": _number(float(dominant["outs"]) * 100.0 / outs, 2) if outs else None,
        "non_dominant_outs": remaining_outs,
        "non_dominant_ip": f"{remaining_outs // 3}.{remaining_outs % 3}",
        "without_dominant_c_ra9": _number(without_c_ra9, 4),
        "without_dominant_t_ra9": _number(without_t_ra9, 4),
        "without_dominant_c_save_run": _number(without_c_save_run, 4),
        "without_dominant_c_save_run_per_ip": _number(without_per_ip),
        "dominant_pair_delta_c_save_run_per_ip": _number(delta_per_ip),
        "dominant_pair_sensitivity_status": sensitivity_status,
    }


def build_catcher_descriptive_slice4_reliability(
    years: Iterable[int] = DEFAULT_YEARS,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    selected_years = tuple(sorted({int(year) for year in years}))
    if not selected_years:
        raise ValueError("At least one season is required")
    root = Path(data_dir or settings.data_dir)
    metrics, pair_frames, source_files = _load_sources(selected_years, root)
    adjacent = _build_adjacent_pairs(metrics, selected_years)
    pooled = _correlation_summary(adjacent)
    bootstrap = _cluster_bootstrap_pearson(adjacent)
    pooled["pearson_cluster_bootstrap_95_ci"] = bootstrap
    annual = []
    for (from_year, to_year), group in adjacent.groupby(["from_year", "to_year"], sort=True):
        result = _correlation_summary(group)
        result.update({"from_year": int(from_year), "to_year": int(to_year)})
        annual.append(result)

    release_gate_passed = bool(
        pooled["adjacent_pairs"] >= MIN_ADJACENT_PAIRS
        and pooled["pearson"] is not None
        and pooled["pearson"] >= MIN_RELIABILITY_CORRELATION
        and pooled["spearman"] is not None
        and pooled["spearman"] >= MIN_RELIABILITY_CORRELATION
        and bootstrap["low"] is not None
        and bootstrap["low"] > 0
    )

    adjacent_by_key: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for item in adjacent.to_dict("records"):
        for year, other_year, own_value, other_value in (
            (int(item["from_year"]), int(item["to_year"]), item["c_save_run_per_ip_from"], item["c_save_run_per_ip_to"]),
            (int(item["to_year"]), int(item["from_year"]), item["c_save_run_per_ip_to"], item["c_save_run_per_ip_from"]),
        ):
            adjacent_by_key.setdefault((year, int(item["catcher_id"])), []).append({
                "season": other_year,
                "c_save_run_per_ip": _number(other_value),
                "absolute_delta": _number(abs(float(other_value) - float(own_value))),
                "same_sign": bool((float(other_value) > 0) == (float(own_value) > 0)),
            })

    rows: list[dict[str, Any]] = []
    for metric in metrics.sort_values(["season", "catcher_id"]).itertuples(index=False):
        metric_series = pd.Series(metric._asdict())
        season = int(metric_series["season"])
        catcher_id = int(metric_series["catcher_id"])
        pair_frame = pair_frames[season]
        catcher_pairs = pair_frame.loc[pair_frame["catcher_id"].astype(int) == catcher_id]
        if catcher_pairs.empty:
            raise ValueError(f"Missing pair rows for {season}/{catcher_id}")
        row = _dominant_pair_result(metric_series, catcher_pairs)
        adjacent_seasons = sorted(adjacent_by_key.get((season, catcher_id), []), key=lambda item: item["season"])
        reasons: list[str] = []
        if not row["ranking_eligible"]:
            tier = "unavailable"
            reasons.append("below_300_catcher_innings")
        elif row["dominant_pair_sensitivity_status"] == "unavailable":
            tier = "unavailable"
            reasons.append("fewer_than_200_non_dominant_innings")
        else:
            if not release_gate_passed:
                reasons.append("cross_year_release_gate_failed")
            if row["dominant_pair_sensitivity_status"] == "sensitive":
                reasons.append("dominant_pair_sensitivity_exceeds_0.02_runs_per_ip")
            if not adjacent_seasons:
                reasons.append("no_adjacent_eligible_season")
            tier = "supported" if not reasons else "limited"
        row.update({
            "adjacent_eligible_seasons": adjacent_seasons,
            "adjacent_eligible_season_count": len(adjacent_seasons),
            "reliability_tier": tier,
            "reliability_reasons": reasons,
        })
        rows.append(row)

    row_frame = pd.DataFrame(rows)
    _atomic_write_parquet(reliability_parquet_path(root), row_frame.drop(columns=["adjacent_eligible_seasons", "reliability_reasons"]))
    tier_counts = row_frame["reliability_tier"].value_counts().to_dict()
    sensitivity_counts = row_frame["dominant_pair_sensitivity_status"].value_counts().to_dict()
    qualified = row_frame.loc[row_frame["ranking_eligible"]]
    payload = {
        "contract_version": CONTRACT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "years": list(selected_years),
        "source_files": source_files,
        "method": {
            "cross_year_metric": "cSaveRun/IP among catchers with at least 900 outs in both adjacent seasons",
            "pooled_unit": "one catcher adjacent-season pair",
            "bootstrap_unit": "catcher_id cluster",
            "dominant_pair_test": "remove the pitcher with the most paired outs, then recompute cRA9, tRA9, cSaveRun and cSaveRun/IP from the remaining pairs",
            "tier_rule": "supported requires the global cross-year gate, at least one adjacent eligible season, and a stable dominant-pair test; below 300 IP or fewer than 200 non-dominant IP is unavailable; all other rows are limited",
        },
        "thresholds": {
            "minimum_ranking_outs": MIN_RANKING_OUTS,
            "minimum_adjacent_pairs": MIN_ADJACENT_PAIRS,
            "minimum_pearson_and_spearman": MIN_RELIABILITY_CORRELATION,
            "minimum_non_dominant_outs": MIN_NON_DOMINANT_OUTS,
            "maximum_absolute_dominant_pair_delta_per_ip": MAX_DOMINANT_SENSITIVITY_PER_IP,
        },
        "cross_year": {
            "pooled": pooled,
            "by_adjacent_season": annual,
            "release_gate_passed": release_gate_passed,
        },
        "dominant_pair": {
            "qualified_rows": int(len(qualified)),
            "qualified_stable_rows": int((qualified["dominant_pair_sensitivity_status"] == "stable").sum()),
            "qualified_sensitive_rows": int((qualified["dominant_pair_sensitivity_status"] == "sensitive").sum()),
            "qualified_unavailable_rows": int((qualified["dominant_pair_sensitivity_status"] == "unavailable").sum()),
            "all_row_status_counts": {str(key): int(value) for key, value in sensitivity_counts.items()},
        },
        "summary": {
            "catcher_seasons": len(rows),
            "ranking_eligible_catcher_seasons": int(row_frame["ranking_eligible"].sum()),
            "reliability_tier_counts": {str(key): int(value) for key, value in tier_counts.items()},
            "individual_catcher_value_release_ready": False,
        },
        "rows": rows,
        "warnings": [
            "cSaveRun and cSaveRun/IP remain observed pitcher-mix associations, not causal catcher value.",
            "The cross-year release gate applies to the metric as a whole; a stable dominant-pair result does not override a failed cross-year gate.",
            "No row is annualized, shrunk into a precise estimate, or promoted to supported when an adjacent season is unavailable.",
        ],
    }
    _atomic_write_json(reliability_json_path(root), payload)
    return payload


def get_catcher_descriptive_reliability(data_dir: Path | None = None) -> dict[str, Any]:
    path = reliability_json_path(data_dir)
    if not path.exists():
        raise FileNotFoundError("Catcher descriptive Slice 4 reliability artifact is unavailable")
    return json.loads(path.read_text(encoding="utf-8"))


def get_catcher_descriptive_reliability_rows(
    year: int,
    data_dir: Path | None = None,
) -> tuple[dict[int, dict[str, Any]], dict[str, Any] | None]:
    path = reliability_json_path(data_dir)
    if not path.exists():
        return {}, None
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = {
        int(row["catcher_id"]): row
        for row in payload.get("rows", [])
        if int(row.get("season") or 0) == int(year)
    }
    return rows, payload
