from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from app.core.config import settings
from app.services.player_archetype_slice6ab_service import _copy_atomic, _number, _sql_path
from app.services.player_archetype_slice6c_service import (
    DEFAULT_PROPENSITY,
    MIN_THREAT_PITCHES,
    MIN_WEAPON_PITCHES,
    _sha256,
    get_player_archetype_slice6c,
    slice6c_candidate_value_path,
)


CONTRACT_VERSION = "player_archetype_slice6d_game_theory_diagnostics_v1"
BOOTSTRAP_RESAMPLES = 200
BOOTSTRAP_SEED = 20261016
MIN_SUBGROUP_DECISIONS = 500


def slice6d_contract_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice6d.json"


def slice6d_decision_diagnostic_path(data_dir: Path | None = None) -> Path:
    return (
        Path(data_dir or settings.data_dir)
        / "derived"
        / "player_archetype_slice6d_decision_diagnostics_2026.parquet"
    )


def slice6d_subgroup_path(data_dir: Path | None = None) -> Path:
    return (
        Path(data_dir or settings.data_dir)
        / "derived"
        / "player_archetype_slice6d_subgroup_diagnostics_2026.parquet"
    )


def slice6d_report_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "PLAYER_ARCHETYPES_PITCH_STRATEGY.md"


def _threshold_values(thresholds: list[float]) -> str:
    return ", ".join(f"({float(value)})" for value in thresholds)


def _decision_diagnostic_query(candidate_path: Path, thresholds: list[float]) -> str:
    candidate = _sql_path(candidate_path)
    return f"""
        WITH threshold_values(propensity_threshold) AS (
            VALUES {_threshold_values(thresholds)}
        ),
        eligible AS (
            SELECT c.*, t.propensity_threshold
            FROM read_parquet('{candidate}') c
            CROSS JOIN threshold_values t
            WHERE c.pregame_type_pitches >= {MIN_WEAPON_PITCHES}
              AND c.threat_pitches >= {MIN_THREAT_PITCHES}
              AND c.candidate_propensity >= t.propensity_threshold
        ),
        normalized AS (
            SELECT *,
                   count(*) OVER decision_window AS supported_candidates,
                   sum(candidate_propensity) OVER decision_window AS supported_probability_mass,
                   candidate_propensity
                     / nullif(sum(candidate_propensity) OVER decision_window, 0) AS supported_probability
            FROM eligible
            WINDOW decision_window AS (PARTITION BY propensity_threshold, decision_id)
        ),
        two_plus AS (
            SELECT * FROM normalized WHERE supported_candidates >= 2
        ),
        aggregated AS (
            SELECT propensity_threshold, decision_id,
                   any_value(game_date) AS game_date,
                   any_value(game_pk) AS game_pk,
                   any_value(at_bat_number) AS at_bat_number,
                   any_value(pitch_number) AS pitch_number,
                   any_value(pitcher_id) AS pitcher_id,
                   any_value(batter_id) AS batter_id,
                   any_value(catcher_id) AS catcher_id,
                   any_value(pitcher_throws) AS pitcher_throws,
                   any_value(batter_side) AS batter_side,
                   any_value(pitcher_role) AS pitcher_role,
                   any_value(count_state) AS count_state,
                   any_value(count_tier) AS count_tier,
                   any_value(outs) AS outs,
                   any_value(base_state) AS base_state,
                   any_value(inning) AS inning,
                   max(supported_candidates) AS supported_candidates,
                   max(supported_probability_mass) AS supported_probability_mass,
                   -sum(supported_probability * ln(supported_probability)) AS shannon_entropy,
                   max(supported_probability) AS top_supported_probability,
                   sum(supported_probability * predicted_batter_run_value)
                     AS strategy_expected_batter_run_value,
                   min(predicted_batter_run_value) AS best_supported_batter_run_value,
                   max(predicted_batter_run_value) AS worst_supported_batter_run_value,
                   arg_min(candidate_pitch_type, predicted_batter_run_value)
                     AS best_supported_pitch_type,
                   bool_or(is_chosen) AS chosen_supported,
                   max(candidate_pitch_type) FILTER (WHERE is_chosen) AS chosen_pitch_type,
                   max(supported_probability) FILTER (WHERE is_chosen) AS chosen_supported_probability,
                   max(predicted_batter_run_value) FILTER (WHERE is_chosen)
                     AS chosen_predicted_batter_run_value,
                   any_value(observed_delta_run_exp) AS observed_delta_run_exp,
                   max((prediction_upper_90 - prediction_lower_90) / 2.0)
                     AS single_pitch_residual_half_width_90
            FROM two_plus
            GROUP BY propensity_threshold, decision_id
        )
        SELECT *,
               shannon_entropy / nullif(ln(supported_candidates), 0) AS normalized_entropy,
               exp(shannon_entropy) AS effective_supported_choices,
               strategy_expected_batter_run_value - best_supported_batter_run_value
                 AS supported_deviation_gain,
               worst_supported_batter_run_value - best_supported_batter_run_value
                 AS supported_value_range,
               chosen_predicted_batter_run_value - best_supported_batter_run_value
                 AS chosen_gap_vs_best_supported,
               CASE WHEN chosen_supported_probability > 0
                    THEN -ln(chosen_supported_probability) END AS chosen_surprisal,
               chosen_pitch_type = best_supported_pitch_type AS observed_choice_is_model_minimum,
               supported_deviation_gain > single_pitch_residual_half_width_90
                 AS deviation_exceeds_noise_floor,
               'one_sided_supported_deviation_not_true_exploitability' AS interpretation_scope
        FROM aggregated
        ORDER BY propensity_threshold, game_date, game_pk, at_bat_number, pitch_number
    """


def _expanded_groups(source: str) -> str:
    return f"""
        SELECT *, 'Overall' AS dimension, 'All' AS subgroup FROM {source}
        UNION ALL
        SELECT *, 'Role' AS dimension, pitcher_role AS subgroup FROM {source}
        UNION ALL
        SELECT *, 'CountTier' AS dimension, count_tier AS subgroup FROM {source}
        UNION ALL
        SELECT *, 'Platoon' AS dimension,
               pitcher_throws || '-to-' || batter_side AS subgroup FROM {source}
    """


def _subgroup_query(diagnostic_path: Path) -> str:
    diagnostic = _sql_path(diagnostic_path)
    expanded = _expanded_groups(f"read_parquet('{diagnostic}')")
    return f"""
        WITH expanded AS ({expanded})
        SELECT propensity_threshold, dimension, subgroup,
               count(*) AS decisions,
               count(DISTINCT pitcher_id) AS pitchers,
               avg(supported_probability_mass) AS mean_supported_probability_mass,
               avg(normalized_entropy) AS mean_normalized_entropy,
               avg(effective_supported_choices) AS mean_effective_supported_choices,
               avg(top_supported_probability) AS mean_top_supported_probability,
               avg(supported_deviation_gain) AS mean_supported_deviation_gain,
               avg(supported_value_range) AS mean_supported_value_range,
               avg(chosen_supported::INTEGER) AS chosen_support_rate,
               avg(observed_choice_is_model_minimum::INTEGER)
                 FILTER (WHERE chosen_supported) AS observed_choice_model_minimum_rate,
               avg(chosen_gap_vs_best_supported)
                 FILTER (WHERE chosen_supported) AS mean_chosen_gap_vs_best_supported,
               count(*) FILTER (WHERE deviation_exceeds_noise_floor)
                 AS deviations_exceeding_noise_floor
        FROM expanded
        GROUP BY propensity_threshold, dimension, subgroup
        ORDER BY propensity_threshold, dimension, subgroup
    """


def _cluster_frame(connection: duckdb.DuckDBPyConnection, diagnostic_path: Path) -> pd.DataFrame:
    diagnostic = _sql_path(diagnostic_path)
    expanded = _expanded_groups(f"read_parquet('{diagnostic}')")
    return connection.execute(
        f"""
        WITH expanded AS ({expanded})
        SELECT propensity_threshold, dimension, subgroup, pitcher_id,
               count(*) AS decisions,
               sum(normalized_entropy) AS entropy_sum,
               sum(supported_deviation_gain) AS deviation_sum
        FROM expanded
        GROUP BY propensity_threshold, dimension, subgroup, pitcher_id
        """
    ).fetchdf()


def _cluster_bootstrap_intervals(frame: pd.DataFrame) -> dict[tuple[float, str, str], dict[str, float]]:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    intervals: dict[tuple[float, str, str], dict[str, float]] = {}
    for key, group in frame.groupby(["propensity_threshold", "dimension", "subgroup"], sort=True):
        counts = group["decisions"].to_numpy(dtype=float)
        entropy = group["entropy_sum"].to_numpy(dtype=float)
        deviation = group["deviation_sum"].to_numpy(dtype=float)
        cluster_count = len(group)
        entropy_draws = np.empty(BOOTSTRAP_RESAMPLES, dtype=float)
        deviation_draws = np.empty(BOOTSTRAP_RESAMPLES, dtype=float)
        for index in range(BOOTSTRAP_RESAMPLES):
            sampled = rng.integers(0, cluster_count, size=cluster_count)
            denominator = counts[sampled].sum()
            entropy_draws[index] = entropy[sampled].sum() / denominator
            deviation_draws[index] = deviation[sampled].sum() / denominator
        intervals[(float(key[0]), str(key[1]), str(key[2]))] = {
            "entropy_lower_90": float(np.quantile(entropy_draws, 0.05)),
            "entropy_upper_90": float(np.quantile(entropy_draws, 0.95)),
            "deviation_lower_90": float(np.quantile(deviation_draws, 0.05)),
            "deviation_upper_90": float(np.quantile(deviation_draws, 0.95)),
        }
    return intervals


def _write_subgroups_with_intervals(
    connection: duckdb.DuckDBPyConnection,
    diagnostic_path: Path,
    output_path: Path,
) -> pd.DataFrame:
    subgroup_frame = connection.execute(_subgroup_query(diagnostic_path)).fetchdf()
    intervals = _cluster_bootstrap_intervals(_cluster_frame(connection, diagnostic_path))
    for name in (
        "entropy_lower_90",
        "entropy_upper_90",
        "deviation_lower_90",
        "deviation_upper_90",
    ):
        subgroup_frame[name] = [
            intervals[(float(row.propensity_threshold), str(row.dimension), str(row.subgroup))][name]
            for row in subgroup_frame.itertuples(index=False)
        ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".tmp.parquet")
    if temporary.exists():
        temporary.unlink()
    pq.write_table(pa.Table.from_pandas(subgroup_frame, preserve_index=False), temporary, compression="zstd")
    temporary.replace(output_path)
    return subgroup_frame


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        records.append(
            {
                key: (_number(value) if isinstance(value, (float, np.floating)) else value)
                for key, value in row.items()
            }
        )
    return records


def _sensitivity_summary(subgroups: pd.DataFrame) -> dict[str, Any]:
    complete = subgroups.groupby(["dimension", "subgroup"]).filter(
        lambda rows: rows["propensity_threshold"].nunique() == 4
    )
    ranges = (
        complete.groupby(["dimension", "subgroup"])
        .agg(
            entropy_range=("mean_normalized_entropy", lambda values: float(values.max() - values.min())),
            deviation_range=("mean_supported_deviation_gain", lambda values: float(values.max() - values.min())),
        )
        .reset_index()
    )
    return {
        "complete_panels": int(len(ranges)),
        "maximum_entropy_range": _number(ranges["entropy_range"].max()),
        "maximum_deviation_range": _number(ranges["deviation_range"].max()),
        "largest_entropy_shift_panel": (
            ranges.sort_values("entropy_range", ascending=False).head(1).to_dict(orient="records")[0]
            if not ranges.empty
            else None
        ),
        "largest_deviation_shift_panel": (
            ranges.sort_values("deviation_range", ascending=False).head(1).to_dict(orient="records")[0]
            if not ranges.empty
            else None
        ),
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def build_player_archetype_slice6d(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    slice6c = get_player_archetype_slice6c(root)
    candidate_path = slice6c_candidate_value_path(root)
    if not candidate_path.exists():
        raise FileNotFoundError(candidate_path)
    expected_hash = slice6c["artifacts"]["candidate_values_2026_sha256"]
    actual_hash = _sha256(candidate_path)
    if actual_hash != expected_hash:
        raise RuntimeError("Slice 6C candidate fingerprint changed; rebuild or audit 6C before Slice 6D.")
    if not slice6c["release_gate"]["aggregate_supported_value_ready"]:
        raise RuntimeError("Slice 6C aggregate supported-value gate is closed.")

    thresholds = [float(value) for value in slice6c["support_contract"]["propensity_thresholds"]]
    diagnostic_path = slice6d_decision_diagnostic_path(root)
    subgroup_path = slice6d_subgroup_path(root)
    with duckdb.connect() as connection:
        _copy_atomic(connection, _decision_diagnostic_query(candidate_path, thresholds), diagnostic_path)
        subgroup_frame = _write_subgroups_with_intervals(
            connection, diagnostic_path, subgroup_path
        )
        diagnostic = _sql_path(diagnostic_path)
        audit = connection.execute(
            f"""
            SELECT count(*) AS row_count,
                   count(*) - count(DISTINCT propensity_threshold || ':' || decision_id)
                     AS duplicates,
                   count(*) FILTER (WHERE supported_candidates < 2) AS bad_support_count,
                   count(*) FILTER (WHERE normalized_entropy < -1e-10
                                      OR normalized_entropy > 1.0000001) AS bad_entropy,
                   count(*) FILTER (WHERE effective_supported_choices < 1
                                      OR effective_supported_choices > supported_candidates + 1e-8)
                     AS bad_effective_choices,
                   count(*) FILTER (WHERE supported_deviation_gain < -1e-10) AS negative_deviation,
                   count(*) FILTER (WHERE interpretation_scope <>
                     'one_sided_supported_deviation_not_true_exploitability') AS bad_scope
            FROM read_parquet('{diagnostic}')
            """
        ).fetchone()
        threshold_rows = connection.execute(
            f"""
            SELECT propensity_threshold, count(*) decisions,
                   count(DISTINCT pitcher_id) pitchers,
                   avg(normalized_entropy) mean_normalized_entropy,
                   avg(effective_supported_choices) mean_effective_supported_choices,
                   avg(top_supported_probability) mean_top_supported_probability,
                   avg(supported_deviation_gain) mean_supported_deviation_gain,
                   avg(chosen_supported::INTEGER) chosen_support_rate,
                   count(*) FILTER (WHERE deviation_exceeds_noise_floor)
                     deviations_exceeding_noise_floor
            FROM read_parquet('{diagnostic}')
            GROUP BY propensity_threshold
            ORDER BY propensity_threshold
            """
        ).fetchdf()
        yamamoto = connection.execute(
            f"""
            SELECT * FROM read_parquet('{diagnostic}')
            WHERE abs(propensity_threshold - {DEFAULT_PROPENSITY}) < 1e-12
              AND game_pk = 823926 AND pitcher_id = 808967 AND batter_id = 543510
              AND at_bat_number = 44 AND pitch_number = 2
            """
        ).fetchdf()

    default_groups = subgroup_frame[
        np.isclose(subgroup_frame["propensity_threshold"], DEFAULT_PROPENSITY)
    ]
    undersized_default_groups = int(
        (default_groups["decisions"] < MIN_SUBGROUP_DECISIONS).sum()
    )
    sensitivity = _sensitivity_summary(subgroup_frame)
    entropy_threshold_stable = bool(sensitivity["maximum_entropy_range"] <= 0.05)
    deviation_threshold_stable = bool(sensitivity["maximum_deviation_range"] <= 0.001)
    integrity_ready = bool(
        int(audit[0]) > 0
        and all(int(value) == 0 for value in audit[1:])
        and not yamamoto.empty
    )
    payload = {
        "contract_version": CONTRACT_VERSION,
        "status": "ready" if integrity_ready else "failed_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "year": 2026,
            "input": "Frozen Slice 6C supported candidate predictions.",
            "model_refit": False,
            "post_pitch_features_allowed": False,
            "strategy_belief": "Frozen Slice 5 exact-pitch propensities renormalized within each supported set.",
        },
        "definitions": {
            "normalized_entropy": "Shannon entropy divided by log(number of supported choices); 0 is concentrated and 1 is even mixing.",
            "effective_supported_choices": "exp(Shannon entropy), interpreted as the effective number of supported pitch choices.",
            "supported_deviation_gain": "Propensity-weighted predicted batter run value minus the minimum among supported candidates; lower is better for the pitcher.",
            "true_exploitability": "Not identified: the current value model does not estimate how a batter changes response after the pitcher changes strategy.",
        },
        "uncertainty": {
            "subgroup_intervals": f"90% pitcher-cluster bootstrap intervals with {BOOTSTRAP_RESAMPLES} resamples.",
            "single_pitch_noise_source": "Frozen Slice 6C 2025-second-half residual interval.",
        },
        "audit": {
            "diagnostic_rows": int(audit[0]),
            "duplicates": int(audit[1]),
            "bad_support_count": int(audit[2]),
            "bad_entropy": int(audit[3]),
            "bad_effective_choices": int(audit[4]),
            "negative_deviation": int(audit[5]),
            "bad_interpretation_scope": int(audit[6]),
            "default_subgroups_below_minimum": undersized_default_groups,
            "minimum_subgroup_decisions": MIN_SUBGROUP_DECISIONS,
        },
        "threshold_sensitivity": _records(threshold_rows),
        "subgroup_sensitivity": sensitivity,
        "default_threshold_groups": _records(default_groups),
        "case_823926_yamamoto_mccann": _records(yamamoto),
        "release_gate": {
            "integrity_ready": integrity_ready,
            "aggregate_entropy_diagnostic_ready": bool(
                integrity_ready and undersized_default_groups == 0
            ),
            "entropy_threshold_stability_ready": entropy_threshold_stable,
            "entropy_leaderboard_ready": bool(
                integrity_ready and undersized_default_groups == 0 and entropy_threshold_stable
            ),
            "aggregate_supported_deviation_research_ready": integrity_ready,
            "supported_deviation_threshold_stability_ready": deviation_threshold_stable,
            "true_exploitability_ready": False,
            "individual_strategy_advice_ready": False,
            "research_only": True,
            "reason": "Entropy describes the frozen observed-strategy belief, while supported deviation is one-sided model comparison. Neither includes the batter best-response function required for game-theory exploitability.",
            "next_step": "If strategy research continues, fit a separately validated batter response layer before using exploitability language; otherwise integrate only entropy and supported-deviation aggregates into the research UI.",
        },
        "artifacts": {
            "slice6c_candidate_values": str(candidate_path),
            "slice6c_candidate_values_sha256": actual_hash,
            "decision_diagnostics": str(diagnostic_path),
            "decision_diagnostics_sha256": _sha256(diagnostic_path),
            "subgroup_diagnostics": str(subgroup_path),
            "subgroup_diagnostics_sha256": _sha256(subgroup_path),
        },
    }
    slice6d_contract_path(root).write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
            default=_json_default,
        ),
        encoding="utf-8",
    )
    return payload


def get_player_archetype_slice6d(data_dir: Path | None = None) -> dict[str, Any]:
    return json.loads(slice6d_contract_path(data_dir).read_text(encoding="utf-8"))


def render_slice6d_report(payload: dict[str, Any]) -> str:
    default = next(
        row
        for row in payload["threshold_sensitivity"]
        if abs(row["propensity_threshold"] - DEFAULT_PROPENSITY) < 1e-12
    )
    case = payload["case_823926_yamamoto_mccann"][0]
    sensitivity = payload["subgroup_sensitivity"]
    return "\n".join(
        [
            "# Player Archetypes Slice 6D — Game-Theory Diagnostics",
            "",
            f"Contract: `{payload['contract_version']}`  ",
            f"Status: **{payload['status']}**  ",
            "",
            "## What is measured",
            "",
            "- Entropy measures how concentrated the frozen Slice 5 observed-strategy belief is within the Slice 6C supported choices.",
            "- Effective supported choices translates entropy back into a pitch-count-like scale.",
            "- Supported deviation is the model's one-sided improvement from the current probability mix to its minimum predicted candidate.",
            "- This is not true exploitability because no batter best-response function is estimated.",
            "",
            "## Default 2.5% support gate",
            "",
            f"- Decisions: {default['decisions']:,}; pitchers: {default['pitchers']:,}.",
            f"- Mean normalized entropy: {default['mean_normalized_entropy']:.4f}.",
            f"- Mean effective supported choices: {default['mean_effective_supported_choices']:.3f}.",
            f"- Mean top-choice probability: {default['mean_top_supported_probability']:.3%}.",
            f"- Mean supported deviation: {default['mean_supported_deviation_gain']:.6f} batter runs per pitch.",
            f"- Deviations exceeding the single-pitch noise floor: {default['deviations_exceeding_noise_floor']:,}.",
            "",
            "## Threshold and subgroup sensitivity",
            "",
            f"- Complete panels: {sensitivity['complete_panels']}.",
            f"- Largest entropy range across the 1%, 2.5%, 5% and 10% gates: {sensitivity['maximum_entropy_range']:.6f}.",
            f"- Largest supported-deviation range: {sensitivity['maximum_deviation_range']:.6f} runs per pitch.",
            f"- Default groups below {payload['audit']['minimum_subgroup_decisions']:,} decisions: {payload['audit']['default_subgroups_below_minimum']}.",
            "- Intervals use pitcher-cluster bootstrap resampling, so repeated pitches by one pitcher are not treated as independent players.",
            "",
            "## Yamamoto–McCann case",
            "",
            f"- Supported choices: {case['supported_candidates']}; normalized entropy: {case['normalized_entropy']:.4f}; effective choices: {case['effective_supported_choices']:.3f}.",
            f"- The frozen strategy's top supported probability is {case['top_supported_probability']:.3%}.",
            f"- Chosen pitch: {case['chosen_pitch_type']}; model-minimum supported pitch: {case['best_supported_pitch_type']}.",
            f"- Chosen gap versus the model minimum: {case['chosen_gap_vs_best_supported']:.6f} runs; single-pitch 90% residual half-width: {case['single_pitch_residual_half_width_90']:.6f} runs.",
            "- The uncertainty is far larger than the modeled choice difference, so the case cannot support a factual-best-pitch or irrational-choice claim.",
            "",
            "## Release decision",
            "",
            f"- Aggregate entropy diagnostic ready: **{payload['release_gate']['aggregate_entropy_diagnostic_ready']}**.",
            f"- Entropy threshold stability ready: **{payload['release_gate']['entropy_threshold_stability_ready']}**; standalone entropy leaderboard ready: **{payload['release_gate']['entropy_leaderboard_ready']}**.",
            "- Supported deviation remains research-only.",
            "- True exploitability and individual strategy advice remain disabled.",
            "",
        ]
    )
