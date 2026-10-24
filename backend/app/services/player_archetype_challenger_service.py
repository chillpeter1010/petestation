from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import silhouette_score
from sklearn.mixture import GaussianMixture

from app.core.config import settings
from app.services.player_archetype_warehouse_service import batter_warehouse_path, pitcher_warehouse_path


CONTRACT_VERSION = "player_archetype_slice2_challenger_v1"
BOOTSTRAP_ITERATIONS = 30
RANDOM_SEED = 20261014
MIN_CLUSTER_ROWS = 30
MIN_CLUSTER_SHARE = 0.02
MIN_MEMBERSHIP = 0.50
MIN_STABILITY = 0.65
MIN_MODEL_SILHOUETTE = 0.10
MIN_MODEL_STABILITY = 0.65


@dataclass(frozen=True)
class DimensionSpec:
    name: str
    features: tuple[str, ...]
    prototypes: dict[str, tuple[float, ...]]


PITCHER_SPECS = (
    DimensionSpec(
        "arsenal",
        ("z_fastball_usage_eb", "z_breaking_usage_eb", "z_offspeed_usage_eb"),
        {
            "Fastball Heavy": (1.4, -0.7, -0.7),
            "Breaking Heavy": (-0.7, 1.4, -0.7),
            "Offspeed Heavy": (-0.7, -0.7, 1.4),
            "Fastball-Breaking Mix": (0.8, 0.8, -1.0),
            "Balanced Arsenal": (0.0, 0.0, 0.0),
        },
    ),
    DimensionSpec(
        "shape",
        ("z_fastball_velocity", "z_fastball_spin", "z_fastball_vertical_break", "z_release_extension"),
        {
            "Power-Ride Shape": (1.2, 0.8, 0.8, 0.0),
            "Power-Extension Shape": (1.0, 0.0, 0.0, 1.0),
            "Spin-Ride Shape": (0.0, 1.0, 1.0, 0.0),
            "Extension-Led Shape": (0.0, 0.0, 0.0, 1.4),
            "Lower-Velocity Shape": (-1.2, 0.0, 0.0, 0.0),
            "Neutral Shape": (0.0, 0.0, 0.0, 0.0),
        },
    ),
    DimensionSpec(
        "command",
        ("z_zone_pct_eb", "z_chase_pct_eb", "z_whiff_pct_eb", "z_first_pitch_strike_pct_eb"),
        {
            "Zone Attacker": (1.0, 0.0, 0.0, 1.0),
            "Chase-and-Miss": (0.0, 1.0, 1.0, 0.0),
            "Bat-Misser": (0.0, 0.0, 1.3, 0.0),
            "Count-Leverage": (0.0, 0.0, 0.0, 1.3),
            "Nibble Profile": (-1.0, -0.5, 0.0, -0.5),
            "Neutral Command": (0.0, 0.0, 0.0, 0.0),
        },
    ),
)

BATTER_SPECS = (
    DimensionSpec(
        "decision",
        ("z_zone_swing_pct_eb", "z_chase_pct_eb", "z_first_pitch_swing_pct_eb"),
        {
            "Selective": (-0.5, -1.0, -0.7),
            "Zone Aggressor": (1.0, -0.5, 0.7),
            "Chase Prone": (0.0, 1.3, 0.0),
            "First-Pitch Aggressor": (0.0, 0.0, 1.4),
            "Balanced Decision": (0.0, 0.0, 0.0),
        },
    ),
    DimensionSpec(
        "contact",
        ("z_contact_pct_eb", "z_woba"),
        {
            "Bat-to-Ball": (1.3, 0.0),
            "Impact Contact": (1.0, 1.0),
            "Damage-over-Contact": (-0.8, 1.0),
            "Low-Output Contact": (-1.0, -1.0),
            "Balanced Contact": (0.0, 0.0),
        },
    ),
    DimensionSpec(
        "damage",
        ("z_hard_hit_pct_eb", "z_barrel_pct_eb", "z_avg_exit_velocity", "z_woba"),
        {
            "Impact Power": (1.0, 1.0, 1.0, 1.0),
            "Hard-Contact Power": (1.2, 0.2, 1.0, 0.4),
            "Barrel-Driven Power": (0.3, 1.3, 0.3, 0.7),
            "Results-over-Contact": (0.0, 0.0, 0.0, 1.2),
            "Low-Damage Profile": (-1.0, -1.0, -1.0, -1.0),
            "Balanced Damage": (0.0, 0.0, 0.0, 0.0),
        },
    ),
    DimensionSpec(
        "swing_shape",
        ("z_avg_bat_speed", "z_avg_swing_length", "z_avg_attack_angle"),
        {
            "Fast-Compact Swing": (1.0, -1.0, 0.0),
            "Long-Power Swing": (1.0, 1.0, 0.0),
            "Steep Attack": (0.0, 0.0, 1.3),
            "Flat Attack": (0.0, 0.0, -1.3),
            "Compact-Control Swing": (0.0, -1.2, 0.0),
            "Neutral Swing Shape": (0.0, 0.0, 0.0),
        },
    ),
)


def pitcher_tags_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_pitcher_tags_v1.parquet"


def batter_tags_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_batter_tags_v1.parquet"


def challenger_contract_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice2_challenger.json"


def challenger_report_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "PLAYER_ARCHETYPES_PITCH_STRATEGY.md"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_parquet(frame: pd.DataFrame, path: Path, relation: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.parquet")
    with duckdb.connect() as connection:
        connection.register(relation, frame)
        connection.execute(f"COPY {relation} TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(temporary)])
        connection.unregister(relation)
    temporary.replace(path)


def _prototype_matrix(spec: DimensionSpec) -> tuple[list[str], np.ndarray]:
    labels = list(spec.prototypes)
    return labels, np.asarray([spec.prototypes[label] for label in labels], dtype=float)


def _nearest_prototype(values: np.ndarray, spec: DimensionSpec) -> np.ndarray:
    labels, prototypes = _prototype_matrix(spec)
    distances = ((values[:, None, :] - prototypes[None, :, :]) ** 2).sum(axis=2)
    return np.asarray([labels[index] for index in distances.argmin(axis=1)], dtype=object)


def _component_labels(means: np.ndarray, spec: DimensionSpec) -> dict[int, str]:
    labels, prototypes = _prototype_matrix(spec)
    distances = ((means[:, None, :] - prototypes[None, :, :]) ** 2).sum(axis=2)
    rows, columns = linear_sum_assignment(distances)
    return {int(row): labels[int(column)] for row, column in zip(rows, columns, strict=True)}


def _fit_candidates(values: np.ndarray, spec: DimensionSpec) -> tuple[GaussianMixture | None, list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    accepted: list[tuple[float, GaussianMixture]] = []
    for components in range(2, 6):
        model = GaussianMixture(
            n_components=components,
            covariance_type="full",
            reg_covar=1e-5,
            n_init=5,
            max_iter=500,
            random_state=RANDOM_SEED + components,
        ).fit(values)
        assignments = model.predict(values)
        counts = np.bincount(assignments, minlength=components)
        minimum = int(counts.min())
        minimum_share = float(minimum / len(values))
        accepted_support = minimum >= MIN_CLUSTER_ROWS and minimum_share >= MIN_CLUSTER_SHARE
        silhouette = float(silhouette_score(values, assignments)) if len(np.unique(assignments)) > 1 else None
        record = {
            "components": components,
            "bic": float(model.bic(values)),
            "silhouette": silhouette,
            "minimum_cluster_rows": minimum,
            "minimum_cluster_share": minimum_share,
            "support_gate_passed": accepted_support,
            "converged": bool(model.converged_),
        }
        diagnostics.append(record)
        if accepted_support and model.converged_:
            accepted.append((record["bic"], model))
    if not accepted:
        return None, diagnostics
    return min(accepted, key=lambda item: item[0])[1], diagnostics


def _bootstrap_stability(
    values: np.ndarray,
    player_ids: np.ndarray,
    base_model: GaussianMixture,
) -> tuple[np.ndarray, int]:
    base_assignments = base_model.predict(values)
    matches = np.zeros(len(values), dtype=float)
    completed = 0
    unique_players = np.unique(player_ids)
    row_indices = {player: np.flatnonzero(player_ids == player) for player in unique_players}
    rng = np.random.default_rng(RANDOM_SEED + base_model.n_components)
    for iteration in range(BOOTSTRAP_ITERATIONS):
        sampled_players = rng.choice(unique_players, size=len(unique_players), replace=True)
        sampled_indices = np.concatenate([row_indices[player] for player in sampled_players])
        try:
            model = GaussianMixture(
                n_components=base_model.n_components,
                covariance_type="full",
                reg_covar=1e-5,
                n_init=2,
                max_iter=500,
                random_state=RANDOM_SEED + 100 + iteration,
            ).fit(values[sampled_indices])
        except (ValueError, np.linalg.LinAlgError):
            continue
        boot_rows, base_columns = linear_sum_assignment(
            ((model.means_[:, None, :] - base_model.means_[None, :, :]) ** 2).sum(axis=2)
        )
        boot_to_base = np.empty(base_model.n_components, dtype=int)
        boot_to_base[boot_rows] = base_columns
        aligned = boot_to_base[model.predict(values)]
        matches += aligned == base_assignments
        completed += 1
    if not completed:
        return np.full(len(values), np.nan), 0
    return matches / completed, completed


def _context_tag(row: Any) -> str:
    if row.role == "SP":
        if row.opener_like_share_pct >= 50.0:
            return "Opener-Dominant"
        if row.traditional_start_appearances >= max(1, row.appearances / 2):
            return "Traditional Starter"
        return "Short-Start Mix"
    if row.bulk_relief_appearances >= max(1, row.appearances / 4):
        return "Bulk Relief"
    if row.avg_appearance_pitches >= 25.0:
        return "Multi-Inning Relief"
    return "Short Relief"


def _empty_assignment(row: Any, population: str, dimension: str, status: str, reason: str) -> dict[str, Any]:
    result = {
        "population": population,
        "year": int(row.year),
        "player_id": int(row.player_id),
        "display_name": row.display_name,
        "team": row.team,
        "dimension": dimension,
        "rule_tag": None,
        "mixture_tag": None,
        "published_tag": None,
        "membership_probability": None,
        "bootstrap_stability": None,
        "rule_mixture_agree": None,
        "sample_reliability": float(row.sample_reliability),
        "sample_status": row.sample_status,
        "feature_coverage": 0.0,
        "assignment_status": status,
        "unassigned_reason": reason,
        "feature_time_scope": row.feature_time_scope,
    }
    if population == "pitcher":
        result["role"] = row.role
    return result


def _assign_dimension(
    frame: pd.DataFrame,
    population: str,
    spec: DimensionSpec,
    cohort_label: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible = frame["archetype_eligible"].astype(bool)
    complete = frame[list(spec.features)].notna().all(axis=1)
    model_mask = eligible & complete
    model_frame = frame.loc[model_mask].copy()
    values = model_frame.loc[:, spec.features].to_numpy(dtype=float)
    model, candidates = _fit_candidates(values, spec)
    diagnostics: dict[str, Any] = {
        "population": population,
        "cohort": cohort_label,
        "dimension": spec.name,
        "features": list(spec.features),
        "eligible_rows": int(eligible.sum()),
        "complete_rows": int(model_mask.sum()),
        "complete_players": int(model_frame["player_id"].nunique()),
        "candidates": candidates,
        "selected_components": None,
        "bootstrap_iterations_requested": BOOTSTRAP_ITERATIONS,
        "bootstrap_iterations_completed": 0,
    }
    modeled: dict[int, dict[str, Any]] = {}
    if model is not None:
        probabilities = model.predict_proba(values)
        components = probabilities.argmax(axis=1)
        membership = probabilities.max(axis=1)
        stability, completed = _bootstrap_stability(
            values, model_frame["player_id"].to_numpy(dtype=np.int64), model
        )
        component_tags = _component_labels(model.means_, spec)
        mixture_tags = np.asarray([component_tags[int(component)] for component in components], dtype=object)
        rule_tags = _nearest_prototype(values, spec)
        selected_candidate = next(item for item in candidates if item["components"] == model.n_components)
        mean_stability = float(np.nanmean(stability))
        model_gate_passed = bool(
            selected_candidate["silhouette"] is not None
            and selected_candidate["silhouette"] >= MIN_MODEL_SILHOUETTE
            and mean_stability >= MIN_MODEL_STABILITY
        )
        for index, row_index in enumerate(model_frame.index):
            supported = (
                model_gate_passed
                and membership[index] >= MIN_MEMBERSHIP
                and stability[index] >= MIN_STABILITY
            )
            status = "supported" if supported else "provisional"
            reason = None if supported else "membership_or_bootstrap_below_gate"
            if not model_gate_passed:
                status = "model_rejected"
                reason = "model_separation_or_stability_below_gate"
            modeled[int(row_index)] = {
                "rule_tag": str(rule_tags[index]),
                "mixture_tag": str(mixture_tags[index]),
                "published_tag": str(mixture_tags[index]) if supported else None,
                "membership_probability": float(membership[index]),
                "bootstrap_stability": float(stability[index]),
                "rule_mixture_agree": bool(rule_tags[index] == mixture_tags[index]),
                "feature_coverage": 1.0,
                "assignment_status": status,
                "unassigned_reason": reason,
            }
        hard_counts = np.bincount(components, minlength=model.n_components)
        diagnostics.update(
            {
                "selected_components": int(model.n_components),
                "component_tags": {str(key): value for key, value in component_tags.items()},
                "component_counts": hard_counts.astype(int).tolist(),
                "bootstrap_iterations_completed": completed,
                "mean_membership_probability": float(membership.mean()),
                "mean_bootstrap_stability": mean_stability,
                "rule_mixture_agreement": float((rule_tags == mixture_tags).mean()),
                "publication_gate_passed": model_gate_passed,
                "supported_rows": int(sum(item["assignment_status"] == "supported" for item in modeled.values())),
            }
        )

    assignments: list[dict[str, Any]] = []
    for row_index, row in zip(frame.index, frame.itertuples(index=False), strict=True):
        if not bool(row.archetype_eligible):
            assignments.append(_empty_assignment(row, population, spec.name, "ineligible", "sample_not_eligible"))
            continue
        feature_coverage = float(pd.notna(frame.loc[row_index, list(spec.features)]).mean())
        if not bool(complete.loc[row_index]):
            item = _empty_assignment(row, population, spec.name, "unavailable", "required_features_missing")
            item["feature_coverage"] = feature_coverage
            assignments.append(item)
            continue
        if model is None:
            item = _empty_assignment(row, population, spec.name, "model_rejected", "no_candidate_passed_support_gate")
            item["feature_coverage"] = feature_coverage
            assignments.append(item)
            continue
        item = _empty_assignment(row, population, spec.name, "provisional", "membership_or_bootstrap_below_gate")
        item.update(modeled[int(row_index)])
        assignments.append(item)
    return assignments, diagnostics


def _pitcher_assignments(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    assignments: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for role in ("SP", "RP"):
        cohort = frame[frame["role"].eq(role)]
        for spec in PITCHER_SPECS:
            rows, audit = _assign_dimension(cohort, "pitcher", spec, role)
            assignments.extend(rows)
            diagnostics.append(audit)
    for row in frame.itertuples(index=False):
        item = _empty_assignment(row, "pitcher", "role_usage", "ineligible", "sample_not_eligible")
        if bool(row.archetype_eligible):
            tag = _context_tag(row)
            item.update(
                {
                    "rule_tag": tag,
                    "published_tag": tag,
                    "membership_probability": 1.0,
                    "bootstrap_stability": 1.0,
                    "feature_coverage": 1.0,
                    "assignment_status": "supported_context",
                    "unassigned_reason": None,
                }
            )
        assignments.append(item)
    return pd.DataFrame(assignments), diagnostics


def _batter_assignments(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    assignments: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for spec in BATTER_SPECS:
        rows, audit = _assign_dimension(frame, "batter", spec, "all_batters")
        assignments.extend(rows)
        diagnostics.append(audit)
    return pd.DataFrame(assignments), diagnostics


def _audit(tags: pd.DataFrame, key: list[str]) -> dict[str, Any]:
    entity_count = int(tags[key].drop_duplicates().shape[0])
    status_counts = {str(k): int(v) for k, v in tags["assignment_status"].value_counts(dropna=False).items()}
    published = tags[tags["published_tag"].notna()]
    per_entity = published.groupby(key).size()
    return {
        "rows": int(len(tags)),
        "entities": entity_count,
        "duplicate_entity_dimensions": int(tags.duplicated(key + ["dimension"]).sum()),
        "status_counts": status_counts,
        "published_tag_rows": int(len(published)),
        "entities_with_3_or_4_tags": int(per_entity.between(3, 4).sum()),
        "entities_with_any_tag": int(per_entity.size),
        "mean_published_tags_per_tagged_entity": float(per_entity.mean()) if len(per_entity) else 0.0,
    }


def _representatives(tags: pd.DataFrame) -> list[dict[str, Any]]:
    supported = tags[tags["published_tag"].notna()].copy()
    supported["representative_score"] = (
        supported["membership_probability"].fillna(0.0)
        * supported["bootstrap_stability"].fillna(0.0)
        * supported["sample_reliability"].fillna(0.0)
    )
    output: list[dict[str, Any]] = []
    groups = ["population", "dimension", "published_tag"]
    if "role" in supported:
        groups.insert(1, "role")
    for keys, group in supported.groupby(groups, dropna=False):
        key_values = keys if isinstance(keys, tuple) else (keys,)
        descriptor = dict(zip(groups, key_values, strict=True))
        descriptor["players"] = [
            {
                "year": int(row.year),
                "player_id": int(row.player_id),
                "display_name": row.display_name,
                "team": row.team,
                "score": round(float(row.representative_score), 4),
            }
            for row in group.nlargest(5, "representative_score").itertuples(index=False)
        ]
        output.append(descriptor)
    return output


def build_player_archetype_challenger(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    pitchers = pd.read_parquet(pitcher_warehouse_path(root))
    batters = pd.read_parquet(batter_warehouse_path(root))
    pitcher_tags, pitcher_models = _pitcher_assignments(pitchers)
    batter_tags, batter_models = _batter_assignments(batters)
    _write_parquet(pitcher_tags, pitcher_tags_path(root), "pitcher_tags")
    _write_parquet(batter_tags, batter_tags_path(root), "batter_tags")
    pitcher_audit = _audit(pitcher_tags, ["year", "player_id", "role"])
    batter_audit = _audit(batter_tags, ["year", "player_id"])
    model_diagnostics = pitcher_models + batter_models
    payload = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready"
        if not pitcher_audit["duplicate_entity_dimensions"] and not batter_audit["duplicate_entity_dimensions"]
        else "invalid",
        "publication_status": "research_only_full_season_descriptive",
        "method": {
            "rule_baseline": "Nearest named baseball prototype in Slice 1 normalized feature space.",
            "soft_challenger": "Role-specific pitcher and pooled-batter Gaussian mixtures; k=2..5 selected by minimum BIC after cluster-support and convergence gates.",
            "bootstrap": "Player-cluster bootstrap preserves all seasons for each sampled player; bootstrap components are aligned to the selected model before assignment stability is calculated.",
            "published_tag_gate": f"model silhouette >= {MIN_MODEL_SILHOUETTE:.2f} and mean stability >= {MIN_MODEL_STABILITY:.2f}, then membership >= {MIN_MEMBERSHIP:.2f} and player stability >= {MIN_STABILITY:.2f}; otherwise null.",
            "context_tag": "Pitcher role_usage is an explicit workload rule, not a learned cluster.",
        },
        "thresholds": {
            "minimum_cluster_rows": MIN_CLUSTER_ROWS,
            "minimum_cluster_share": MIN_CLUSTER_SHARE,
            "minimum_membership": MIN_MEMBERSHIP,
            "minimum_bootstrap_stability": MIN_STABILITY,
            "minimum_model_silhouette": MIN_MODEL_SILHOUETTE,
            "minimum_model_mean_stability": MIN_MODEL_STABILITY,
            "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
        },
        "artifacts": {
            "pitcher_tags": str(pitcher_tags_path(root)),
            "batter_tags": str(batter_tags_path(root)),
        },
        "artifact_fingerprints": {
            "pitcher_tags_sha256": _sha256(pitcher_tags_path(root)),
            "batter_tags_sha256": _sha256(batter_tags_path(root)),
            "pitcher_warehouse_sha256": _sha256(pitcher_warehouse_path(root)),
            "batter_warehouse_sha256": _sha256(batter_warehouse_path(root)),
        },
        "audit": {"pitcher": pitcher_audit, "batter": batter_audit},
        "model_diagnostics": model_diagnostics,
        "representative_players": _representatives(pd.concat([pitcher_tags, batter_tags], ignore_index=True)),
        "warnings": [
            "These are retrospective full-season descriptions, not pre-pitch beliefs and not causal player types.",
            "Mixture components describe density in the selected features; the baseball names are post-fit interpretations anchored to fixed prototypes.",
            "A null published tag is intentional when sample, feature, membership, or bootstrap support is weak.",
            "Swing-shape remains unavailable when tracking coverage is insufficient; missing seasons are not imputed.",
            "Tag balance and cross-year persistence are Slice 3 questions and are not optimized here.",
        ],
    }
    contract = challenger_contract_path(root)
    contract.parent.mkdir(parents=True, exist_ok=True)
    temporary = contract.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(contract)
    return payload


def get_player_archetype_challenger(data_dir: Path | None = None) -> dict[str, Any]:
    path = challenger_contract_path(data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Player archetype Slice 2 contract not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def render_challenger_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Player Archetypes & Pitch Strategy · Slice 2 Challenger",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Outcome",
        "",
        "| Population | Rows | Entities | Published tags | Entities with 3–4 tags | Mean tags when tagged |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for population in ("pitcher", "batter"):
        row = payload["audit"][population]
        lines.append(
            f"| {population.title()} | {row['rows']:,} | {row['entities']:,} | {row['published_tag_rows']:,} | {row['entities_with_3_or_4_tags']:,} | {row['mean_published_tags_per_tagged_entity']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Model diagnostics",
            "",
            "| Population | Cohort | Dimension | Complete rows | Selected k | Silhouette | Mean membership | Mean stability | Rule/GMM agreement | Publish? | Supported rows |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|",
        ]
    )
    for model in payload["model_diagnostics"]:
        selected = next(
            candidate for candidate in model["candidates"] if candidate["components"] == model["selected_components"]
        )
        lines.append(
            f"| {model['population']} | {model['cohort']} | {model['dimension']} | {model['complete_rows']:,} | {model['selected_components'] or '—'} | {selected['silhouette']:.3f} | {model.get('mean_membership_probability', 0):.3f} | {model.get('mean_bootstrap_stability', 0):.3f} | {model.get('rule_mixture_agreement', 0):.3f} | {'yes' if model.get('publication_gate_passed') else 'no'} | {model.get('supported_rows', 0):,} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation contract",
            "",
            *[f"- **{key}**: {value}" for key, value in payload["method"].items()],
            "",
            "## Warnings",
            "",
            *[f"- {warning}" for warning in payload["warnings"]],
            "",
        ]
    )
    return "\n".join(lines)
