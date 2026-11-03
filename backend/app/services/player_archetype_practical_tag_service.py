from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path
from app.services.player_archetype_warehouse_service import YEARS, pitcher_warehouse_path


CONTRACT_VERSION = "player_archetype_practical_tags_v1"
VALID_PITCH_TYPES = ("FF", "FA", "SI", "FC", "SL", "ST", "CU", "KC", "SV", "CH", "FS", "FO")
PRONATION_TYPES = frozenset({"FF", "FA", "SI", "CH", "FS", "FO"})
SUPINATION_TYPES = frozenset({"SL", "ST", "CU", "KC", "SV"})
BREAKING_TYPES = frozenset({"SL", "ST", "CU", "KC", "SV"})
OFFSPEED_TYPES = frozenset({"CH", "FS", "FO"})
MIN_TYPE_PITCHES = 20
MIN_TYPE_USAGE = 0.05
MIN_COHORT_ENTITIES = 20
STRONG_SHAPE_Z = 0.5
MIN_STRONG_TYPES = 1
MIN_PLATOON_PITCHES = 40
MIN_PLATOON_USAGE = 0.25
MIN_PLATOON_GAP = 0.12


def practical_roster_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_practical_tags_v1.parquet"


def practical_distribution_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_practical_tag_distribution_v1.parquet"


def practical_contract_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_practical_tags_v1.json"


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


def _pitch_rows(year: int, root: Path) -> pd.DataFrame:
    valid = ", ".join(f"'{pitch_type}'" for pitch_type in VALID_PITCH_TYPES)
    with duckdb.connect(str(get_season_duckdb_path(year, root)), read_only=True) as connection:
        rows = connection.execute(
            f"""
            WITH base AS (
                SELECT cast(pitcher AS BIGINT) AS player_id,
                       game_pk,
                       coalesce(nullif(pitcher_team, ''),
                           CASE WHEN inning_topbot = 'Top' THEN home_team ELSE away_team END) AS team,
                       inning, at_bat_number, pitch_number,
                       upper(pitch_type) AS pitch_type,
                       upper(p_throws) AS throws,
                       upper(stand) AS stand,
                       pfx_x,
                       min(coalesce(inning, 99) * 1000000
                           + coalesce(at_bat_number, 9999) * 100
                           + coalesce(pitch_number, 99))
                           OVER (PARTITION BY pitcher, game_pk) AS first_sequence
                FROM pitches
                WHERE game_type = 'R'
                  AND pitcher IS NOT NULL
                  AND game_pk IS NOT NULL
                  AND upper(pitch_type) IN ({valid})
            ), classified AS (
                SELECT *, CASE WHEN first_sequence = min(first_sequence) OVER (PARTITION BY game_pk, team)
                               THEN 'SP' ELSE 'RP' END AS appearance_role
                FROM base
            )
            SELECT {int(year)} AS year, player_id, appearance_role, throws, stand, pitch_type,
                   count(*) AS pitch_count,
                   count(pfx_x) AS movement_pitches,
                   avg(CASE WHEN throws = 'R' THEN -pfx_x * 12.0 ELSE pfx_x * 12.0 END) AS arm_side_break
            FROM classified
            GROUP BY player_id, appearance_role, throws, stand, pitch_type
            ORDER BY player_id, appearance_role, stand, pitch_type
            """
        ).fetchdf()
    return rows.rename(columns={"appearance_role": "role"})


def classify_mechanics_tag(metrics: pd.DataFrame) -> tuple[str | None, str, dict[str, Any]]:
    pronation = metrics[metrics["pitch_type"].isin(PRONATION_TYPES)].copy()
    supination = metrics[metrics["pitch_type"].isin(SUPINATION_TYPES)].copy()
    pronation_strong = pronation[pronation["arm_side_z"].ge(STRONG_SHAPE_Z)]
    supination_strong = supination[supination["arm_side_z"].le(-STRONG_SHAPE_Z)]
    pronation_mean = float(np.average(pronation["arm_side_z"], weights=pronation["pitch_count"])) if len(pronation) else None
    supination_mean = float(np.average(-supination["arm_side_z"], weights=supination["pitch_count"])) if len(supination) else None
    enough_pronation = len(pronation) >= 1
    enough_supination = len(supination) >= 1
    pronation_candidate = (
        len(pronation_strong) >= MIN_STRONG_TYPES
        and pronation_mean is not None
        and pronation_mean >= STRONG_SHAPE_Z
    )
    supination_candidate = (
        len(supination_strong) >= MIN_STRONG_TYPES
        and supination_mean is not None
        and supination_mean >= STRONG_SHAPE_Z
    )
    tag = "Pronation" if pronation_candidate ^ supination_candidate and pronation_candidate else (
        "Supination" if pronation_candidate ^ supination_candidate and supination_candidate else None
    )
    if pronation_candidate and supination_candidate:
        status = "conflict_suppressed"
    elif tag:
        status = "supported"
    elif enough_pronation or enough_supination:
        status = "unassigned"
    else:
        status = "insufficient"
    evidence = {
        "pronation_supported_types": sorted(pronation["pitch_type"].astype(str).tolist()),
        "pronation_strong_types": sorted(pronation_strong["pitch_type"].astype(str).tolist()),
        "pronation_family_z": round(pronation_mean, 3) if pronation_mean is not None else None,
        "supination_supported_types": sorted(supination["pitch_type"].astype(str).tolist()),
        "supination_strong_types": sorted(supination_strong["pitch_type"].astype(str).tolist()),
        "supination_family_z": round(supination_mean, 3) if supination_mean is not None else None,
        "xor_conflict": bool(pronation_candidate and supination_candidate),
    }
    return tag, status, evidence


def classify_platoon_strategy(rows: pd.DataFrame) -> tuple[list[str], str, dict[str, Any]]:
    totals = rows.groupby("stand")["pitch_count"].sum().to_dict()
    evidence: dict[str, Any] = {"L_pitches": int(totals.get("L", 0)), "R_pitches": int(totals.get("R", 0)), "tags": {}}
    if min(evidence["L_pitches"], evidence["R_pitches"]) < MIN_PLATOON_PITCHES:
        return [], "insufficient", evidence
    families = {"More Breaking Balls": BREAKING_TYPES, "More Offspeed": OFFSPEED_TYPES}
    tags: list[str] = []
    for side, other_side in (("L", "R"), ("R", "L")):
        candidates: list[tuple[float, str, float, float]] = []
        for family, pitch_types in families.items():
            side_count = int(rows[rows["stand"].eq(side) & rows["pitch_type"].isin(pitch_types)]["pitch_count"].sum())
            other_count = int(rows[rows["stand"].eq(other_side) & rows["pitch_type"].isin(pitch_types)]["pitch_count"].sum())
            side_usage = side_count / evidence[f"{side}_pitches"]
            other_usage = other_count / evidence[f"{other_side}_pitches"]
            gap = side_usage - other_usage
            if side_usage >= MIN_PLATOON_USAGE and gap >= MIN_PLATOON_GAP:
                candidates.append((gap, family, side_usage, other_usage))
        if candidates:
            gap, family, side_usage, other_usage = max(candidates)
            label = f"{side}HB {family}"
            tags.append(label)
            evidence["tags"][label] = {
                "usage_pct": round(side_usage * 100, 1),
                "opposite_side_usage_pct": round(other_usage * 100, 1),
                "gap_pp": round(gap * 100, 1),
            }
    return tags, "supported" if tags else "unassigned", evidence


def _tag_item(code: str, label: str, dimension: str, description: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"code": code, "label": label, "dimension": dimension, "description": description, "evidence": evidence}


def _build_roster(root: Path) -> pd.DataFrame:
    warehouse = pd.read_parquet(pitcher_warehouse_path(root))
    raw = pd.concat([_pitch_rows(year, root) for year in YEARS], ignore_index=True)
    entity_pitch = (
        raw.dropna(subset=["arm_side_break"])
        .assign(weighted_break=lambda frame: frame["movement_pitches"] * frame["arm_side_break"])
        .groupby(["year", "player_id", "role", "throws", "pitch_type"], as_index=False)
        .agg(pitch_count=("pitch_count", "sum"), movement_pitches=("movement_pitches", "sum"), weighted_break=("weighted_break", "sum"))
    )
    entity_pitch["arm_side_break"] = entity_pitch["weighted_break"] / entity_pitch["movement_pitches"]
    support = warehouse[["year", "player_id", "role", "pitches"]]
    qualified = entity_pitch.merge(support, on=["year", "player_id", "role"], how="left")
    qualified = qualified[
        qualified["movement_pitches"].ge(MIN_TYPE_PITCHES)
        & qualified["pitch_count"].div(qualified["pitches"]).ge(MIN_TYPE_USAGE)
    ].copy()
    benchmark = (
        qualified.groupby(["year", "role", "throws", "pitch_type"])["arm_side_break"]
        .agg(cohort_mean="mean", cohort_sd="std", cohort_entities="count")
        .reset_index()
    )
    qualified = qualified.merge(benchmark, on=["year", "role", "throws", "pitch_type"], how="left")
    qualified = qualified[qualified["cohort_entities"].ge(MIN_COHORT_ENTITIES) & qualified["cohort_sd"].gt(0)].copy()
    qualified["arm_side_z"] = (qualified["arm_side_break"] - qualified["cohort_mean"]) / qualified["cohort_sd"]
    mechanics_groups = {key: group for key, group in qualified.groupby(["year", "player_id", "role"], sort=False)}
    strategy_groups = {key: group for key, group in raw.groupby(["year", "player_id", "role"], sort=False)}
    records: list[dict[str, Any]] = []
    for row in warehouse.itertuples(index=False):
        key = (int(row.year), int(row.player_id), str(row.role))
        practical_tags: list[dict[str, Any]] = []
        if bool(row.archetype_eligible):
            mechanics_tag, mechanics_status, mechanics_evidence = classify_mechanics_tag(
                mechanics_groups.get(key, pd.DataFrame(columns=["pitch_type", "arm_side_z", "pitch_count"]))
            )
            strategy_tags, strategy_status, strategy_evidence = classify_platoon_strategy(
                strategy_groups.get(key, pd.DataFrame(columns=["stand", "pitch_type", "pitch_count"]))
            )
        else:
            mechanics_tag, mechanics_status, mechanics_evidence = None, "ineligible", {}
            strategy_tags, strategy_status, strategy_evidence = [], "ineligible", {}
        if mechanics_tag:
            practical_tags.append(_tag_item(
                mechanics_tag.lower(), mechanics_tag, "mechanics",
                "Hand-normalized horizontal movement profile versus the same season, role, throwing hand, and pitch type.",
                mechanics_evidence,
            ))
        for label in strategy_tags:
            practical_tags.append(_tag_item(
                f"platoon_{label.lower().replace(' ', '_').replace('-', '_')}", label, "platoon_strategy",
                "Full-season pitch-family usage changes by batter side; descriptive tendency, not an effectiveness claim.",
                strategy_evidence["tags"][label],
            ))
        records.append({
            "year": int(row.year), "player_id": int(row.player_id), "role": str(row.role),
            "display_name": row.display_name, "team": row.team, "throws": row.throws, "pitches": int(row.pitches),
            "mechanics_tag": mechanics_tag, "mechanics_status": mechanics_status,
            "mechanics_evidence": json.dumps(mechanics_evidence, ensure_ascii=False),
            "platoon_strategy_tags": json.dumps(strategy_tags, ensure_ascii=False),
            "platoon_strategy_status": strategy_status,
            "platoon_strategy_evidence": json.dumps(strategy_evidence, ensure_ascii=False),
            "practical_tags": json.dumps(practical_tags, ensure_ascii=False),
            "practical_tag_count": len(practical_tags),
        })
    return pd.DataFrame(records).sort_values(["year", "role", "pitches"], ascending=[False, True, False])


def _parse_tags(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _retention(roster: pd.DataFrame) -> list[dict[str, Any]]:
    entity_tags = {
        (int(row.year), int(row.player_id), str(row.role)): _parse_tags(row.practical_tags)
        for row in roster.itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []
    for (year, player_id, role), tags in entity_tags.items():
        next_tags = entity_tags.get((year + 1, player_id, role))
        if next_tags is None:
            continue
        next_values = {(str(item.get("dimension")), str(item.get("label"))) for item in next_tags}
        for item in tags:
            dimension = str(item.get("dimension"))
            label = str(item.get("label"))
            rows.append({"dimension": dimension, "tag": label, "retained": (dimension, label) in next_values})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return []
    return [
        {"dimension": dimension, "tag": tag, "adjacent_pairs": int(len(group)), "retention_pct": round(float(group["retained"].mean() * 100), 1)}
        for (dimension, tag), group in frame.groupby(["dimension", "tag"], sort=True)
    ]


def _distribution(roster: pd.DataFrame, retention: list[dict[str, Any]]) -> pd.DataFrame:
    retention_map = {(row["dimension"], row["tag"]): row for row in retention}
    rows: list[dict[str, Any]] = []
    for (year, role), group in roster.groupby(["year", "role"], sort=True):
        tags = [(item, record) for record in group.itertuples(index=False) for item in _parse_tags(record.practical_tags)]
        for dimension in ("mechanics", "platoon_strategy"):
            eligible_column = "mechanics_status" if dimension == "mechanics" else "platoon_strategy_status"
            eligible = int(group[eligible_column].isin(["supported", "unassigned", "conflict_suppressed"]).sum())
            labels = [str(item["label"]) for item, _ in tags if item.get("dimension") == dimension]
            for label, count in pd.Series(labels, dtype="object").value_counts().items():
                share = count / eligible if eligible else 0.0
                flags = []
                if count < 30 or share < 0.02:
                    flags.append("sparse")
                if share > 0.60:
                    flags.append("dominant")
                retention_row = retention_map.get((dimension, str(label)), {})
                rows.append({
                    "population": "pitcher", "year": int(year), "role": str(role), "source": "practical_v1",
                    "dimension": dimension, "tag": str(label), "count": int(count), "eligible_entities": eligible,
                    "eligible_share_pct": round(share * 100, 2), "effective_support": float(count),
                    "adjacent_pairs": int(retention_row.get("adjacent_pairs", 0)),
                    "retention_pct": retention_row.get("retention_pct"), "unassigned_count": eligible - int(count),
                    "unassigned_share_pct": round((eligible - int(count)) * 100 / eligible, 2) if eligible else 0.0,
                    "top_cooccurring_tag": None, "cooccurrence_share_pct": 0.0,
                    "review_flags": ",".join(flags),
                })
    return pd.DataFrame(rows)


def build_player_archetype_practical_tags(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    roster = _build_roster(root)
    retention = _retention(roster)
    distribution = _distribution(roster, retention)
    _write_parquet(roster, practical_roster_path(root), "practical_roster")
    _write_parquet(distribution, practical_distribution_path(root), "practical_distribution")
    payload = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "publication_scope": "lab_first_retrospective_full_season_descriptive_only",
        "artifacts": {"roster": str(practical_roster_path(root)), "distribution": str(practical_distribution_path(root))},
        "artifact_fingerprints": {
            "roster_sha256": _sha256(practical_roster_path(root)),
            "distribution_sha256": _sha256(practical_distribution_path(root)),
        },
        "thresholds": {
            "pitch_type_support": f"at least {MIN_TYPE_PITCHES} pitches and {MIN_TYPE_USAGE:.0%} role-season usage",
            "movement_benchmark": f"same year, role, throwing hand and exact pitch type with at least {MIN_COHORT_ENTITIES} entities",
            "strong_shape": f"at least {STRONG_SHAPE_Z:.1f} SD above the hand-normalized horizontal-movement benchmark",
            "mechanics": f"at least {MIN_STRONG_TYPES} supported strong pitch type and a usage-weighted family mean at least {STRONG_SHAPE_Z:.1f} SD above benchmark; XOR conflicts suppressed",
            "platoon_support": f"at least {MIN_PLATOON_PITCHES} pitches against each batter side",
            "platoon_strategy": f"family usage at least {MIN_PLATOON_USAGE:.0%} and at least {MIN_PLATOON_GAP:.0%} higher than against the other side",
        },
        "audit": {
            "rows": int(len(roster)), "duplicate_keys": int(roster.duplicated(["year", "player_id", "role"]).sum()),
            "mechanics_tags": {str(key): int(value) for key, value in roster["mechanics_tag"].dropna().value_counts().items()},
            "platoon_tagged_rows": int(roster["platoon_strategy_tags"].map(lambda value: len(_parse_tags(value)) > 0).sum()),
            "by_year": [
                {"year": int(year), "rows": int(len(group)), "mechanics_tagged": int(group["mechanics_tag"].notna().sum()), "platoon_tagged": int(group["platoon_strategy_tags"].map(lambda value: len(_parse_tags(value)) > 0).sum())}
                for year, group in roster.groupby("year", sort=True)
            ],
        },
        "retention": retention,
        "warnings": [
            "Pronation and Supination are hand-normalized movement-shape labels, not biomechanics measurements or injury claims.",
            "Platoon strategy tags describe pitch-family usage differences, not pitch quality, effectiveness, intent, or a recommended plan.",
            "All practical tags use complete-season data and cannot be used as same-season pre-pitch features.",
            "These tags are Lab-first supplements and do not replace or alter the frozen Slice 3 core tag columns.",
        ],
    }
    contract = practical_contract_path(root)
    temporary = contract.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(contract)
    _load_practical_roster.cache_clear()
    return payload


def get_player_archetype_practical_tags(data_dir: Path | None = None) -> dict[str, Any]:
    path = practical_contract_path(data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Practical tag contract not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def _load_practical_roster(path_value: str, modified_ns: int) -> pd.DataFrame:
    del modified_ns
    return pd.read_parquet(path_value)


def get_practical_tags_for_pitcher(year: int, pitcher_id: int, role: str, data_dir: Path | None = None) -> list[dict[str, Any]]:
    path = practical_roster_path(data_dir)
    if not path.exists():
        return []
    roster = _load_practical_roster(str(path), path.stat().st_mtime_ns)
    row = roster[
        roster["year"].eq(int(year))
        & roster["player_id"].eq(int(pitcher_id))
        & roster["role"].eq(str(role).upper())
    ]
    return _parse_tags(row.iloc[0]["practical_tags"]) if len(row) else []
