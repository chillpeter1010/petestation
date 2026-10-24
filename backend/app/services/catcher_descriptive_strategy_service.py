from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from app.core.config import settings


CONTRACT_VERSION = "catcher_descriptive_slice8_strategy_bridge_v1"
SOURCE_YEAR = 2026
DEFAULT_PROPENSITY_THRESHOLD = 0.025
MIN_SUPPORTED_DECISIONS = 500


def slice8_root(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "research" / "catcher_descriptive" / "slice8_strategy"


def strategy_json_path(data_dir: Path | None = None) -> Path:
    return slice8_root(data_dir) / "catcher_descriptive_slice8_strategy_bridge.json"


def strategy_parquet_path(data_dir: Path | None = None) -> Path:
    return slice8_root(data_dir) / "catcher_strategy_bridge_2026.parquet"


def _derived_path(filename: str, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / filename


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _number(value: Any, digits: int = 6) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _load_manifest(path: Path, expected_contract: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required frozen strategy manifest is unavailable: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contract_version") != expected_contract:
        raise ValueError(f"Unexpected strategy contract in {path.name}: {payload.get('contract_version')}")
    if payload.get("status") != "ready":
        raise ValueError(f"Frozen strategy manifest is not ready: {path}")
    return payload


def _verify_fingerprint(path: Path, expected: str | None) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Required frozen strategy artifact is unavailable: {path}")
    actual = _sha256(path)
    if not expected or actual != expected:
        raise ValueError(f"Frozen strategy artifact fingerprint mismatch: {path.name}")
    return actual


def build_catcher_descriptive_slice8_strategy_bridge(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    slice6c_manifest_path = _derived_path("player_archetype_slice6c.json", root)
    slice6d_manifest_path = _derived_path("player_archetype_slice6d.json", root)
    decisions_path = _derived_path("player_archetype_slice6c_decision_values_2026.parquet", root)
    diagnostics_path = _derived_path("player_archetype_slice6d_decision_diagnostics_2026.parquet", root)

    slice6c = _load_manifest(slice6c_manifest_path, "player_archetype_slice6c_supported_value_v1")
    slice6d = _load_manifest(slice6d_manifest_path, "player_archetype_slice6d_game_theory_diagnostics_v1")
    decision_sha = _verify_fingerprint(decisions_path, slice6c.get("artifacts", {}).get("decision_values_2026_sha256"))
    diagnostic_sha = _verify_fingerprint(diagnostics_path, slice6d.get("artifacts", {}).get("decision_diagnostics_sha256"))

    with duckdb.connect() as connection:
        totals = connection.execute(
            """
            SELECT
                CAST(catcher_id AS BIGINT) AS catcher_id,
                COUNT(*) AS total_decisions,
                COUNT(DISTINCT pitcher_id) AS pitchers
            FROM read_parquet(?)
            GROUP BY catcher_id
            ORDER BY catcher_id
            """,
            [str(decisions_path)],
        ).fetchdf()
        aggregates = connection.execute(
            """
            SELECT
                CAST(catcher_id AS BIGINT) AS catcher_id,
                COUNT(*) AS supported_set_decisions,
                SUM(CASE WHEN chosen_supported THEN 1 ELSE 0 END) AS chosen_supported_decisions,
                AVG(normalized_entropy) AS mean_normalized_entropy,
                AVG(effective_supported_choices) AS mean_effective_supported_choices,
                AVG(top_supported_probability) AS mean_top_supported_probability,
                AVG(supported_deviation_gain) AS mean_supported_deviation_gain,
                AVG(CASE WHEN chosen_supported THEN chosen_gap_vs_best_supported END) AS mean_chosen_gap_vs_best_supported,
                AVG(CASE WHEN observed_choice_is_model_minimum THEN 1.0 ELSE 0.0 END) AS observed_choice_model_minimum_rate,
                SUM(CASE WHEN deviation_exceeds_noise_floor THEN 1 ELSE 0 END) AS deviations_exceeding_noise_floor
            FROM read_parquet(?)
            WHERE CAST(propensity_threshold AS DOUBLE) = ?
            GROUP BY catcher_id
            ORDER BY catcher_id
            """,
            [str(diagnostics_path), DEFAULT_PROPENSITY_THRESHOLD],
        ).fetchdf()
        count_tiers = connection.execute(
            """
            SELECT
                CAST(catcher_id AS BIGINT) AS catcher_id,
                count_tier,
                COUNT(*) AS decisions,
                AVG(normalized_entropy) AS mean_normalized_entropy,
                AVG(effective_supported_choices) AS mean_effective_supported_choices,
                AVG(supported_deviation_gain) AS mean_supported_deviation_gain,
                AVG(CASE WHEN observed_choice_is_model_minimum THEN 1.0 ELSE 0.0 END) AS observed_choice_model_minimum_rate
            FROM read_parquet(?)
            WHERE CAST(propensity_threshold AS DOUBLE) = ?
            GROUP BY catcher_id, count_tier
            ORDER BY catcher_id, count_tier
            """,
            [str(diagnostics_path), DEFAULT_PROPENSITY_THRESHOLD],
        ).fetchdf()
        duplicate_decisions = int(
            connection.execute(
                """
                SELECT COUNT(*) - COUNT(DISTINCT decision_id)
                FROM read_parquet(?)
                WHERE CAST(propensity_threshold AS DOUBLE) = ?
                """,
                [str(diagnostics_path), DEFAULT_PROPENSITY_THRESHOLD],
            ).fetchone()[0]
        )

    merged = totals.merge(aggregates, on="catcher_id", how="left", validate="one_to_one")
    tier_lookup: dict[int, list[dict[str, Any]]] = {}
    for tier in count_tiers.itertuples(index=False):
        tier_lookup.setdefault(int(tier.catcher_id), []).append(
            {
                "count_tier": str(tier.count_tier),
                "decisions": int(tier.decisions),
                "mean_normalized_entropy": _number(tier.mean_normalized_entropy),
                "mean_effective_supported_choices": _number(tier.mean_effective_supported_choices),
                "mean_supported_deviation_gain": _number(tier.mean_supported_deviation_gain),
                "observed_choice_model_minimum_rate_pct": _number(tier.observed_choice_model_minimum_rate * 100.0, 3),
            }
        )

    rows: list[dict[str, Any]] = []
    for record in merged.to_dict(orient="records"):
        total = int(record["total_decisions"])
        supported = int(record["supported_set_decisions"]) if pd.notna(record["supported_set_decisions"]) else 0
        chosen_supported = int(record["chosen_supported_decisions"]) if pd.notna(record["chosen_supported_decisions"]) else 0
        rows.append(
            {
                "season": SOURCE_YEAR,
                "catcher_id": int(record["catcher_id"]),
                "total_decisions": total,
                "pitchers": int(record["pitchers"]),
                "supported_set_decisions": supported,
                "supported_set_coverage_pct": _number(100.0 * supported / total if total else None, 3),
                "chosen_supported_decisions": chosen_supported,
                "chosen_supported_coverage_pct": _number(100.0 * chosen_supported / total if total else None, 3),
                "chosen_support_rate_pct": _number(100.0 * chosen_supported / supported if supported else None, 3),
                "mean_normalized_entropy": _number(record.get("mean_normalized_entropy")),
                "mean_effective_supported_choices": _number(record.get("mean_effective_supported_choices")),
                "mean_top_supported_probability_pct": _number(
                    100.0 * record["mean_top_supported_probability"] if pd.notna(record.get("mean_top_supported_probability")) else None,
                    3,
                ),
                "mean_supported_deviation_gain": _number(record.get("mean_supported_deviation_gain")),
                "mean_chosen_gap_vs_best_supported": _number(record.get("mean_chosen_gap_vs_best_supported")),
                "observed_choice_model_minimum_rate_pct": _number(
                    100.0 * record["observed_choice_model_minimum_rate"] if pd.notna(record.get("observed_choice_model_minimum_rate")) else None,
                    3,
                ),
                "deviations_exceeding_noise_floor": int(record["deviations_exceeding_noise_floor"]),
                "sample_status": "available" if supported >= MIN_SUPPORTED_DECISIONS else "limited",
                "count_tiers": tier_lookup.get(int(record["catcher_id"]), []),
            }
        )

    diagnostics_total = sum(row["supported_set_decisions"] for row in rows)
    decisions_total = sum(row["total_decisions"] for row in rows)
    expected_diagnostics_total = next(
        int(item["decisions"])
        for item in slice6d.get("threshold_sensitivity", [])
        if float(item.get("propensity_threshold", -1)) == DEFAULT_PROPENSITY_THRESHOLD
    )
    expected_decisions_total = int(slice6c.get("audit", {}).get("decisions", -1))
    release_gate = {
        "input_fingerprints_match": True,
        "duplicate_default_threshold_decisions": duplicate_decisions,
        "decision_total_matches_slice6c": decisions_total == expected_decisions_total,
        "diagnostic_total_matches_slice6d": diagnostics_total == expected_diagnostics_total,
        "all_entropy_in_unit_interval": all(
            row["mean_normalized_entropy"] is None or 0.0 <= row["mean_normalized_entropy"] <= 1.0 for row in rows
        ),
        "no_deviation_exceeds_noise_floor": sum(row["deviations_exceeding_noise_floor"] for row in rows) == 0,
        "leaderboard_enabled": False,
        "composite_score_enabled": False,
        "individual_pitch_advice_enabled": False,
    }
    release_gate_passed = all(
        (
            release_gate["input_fingerprints_match"],
            release_gate["duplicate_default_threshold_decisions"] == 0,
            release_gate["decision_total_matches_slice6c"],
            release_gate["diagnostic_total_matches_slice6d"],
            release_gate["all_entropy_in_unit_interval"],
            release_gate["no_deviation_exceeds_noise_floor"],
            not release_gate["leaderboard_enabled"],
            not release_gate["composite_score_enabled"],
            not release_gate["individual_pitch_advice_enabled"],
        )
    )
    if not release_gate_passed:
        raise ValueError("Catcher descriptive Slice 8 release gate failed")

    frame = pd.DataFrame([{key: value for key, value in row.items() if key != "count_tiers"} for row in rows])
    _atomic_write_parquet(strategy_parquet_path(root), frame)
    payload = {
        "contract_version": CONTRACT_VERSION,
        "status": "ready",
        "publication_status": "research_only_no_leaderboard",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "year": SOURCE_YEAR,
        "source_contracts": {
            "supported_value": slice6c["contract_version"],
            "game_theory_diagnostics": slice6d["contract_version"],
        },
        "source_artifacts": {
            "decision_values": str(decisions_path),
            "decision_values_sha256": decision_sha,
            "decision_diagnostics": str(diagnostics_path),
            "decision_diagnostics_sha256": diagnostic_sha,
        },
        "method": {
            "propensity_threshold": DEFAULT_PROPENSITY_THRESHOLD,
            "minimum_supported_decisions": MIN_SUPPORTED_DECISIONS,
            "grain": "season-catcher context plus count-tier diagnostics",
            "normalized_entropy": "Frozen Slice 5 pitch-choice belief entropy divided by log(supported choices); 0 is concentrated and 1 is even mixing.",
            "supported_deviation_gain": "One-sided model comparison within supported choices; it is not true exploitability or causal catcher value.",
        },
        "summary": {
            "catchers": len(rows),
            "total_decisions": decisions_total,
            "supported_set_decisions": diagnostics_total,
            "available_catchers": sum(row["sample_status"] == "available" for row in rows),
            "limited_catchers": sum(row["sample_status"] == "limited" for row in rows),
        },
        "release_gate": release_gate,
        "release_gate_passed": release_gate_passed,
        "rows": rows,
        "warnings": [
            "Only 2026 has the frozen Slice 6C/6D strategy artifacts required by this bridge.",
            "The catcher ID identifies the on-field catcher context, not who selected the pitch.",
            "Normalized entropy is a descriptive predictability diagnostic and failed the entropy-leaderboard stability gate.",
            "Supported deviation is a one-sided observational model comparison, not true game-theory exploitability.",
            "No individual best-pitch label, catcher ranking, composite score, or causal pitch-calling value is released.",
        ],
    }
    _atomic_write_json(strategy_json_path(root), payload)
    return payload


def get_catcher_descriptive_strategy_bridge(
    year: int,
    catcher_id: int,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    if int(year) != SOURCE_YEAR:
        return {
            "contract_version": CONTRACT_VERSION,
            "publication_status": "research_only_no_leaderboard",
            "year": int(year),
            "catcher_id": int(catcher_id),
            "status": "unavailable",
            "reason": "Frozen model-consistent strategy diagnostics are currently available for 2026 only.",
            "row": None,
            "warnings": ["Unavailable seasons are not imputed from 2026 or assigned an Average value."],
        }
    path = strategy_json_path(data_dir)
    if not path.exists():
        raise FileNotFoundError("Catcher descriptive Slice 8 strategy bridge has not been built")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("release_gate_passed"):
        raise ValueError("Catcher descriptive Slice 8 strategy bridge has not passed its release gate")
    row = next((item for item in payload.get("rows", []) if int(item["catcher_id"]) == int(catcher_id)), None)
    return {
        "contract_version": payload["contract_version"],
        "publication_status": payload["publication_status"],
        "year": SOURCE_YEAR,
        "catcher_id": int(catcher_id),
        "status": row.get("sample_status", "limited") if row else "unavailable",
        "reason": None if row else "No frozen 2026 strategy decisions were linked to this catcher context.",
        "method": payload["method"],
        "release_gate": payload["release_gate"],
        "row": row,
        "warnings": payload["warnings"],
    }
