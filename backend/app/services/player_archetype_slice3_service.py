from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.core.config import settings
from app.services.player_archetype_challenger_service import batter_tags_path, pitcher_tags_path
from app.services.player_archetype_practical_tag_service import (
    get_player_archetype_practical_tags,
    practical_distribution_path,
    practical_roster_path,
)
from app.services.player_archetype_slice2a_service import slice2a_tags_path
from app.services.player_archetype_warehouse_service import batter_warehouse_path, pitcher_warehouse_path


CONTRACT_VERSION = "player_archetype_slice3_validation_v1"
CORE_PITCHER_DIMENSIONS = ("arsenal_depth", "primary_pair", "arm_slot", "command")
CORE_BATTER_DIMENSIONS = ("decision", "contact", "damage", "swing_shape")
SPARSE_COUNT = 30
SPARSE_SHARE = 0.02
DOMINANT_SHARE = 0.60
HIGH_UNASSIGNED_SHARE = 0.20


def slice3_roster_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice3_roster.parquet"


def slice3_distribution_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice3_distribution.parquet"


def slice3_transition_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice3_transitions.parquet"


def slice3_contract_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice3.json"


def slice3_report_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "PLAYER_ARCHETYPES_PITCH_STRATEGY.md"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_parquet(frame: pd.DataFrame, path: Path, relation: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.parquet")
    with duckdb.connect() as connection:
        connection.register(relation, frame)
        connection.execute(f"COPY {relation} TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(temporary)])
        connection.unregister(relation)
    temporary.replace(path)


def _normalized_tags(root: Path) -> pd.DataFrame:
    transparent = pd.read_parquet(slice2a_tags_path(root)).copy()
    transparent["population"] = "pitcher"
    transparent["source"] = "slice2a_transparent"
    transparent["published_tag"] = transparent["tag"]
    transparent["membership_probability"] = np.where(transparent["tag"].notna(), 1.0, np.nan)
    transparent["sample_status"] = np.where(transparent["sample_reliability"] >= 0.75, "high_support", "qualified")

    learned_pitcher = pd.read_parquet(pitcher_tags_path(root)).copy()
    learned_pitcher["source"] = "slice2_learned"
    learned_batter = pd.read_parquet(batter_tags_path(root)).copy()
    learned_batter["source"] = "slice2_learned"
    learned_batter["role"] = "Batter"

    columns = [
        "population", "year", "player_id", "role", "display_name", "team", "source", "dimension",
        "published_tag", "assignment_status", "unassigned_reason", "membership_probability",
        "bootstrap_stability", "sample_reliability", "sample_status",
    ]
    transparent["bootstrap_stability"] = np.where(transparent["tag"].notna(), 1.0, np.nan)
    frames = [transparent.reindex(columns=columns), learned_pitcher.reindex(columns=columns), learned_batter.reindex(columns=columns)]
    return pd.concat(frames, ignore_index=True)


def _adjacent_pairs(tags: pd.DataFrame) -> pd.DataFrame:
    assigned = tags[tags["published_tag"].notna()].copy()
    key = ["population", "player_id", "source", "dimension"]
    prior = assigned.rename(columns={
        "year": "year_from", "role": "role_from", "team": "team_from", "published_tag": "tag_from",
        "sample_reliability": "reliability_from",
    })
    later = assigned.rename(columns={
        "year": "year_to", "role": "role_to", "team": "team_to", "published_tag": "tag_to",
        "sample_reliability": "reliability_to",
    })
    pairs = prior.merge(later, on=key, suffixes=("_x", "_y"))
    pairs = pairs[pairs["year_to"].eq(pairs["year_from"] + 1)].copy()
    pairs["same_role"] = pairs["role_from"].eq(pairs["role_to"])
    pairs["team_changed"] = pairs["team_from"].ne(pairs["team_to"])
    pairs["retained"] = pairs["tag_from"].eq(pairs["tag_to"])
    pairs["pair_reliability"] = pairs[["reliability_from", "reliability_to"]].min(axis=1)
    return pairs


def _retention_summary(pairs: pd.DataFrame) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for (population, source, dimension, role), group in pairs[pairs["same_role"]].groupby(
        ["population", "source", "dimension", "role_from"], dropna=False, sort=True
    ):
        traded = group[group["team_changed"]]
        output.append({
            "population": str(population), "source": str(source), "dimension": str(dimension), "role": str(role),
            "adjacent_pairs": int(len(group)), "retained_pairs": int(group["retained"].sum()),
            "retention_pct": round(float(group["retained"].mean() * 100), 1),
            "traded_pairs": int(len(traded)),
            "traded_retention_pct": round(float(traded["retained"].mean() * 100), 1) if len(traded) else None,
            "effective_pair_support": round(float(group["pair_reliability"].sum()), 1),
        })
    return output


def _transition_table(pairs: pd.DataFrame) -> pd.DataFrame:
    columns = ["population", "source", "dimension", "year_from", "year_to", "role_from", "role_to", "same_role", "team_changed", "tag_from", "tag_to"]
    if pairs.empty:
        return pd.DataFrame(columns=columns + ["players", "mean_pair_reliability"])
    return pairs.groupby(columns, dropna=False).agg(
        players=("player_id", "nunique"), mean_pair_reliability=("pair_reliability", "mean")
    ).reset_index().sort_values(["population", "dimension", "year_from", "players"], ascending=[True, True, True, False])


def _distribution(tags: pd.DataFrame, retention: list[dict[str, Any]]) -> pd.DataFrame:
    retention_map = {
        (item["population"], item["source"], item["dimension"], item["role"]): item for item in retention
    }
    cooccurrences: dict[tuple[Any, ...], Counter[str]] = defaultdict(Counter)
    assigned_tags = tags[tags["published_tag"].notna()]
    for (population, year, player_id, role), entity in assigned_tags.groupby(
        ["population", "year", "player_id", "role"], dropna=False, sort=False
    ):
        values = list(entity[["source", "dimension", "published_tag"]].itertuples(index=False, name=None))
        for source, dimension, tag in values:
            key = (population, int(year), role, source, dimension, tag)
            for other_source, other_dimension, other_tag in values:
                if source == other_source and dimension == other_dimension:
                    continue
                cooccurrences[key][f"{other_dimension}: {other_tag}"] += 1
    rows: list[dict[str, Any]] = []
    group_columns = ["population", "year", "role", "source", "dimension"]
    for keys, group in tags.groupby(group_columns, dropna=False, sort=True):
        population, year, role, source, dimension = keys
        eligible = group[~group["assignment_status"].eq("ineligible")]
        total = int(len(eligible))
        assigned = eligible[eligible["published_tag"].notna()]
        unassigned = total - len(assigned)
        retention_row = retention_map.get((str(population), str(source), str(dimension), str(role)), {})
        counts = assigned["published_tag"].value_counts()
        for tag, count in counts.items():
            tag_group = assigned[assigned["published_tag"].eq(tag)]
            cooccurrence = cooccurrences.get((population, int(year), role, source, dimension, tag), Counter())
            top_cooccurrence = cooccurrence.most_common(1)[0] if cooccurrence else (None, 0)
            share = count / total if total else 0.0
            flags: list[str] = []
            if count < SPARSE_COUNT or share < SPARSE_SHARE:
                flags.append("sparse")
            if share > DOMINANT_SHARE:
                flags.append("dominant")
            if total and unassigned / total > HIGH_UNASSIGNED_SHARE:
                flags.append("high_unassigned")
            rows.append({
                "population": population, "year": int(year), "role": role, "source": source,
                "dimension": dimension, "tag": tag, "count": int(count), "eligible_entities": total,
                "eligible_share_pct": round(share * 100, 2),
                "effective_support": round(float(tag_group["sample_reliability"].fillna(0).sum()), 2),
                "adjacent_pairs": int(retention_row.get("adjacent_pairs", 0)),
                "retention_pct": retention_row.get("retention_pct"),
                "unassigned_count": int(unassigned),
                "unassigned_share_pct": round(unassigned * 100 / total, 2) if total else 0.0,
                "top_cooccurring_tag": top_cooccurrence[0],
                "cooccurrence_share_pct": round(top_cooccurrence[1] * 100 / count, 2) if count else 0.0,
                "review_flags": ",".join(flags),
            })
        if assigned.empty:
            rows.append({
                "population": population, "year": int(year), "role": role, "source": source,
                "dimension": dimension, "tag": None, "count": 0, "eligible_entities": total,
                "eligible_share_pct": 0.0, "effective_support": 0.0,
                "adjacent_pairs": int(retention_row.get("adjacent_pairs", 0)),
                "retention_pct": retention_row.get("retention_pct"), "unassigned_count": total,
                "unassigned_share_pct": 100.0, "review_flags": "high_unassigned",
                "top_cooccurring_tag": None, "cooccurrence_share_pct": 0.0,
            })
    return pd.DataFrame(rows)


def _tag_value(group: pd.DataFrame, dimension: str) -> Any:
    values = group.loc[group["dimension"].eq(dimension), "published_tag"].dropna()
    return values.iloc[0] if len(values) else None


def _build_roster(tags: pd.DataFrame, root: Path) -> pd.DataFrame:
    pitcher_warehouse = pd.read_parquet(pitcher_warehouse_path(root))[
        ["year", "player_id", "role", "pitches", "sample_reliability", "sample_status"]
    ].rename(columns={"pitches": "sample_size"})
    batter_warehouse = pd.read_parquet(batter_warehouse_path(root))[
        ["year", "player_id", "plate_appearances", "sample_reliability", "sample_status"]
    ].rename(columns={"plate_appearances": "sample_size"})
    batter_warehouse["role"] = "Batter"
    sample = pd.concat([pitcher_warehouse, batter_warehouse], ignore_index=True)
    rows: list[dict[str, Any]] = []
    for (population, year, player_id, role), group in tags.groupby(
        ["population", "year", "player_id", "role"], dropna=False, sort=False
    ):
        identity = group.iloc[0]
        if population == "pitcher":
            dimensions = CORE_PITCHER_DIMENSIONS
            core = [(dimension, _tag_value(group, dimension)) for dimension in dimensions]
            role_tag = _tag_value(group, "role_usage")
            concentration = _tag_value(group, "arsenal_concentration")
            shape = _tag_value(group, "shape")
            supplemental = [value for value in (role_tag, concentration, shape) if value]
        else:
            dimensions = CORE_BATTER_DIMENSIONS
            core = [(dimension, _tag_value(group, dimension)) for dimension in dimensions]
            supplemental = []
        core = [(dimension, value) for dimension, value in core if value][:4]
        sample_row = sample[
            sample["year"].eq(year) & sample["player_id"].eq(player_id) & sample["role"].eq(role)
        ]
        sample_values = sample_row.iloc[0] if len(sample_row) else None
        rows.append({
            "population": population, "year": int(year), "player_id": int(player_id), "role": role,
            "display_name": identity["display_name"], "team": identity["team"],
            "sample_size": int(sample_values["sample_size"]) if sample_values is not None else 0,
            "sample_reliability": float(sample_values["sample_reliability"]) if sample_values is not None else 0.0,
            "sample_status": sample_values["sample_status"] if sample_values is not None else "unknown",
            "tag_1": core[0][1] if len(core) > 0 else None, "tag_1_dimension": core[0][0] if len(core) > 0 else None,
            "tag_2": core[1][1] if len(core) > 1 else None, "tag_2_dimension": core[1][0] if len(core) > 1 else None,
            "tag_3": core[2][1] if len(core) > 2 else None, "tag_3_dimension": core[2][0] if len(core) > 2 else None,
            "tag_4": core[3][1] if len(core) > 3 else None, "tag_4_dimension": core[3][0] if len(core) > 3 else None,
            "tag_count": len(core), "supplemental_tags": json.dumps(supplemental, ensure_ascii=False),
            "support_status": "supported" if len(core) >= 3 else ("review" if core else "unassigned"),
        })
    return pd.DataFrame(rows).sort_values(["year", "population", "role", "sample_size"], ascending=[False, True, True, False])


def _rookie_audit(roster: pd.DataFrame) -> list[dict[str, Any]]:
    first_year = roster.groupby(["population", "player_id"])["year"].transform("min")
    rookies = roster[roster["year"].eq(first_year)].copy()
    rookies["sample_bucket"] = np.where(
        rookies["population"].eq("pitcher"),
        pd.cut(rookies["sample_size"], [-1, 99, 199, 499, np.inf], labels=["<100", "100-199", "200-499", "500+"]).astype(str),
        pd.cut(rookies["sample_size"], [-1, 99, 199, 299, np.inf], labels=["<100", "100-199", "200-299", "300+"]).astype(str),
    )
    rows: list[dict[str, Any]] = []
    for (population, bucket), group in rookies.groupby(["population", "sample_bucket"], observed=True, sort=True):
        rows.append({
            "population": population, "sample_bucket": bucket, "entities": int(len(group)),
            "three_plus_tags": int(group["tag_count"].ge(3).sum()),
            "three_plus_coverage_pct": round(float(group["tag_count"].ge(3).mean() * 100), 1),
            "mean_tags": round(float(group["tag_count"].mean()), 2),
            "mean_reliability": round(float(group["sample_reliability"].mean()), 3),
        })
    return rows


def _depth_label(row: Any, top_two_threshold: float = 85.0, versatile_effective: float = 5.0) -> str:
    if row.top_two_usage_pct >= top_two_threshold and row.effective_arsenal_size <= 2.5:
        return f"Two-Pitch {row.role}"
    if row.support_pitch_types >= 6 or row.effective_arsenal_size >= versatile_effective:
        return f"Versatile {row.role}"
    if row.support_pitch_types <= 3 and row.effective_arsenal_size < 3.5:
        return f"Three-Pitch {row.role}"
    return f"Multi-Pitch {row.role}"


def _slot_label(angle: float, hand: str, offset: float = 0.0) -> str:
    boundaries = [5 + offset, 15 + offset, 30 + offset, 45 + offset, 60 + offset]
    names = ["Submarine", "Sidearm", "Low 3/4", "3/4", "High 3/4", "Overhand"]
    index = int(np.searchsorted(boundaries, angle, side="right"))
    return f"{hand} {names[index]}"


def _sensitivity(transparent: pd.DataFrame) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    depth = transparent[(transparent["dimension"].eq("arsenal_depth")) & transparent["tag"].notna()]
    for label, top_two, effective in (("two_pitch_80", 80.0, 5.0), ("two_pitch_90", 90.0, 5.0), ("versatile_4_5", 85.0, 4.5), ("versatile_5_5", 85.0, 5.5)):
        alternative = depth.apply(lambda row: _depth_label(row, top_two, effective), axis=1)
        output.append({"dimension": "arsenal_depth", "scenario": label, "eligible_rows": int(len(depth)), "changed_rows": int(alternative.ne(depth["tag"]).sum()), "changed_pct": round(float(alternative.ne(depth["tag"]).mean() * 100), 2)})
    arm = transparent[(transparent["dimension"].eq("arm_slot")) & transparent["tag"].notna()]
    for offset in (-2.0, 2.0):
        alternative = arm.apply(lambda row: _slot_label(float(row.arm_angle_median), str(row.tag).split()[0], offset), axis=1)
        output.append({"dimension": "arm_slot", "scenario": f"all_boundaries_{offset:+.0f}_degrees", "eligible_rows": int(len(arm)), "changed_rows": int(alternative.ne(arm["tag"]).sum()), "changed_pct": round(float(alternative.ne(arm["tag"]).mean() * 100), 2)})
    return output


def _release_decisions(tags: pd.DataFrame, retention: list[dict[str, Any]]) -> list[dict[str, Any]]:
    retention_frame = pd.DataFrame(retention)
    rows: list[dict[str, Any]] = []
    for (population, source, dimension), group in tags.groupby(["population", "source", "dimension"], sort=True):
        eligible = group[~group["assignment_status"].eq("ineligible")]
        assigned_share = float(eligible["published_tag"].notna().mean()) if len(eligible) else 0.0
        metric = retention_frame[
            retention_frame["population"].eq(population)
            & retention_frame["source"].eq(source)
            & retention_frame["dimension"].eq(dimension)
        ]
        pairs = int(metric["adjacent_pairs"].sum()) if len(metric) else 0
        retained = int(metric["retained_pairs"].sum()) if len(metric) else 0
        retention_pct = 100 * retained / pairs if pairs else 0.0
        hard_reject = bool(source == "slice2_learned" and dimension == "arsenal" and population == "pitcher")
        if hard_reject:
            decision, reason = "research_only", "Slice 2 model-level separation/stability gate failed for SP arsenal; excluded from the official roster."
        elif pairs >= 100 and retention_pct >= 60 and assigned_share >= 0.80:
            decision, reason = "publish", "Adequate adjacent-year support, at least 60% retention and at least 80% assignment coverage."
        elif pairs >= 50 and retention_pct >= 40:
            decision, reason = "monitor", "Usable descriptive signal, but persistence or coverage is not strong enough for an unqualified display."
        else:
            decision, reason = "research_only", "Adjacent-year support, persistence or assignment coverage is below the Slice 3 display gate."
        rows.append({
            "population": population, "source": source, "dimension": dimension, "decision": decision,
            "assigned_share_pct": round(assigned_share * 100, 1), "adjacent_pairs": pairs,
            "retention_pct": round(retention_pct, 1), "reason": reason,
        })
    return rows


def build_player_archetype_slice3(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    tags = _normalized_tags(root)
    pairs = _adjacent_pairs(tags)
    retention = _retention_summary(pairs)
    transitions = _transition_table(pairs)
    distribution = _distribution(tags, retention)
    roster = _build_roster(tags, root)
    transparent = pd.read_parquet(slice2a_tags_path(root))
    decisions = _release_decisions(tags, retention)

    _write_parquet(roster, slice3_roster_path(root), "roster")
    _write_parquet(distribution, slice3_distribution_path(root), "distribution")
    _write_parquet(transitions, slice3_transition_path(root), "transitions")

    role_changes = pairs[~pairs["same_role"]]
    payload = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "publication_scope": "retrospective_full_season_descriptive_only",
        "artifacts": {
            "roster": str(slice3_roster_path(root)), "distribution": str(slice3_distribution_path(root)),
            "transitions": str(slice3_transition_path(root)),
        },
        "artifact_fingerprints": {
            "roster_sha256": _sha256(slice3_roster_path(root)),
            "distribution_sha256": _sha256(slice3_distribution_path(root)),
            "transitions_sha256": _sha256(slice3_transition_path(root)),
        },
        "audit": {
            "roster_rows": int(len(roster)), "duplicate_roster_keys": int(roster.duplicated(["population", "year", "player_id", "role"]).sum()),
            "distribution_rows": int(len(distribution)), "transition_rows": int(len(transitions)),
            "adjacent_tag_pairs": int(len(pairs)), "same_role_tag_pairs": int(pairs["same_role"].sum()),
            "role_change_tag_pairs": int(len(role_changes)), "traded_same_role_tag_pairs": int(pairs[pairs["same_role"] & pairs["team_changed"]].shape[0]),
            "roster_three_plus_tags": int(roster["tag_count"].ge(3).sum()),
        },
        "thresholds": {
            "publish": "at least 100 adjacent-year pairs, retention at least 60%, assignment coverage at least 80%",
            "monitor": "at least 50 adjacent-year pairs and retention at least 40%",
            "sparse_tag": f"count < {SPARSE_COUNT} or eligible share < {SPARSE_SHARE:.0%}",
            "dominant_tag": f"eligible share > {DOMINANT_SHARE:.0%}",
            "high_unassigned": f"unassigned share > {HIGH_UNASSIGNED_SHARE:.0%}",
        },
        "retention": retention,
        "role_change_summary": {
            "pairs": int(len(role_changes)),
            "retention_pct": round(float(role_changes["retained"].mean() * 100), 1) if len(role_changes) else None,
        },
        "rookie_cold_start": _rookie_audit(roster),
        "boundary_sensitivity": _sensitivity(transparent),
        "release_decisions": decisions,
        "review_flag_counts": {str(key): int(value) for key, value in distribution["review_flags"].replace("", "none").value_counts().items()},
        "warnings": [
            "Retention is descriptive agreement between adjacent full seasons, not a predictive validation score.",
            "Team changes are inferred from the season-role team field and may compress multi-team seasons.",
            "The first observed tracking season is a cold-start proxy, not an official MLB rookie definition.",
            "Tags are not talent grades; sparse and dominant groups are flagged rather than rebalanced.",
            "Pitcher Slice 2 learned arsenal is excluded from the official roster because the SP model gate failed.",
        ],
    }
    contract = slice3_contract_path(root)
    temporary = contract.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(contract)
    return payload


def get_player_archetype_slice3(data_dir: Path | None = None) -> dict[str, Any]:
    path = slice3_contract_path(data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Player archetype Slice 3 contract not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_player_archetype_slice3_view(
    year: int = 2026, population: str = "pitcher", role: str | None = None, data_dir: Path | None = None
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    contract = get_player_archetype_slice3(root)
    roster = pd.read_parquet(slice3_roster_path(root))
    distribution = pd.read_parquet(slice3_distribution_path(root))
    roster = roster[roster["year"].eq(year) & roster["population"].eq(population)]
    distribution = distribution[distribution["year"].eq(year) & distribution["population"].eq(population)]
    if population == "pitcher":
        distribution = distribution[distribution["dimension"].ne("primary_pair")]
    practical_contract: dict[str, Any] | None = None
    practical_year = pd.DataFrame()
    if population == "pitcher" and practical_roster_path(root).exists() and practical_distribution_path(root).exists():
        practical_contract = get_player_archetype_practical_tags(root)
        practical = pd.read_parquet(practical_roster_path(root))
        practical = practical[practical["year"].eq(year)]
        practical_year = practical.copy()
        practical["practical_tags"] = practical["practical_tags"].map(
            lambda value: json.loads(value) if isinstance(value, str) and value else []
        )
        roster = roster.merge(
            practical[["year", "player_id", "role", "practical_tags", "practical_tag_count"]],
            on=["year", "player_id", "role"],
            how="left",
        )
        roster["practical_tags"] = roster["practical_tags"].map(lambda value: value if isinstance(value, list) else [])
        roster["practical_tag_count"] = pd.to_numeric(roster["practical_tag_count"], errors="coerce").fillna(0).astype(int)
        practical_distribution = pd.read_parquet(practical_distribution_path(root))
        practical_distribution = practical_distribution[practical_distribution["year"].eq(year)]
        distribution = pd.concat([distribution, practical_distribution], ignore_index=True, sort=False)
    elif population == "pitcher":
        roster = roster.copy()
        roster["practical_tags"] = [[] for _ in range(len(roster))]
        roster["practical_tag_count"] = 0
    if role:
        roster = roster[roster["role"].eq(role)]
        distribution = distribution[distribution["role"].eq(role)]
    roster_records = roster.replace([np.inf, -np.inf], np.nan).astype(object).where(pd.notna(roster), None).to_dict(orient="records")
    distribution_records = distribution.replace([np.inf, -np.inf], np.nan).astype(object).where(pd.notna(distribution), None).to_dict(orient="records")
    release_decisions = [item for item in contract["release_decisions"] if item["population"] == population]
    if population == "pitcher":
        release_decisions = [item for item in release_decisions if item["dimension"] != "primary_pair"]
    warnings = list(contract["warnings"])
    practical_version = None
    if practical_contract is not None:
        practical_version = practical_contract["contract_version"]
        warnings.extend(practical_contract["warnings"])
        for practical_dimension in ("mechanics", "platoon_strategy"):
            rows = [item for item in practical_contract["retention"] if item["dimension"] == practical_dimension]
            pairs = sum(int(item["adjacent_pairs"]) for item in rows)
            retained = sum(int(item["adjacent_pairs"]) * float(item["retention_pct"]) / 100 for item in rows)
            status_column = "mechanics_status" if practical_dimension == "mechanics" else "platoon_strategy_status"
            eligible = int(practical_year[status_column].isin(["supported", "unassigned", "conflict_suppressed"]).sum())
            assigned = int(practical_year[status_column].eq("supported").sum())
            release_decisions.append({
                "population": "pitcher", "source": "practical_v1", "dimension": practical_dimension,
                "decision": "monitor", "assigned_share_pct": round(assigned * 100 / eligible, 1) if eligible else 0.0,
                "adjacent_pairs": pairs, "retention_pct": round(retained * 100 / pairs, 1) if pairs else 0.0,
                "reason": "Lab-first supplemental profile; it does not replace the frozen core tags.",
            })
    return {
        "contract_version": contract["contract_version"], "year": year, "population": population, "role": role,
        "practical_contract_version": practical_version,
        "publication_scope": contract["publication_scope"],
        "roster": roster_records,
        "distribution": distribution_records,
        "release_decisions": release_decisions,
        "boundary_sensitivity": contract["boundary_sensitivity"] if population == "pitcher" else [],
        "rookie_cold_start": [item for item in contract["rookie_cold_start"] if item["population"] == population],
        "warnings": warnings,
    }


def render_slice3_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Player Archetypes & Pitch Strategy · Slice 3 Validation", "", f"Generated: {payload['generated_at']}", "",
        "## Outcome", "",
        f"- Roster rows: **{payload['audit']['roster_rows']:,}**; duplicate keys: **{payload['audit']['duplicate_roster_keys']}**.",
        f"- Adjacent-season tag pairs: **{payload['audit']['adjacent_tag_pairs']:,}**; same-role: **{payload['audit']['same_role_tag_pairs']:,}**; role changes: **{payload['audit']['role_change_tag_pairs']:,}**.",
        f"- Player-season rows with at least three core tags: **{payload['audit']['roster_three_plus_tags']:,}**.", "",
        "## Release decisions", "", "| Population | Source | Dimension | Decision | Assigned | Pairs | Retention |", "|---|---|---|---|---:|---:|---:|",
    ]
    for row in payload["release_decisions"]:
        lines.append(f"| {row['population']} | {row['source']} | {row['dimension']} | {row['decision']} | {row['assigned_share_pct']:.1f}% | {row['adjacent_pairs']:,} | {row['retention_pct']:.1f}% |")
    lines.extend(["", "## Same-role retention", "", "| Population | Source | Dimension | Role | Pairs | Retention | Traded pairs | Traded retention |", "|---|---|---|---|---:|---:|---:|---:|"])
    for row in payload["retention"]:
        traded = "—" if row["traded_retention_pct"] is None else f"{row['traded_retention_pct']:.1f}%"
        lines.append(f"| {row['population']} | {row['source']} | {row['dimension']} | {row['role']} | {row['adjacent_pairs']:,} | {row['retention_pct']:.1f}% | {row['traded_pairs']:,} | {traded} |")
    lines.extend(["", "## Boundary sensitivity", "", "| Dimension | Scenario | Rows | Changed | Changed share |", "|---|---|---:|---:|---:|"])
    for row in payload["boundary_sensitivity"]:
        lines.append(f"| {row['dimension']} | {row['scenario']} | {row['eligible_rows']:,} | {row['changed_rows']:,} | {row['changed_pct']:.2f}% |")
    lines.extend(["", "## Interpretation limits", "", *[f"- {warning}" for warning in payload["warnings"]], ""])
    return "\n".join(lines)
