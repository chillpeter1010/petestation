from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path
from app.services.player_archetype_warehouse_service import YEARS, pitcher_warehouse_path


CONTRACT_VERSION = "player_archetype_slice2a_transparent_tags_v1"
VALID_PITCH_TYPES = ("FF", "FA", "SI", "FC", "SL", "ST", "CU", "KC", "SV", "CH", "FS", "FO", "CS", "EP", "KN", "SC")
DIMENSIONS = ("arsenal_depth", "arsenal_concentration", "primary_pair", "arm_slot")


def slice2a_tags_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_pitcher_tags_slice2a_v1.parquet"


def slice2a_contract_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice2a.json"


def slice2a_report_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "PLAYER_ARCHETYPES_PITCH_STRATEGY.md"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.parquet")
    with duckdb.connect() as connection:
        connection.register("tags", frame)
        connection.execute("COPY tags TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(temporary)])
        connection.unregister("tags")
    temporary.replace(path)


def _pitch_type_rows(year: int, root: Path) -> pd.DataFrame:
    valid = ", ".join(f"'{value}'" for value in VALID_PITCH_TYPES)
    with duckdb.connect(str(get_season_duckdb_path(year, root)), read_only=True) as connection:
        return connection.execute(
            f"""
            WITH base AS (
                SELECT cast(pitcher AS BIGINT) AS player_id, game_pk,
                       coalesce(nullif(pitcher_team, ''),
                           CASE WHEN inning_topbot = 'Top' THEN home_team ELSE away_team END) AS team,
                       inning, at_bat_number, pitch_number, upper(pitch_type) AS pitch_type,
                       arm_angle,
                       min(coalesce(inning, 99) * 1000000 + coalesce(at_bat_number, 9999) * 100 + coalesce(pitch_number, 99))
                           OVER (PARTITION BY pitcher, game_pk) AS first_sequence
                FROM pitches
                WHERE game_type = 'R' AND pitcher IS NOT NULL AND game_pk IS NOT NULL
            ), classified AS (
                SELECT *, CASE WHEN first_sequence = min(first_sequence) OVER (PARTITION BY game_pk, team)
                               THEN 'SP' ELSE 'RP' END AS role
                FROM base
            )
            , entity_arm AS (
                SELECT player_id, role, median(arm_angle) AS overall_arm_angle
                FROM classified GROUP BY player_id, role
            ), pitch_types AS (
                SELECT player_id, role, pitch_type, count(*) AS pitch_count,
                       median(arm_angle) AS pitch_type_arm_angle,
                       count(arm_angle) AS pitch_type_arm_angle_pitches
                FROM classified
                WHERE pitch_type IN ({valid})
                GROUP BY player_id, role, pitch_type
            )
            SELECT {year} AS year, p.*, a.overall_arm_angle
            FROM pitch_types p JOIN entity_arm a USING (player_id, role)
            ORDER BY player_id, role, pitch_count DESC, pitch_type
            """
        ).fetchdf()


def _arm_slot(angle: float, hand: str) -> str:
    if angle >= 60.0:
        slot = "Overhand"
    elif angle >= 45.0:
        slot = "High 3/4"
    elif angle >= 30.0:
        slot = "3/4"
    elif angle >= 15.0:
        slot = "Low 3/4"
    elif angle >= 5.0:
        slot = "Sidearm"
    else:
        slot = "Submarine"
    prefix = "LHP" if str(hand).upper() == "L" else "RHP"
    return f"{prefix} {slot}"


def _base_row(row: Any, dimension: str) -> dict[str, Any]:
    return {
        "year": int(row.year),
        "player_id": int(row.player_id),
        "role": row.role,
        "display_name": row.display_name,
        "team": row.team,
        "throws": row.throws,
        "dimension": dimension,
        "tag": None,
        "assignment_status": "ineligible",
        "unassigned_reason": "sample_not_eligible",
        "sample_reliability": float(row.sample_reliability),
        "pitches": int(row.pitches),
        "listed_pitch_types": None,
        "core_pitch_types": None,
        "support_pitch_types": None,
        "show_me_pitch_types": None,
        "effective_arsenal_size": None,
        "top_two_usage_pct": None,
        "primary_pitch": None,
        "secondary_pitch": None,
        "primary_pair_usage_pct": None,
        "arm_angle_median": None,
        "arm_angle_coverage_pct": float(row.arm_angle_coverage_pct),
        "arm_slot_pitch_type_range": None,
        "arm_slot_consistency": None,
        "repertoire": None,
        "feature_time_scope": row.feature_time_scope,
    }


def _entity_metrics(group: pd.DataFrame, total_pitches: int) -> dict[str, Any]:
    ordered = group.sort_values(["pitch_count", "pitch_type"], ascending=[False, True], kind="stable").copy()
    ordered["usage"] = ordered["pitch_count"] / total_pitches
    probabilities = ordered["pitch_count"].to_numpy(dtype=float)
    probabilities = probabilities / probabilities.sum()
    effective_size = float(1.0 / np.square(probabilities).sum())
    core = ordered[(ordered["usage"] >= 0.10) & (ordered["pitch_count"] >= 20)]
    support = ordered[(ordered["usage"] >= 0.05) & (ordered["pitch_count"] >= 10)]
    show_me = ordered[(ordered["usage"] >= 0.01) & (ordered["pitch_count"] >= 5)]
    top = ordered.head(2)
    top_two_usage = float(top["usage"].sum() * 100.0)
    arm_types = ordered[
        (ordered["usage"] >= 0.05)
        & (ordered["pitch_type_arm_angle_pitches"] >= 20)
        & ordered["pitch_type_arm_angle"].notna()
    ]
    arm_range = None
    consistency = None
    if len(arm_types) >= 2:
        arm_range = float(arm_types["pitch_type_arm_angle"].max() - arm_types["pitch_type_arm_angle"].min())
        consistency = (
            "Consistent Arm Slot"
            if arm_range < 5.0
            else ("Pitch-Dependent Arm Slot" if arm_range >= 8.0 else "Moderate Arm-Slot Variation")
        )
    repertoire = [
        {
            "pitch_type": item.pitch_type,
            "pitches": int(item.pitch_count),
            "usage_pct": round(float(item.usage * 100.0), 1),
            "arm_angle": round(float(item.pitch_type_arm_angle), 1)
            if pd.notna(item.pitch_type_arm_angle)
            else None,
        }
        for item in ordered.itertuples(index=False)
    ]
    return {
        "listed": int(len(ordered)),
        "core": int(len(core)),
        "support": int(len(support)),
        "show_me": int(len(show_me)),
        "effective_size": effective_size,
        "top_two_usage": top_two_usage,
        "primary": str(top.iloc[0]["pitch_type"]) if len(top) else None,
        "secondary": str(top.iloc[1]["pitch_type"]) if len(top) > 1 else None,
        "secondary_usage": float(top.iloc[1]["usage"] * 100.0) if len(top) > 1 else 0.0,
        "arm_median": float(ordered["overall_arm_angle"].iloc[0])
        if pd.notna(ordered["overall_arm_angle"].iloc[0])
        else None,
        "arm_range": arm_range,
        "consistency": consistency,
        "repertoire": repertoire,
    }


def _depth_tag(metrics: dict[str, Any], role: str) -> str:
    if metrics["top_two_usage"] >= 85.0 and metrics["effective_size"] <= 2.5:
        return f"Two-Pitch {role}"
    if metrics["support"] >= 6 or metrics["effective_size"] >= 5.0:
        return f"Versatile {role}"
    if metrics["support"] <= 3 and metrics["effective_size"] < 3.5:
        return f"Three-Pitch {role}"
    return f"Multi-Pitch {role}"


def _tag_rows(warehouse: pd.DataFrame, pitch_types: pd.DataFrame) -> pd.DataFrame:
    grouped = {
        (int(year), int(player_id), str(role)): group
        for (year, player_id, role), group in pitch_types.groupby(["year", "player_id", "role"], sort=False)
    }
    output: list[dict[str, Any]] = []
    for row in warehouse.itertuples(index=False):
        key = (int(row.year), int(row.player_id), str(row.role))
        group = grouped.get(key)
        metrics = _entity_metrics(group, int(row.pitches)) if group is not None and not group.empty else None
        for dimension in DIMENSIONS:
            item = _base_row(row, dimension)
            if not bool(row.archetype_eligible):
                output.append(item)
                continue
            if metrics is None:
                item.update({"assignment_status": "unavailable", "unassigned_reason": "no_valid_pitch_types"})
                output.append(item)
                continue
            item.update(
                {
                    "listed_pitch_types": metrics["listed"],
                    "core_pitch_types": metrics["core"],
                    "support_pitch_types": metrics["support"],
                    "show_me_pitch_types": metrics["show_me"],
                    "effective_arsenal_size": metrics["effective_size"],
                    "top_two_usage_pct": metrics["top_two_usage"],
                    "primary_pitch": metrics["primary"],
                    "secondary_pitch": metrics["secondary"],
                    "primary_pair_usage_pct": metrics["top_two_usage"],
                    "arm_angle_median": metrics["arm_median"],
                    "arm_slot_pitch_type_range": metrics["arm_range"],
                    "arm_slot_consistency": metrics["consistency"],
                    "repertoire": json.dumps(metrics["repertoire"], ensure_ascii=False),
                }
            )
            tag = None
            reason = None
            if dimension == "arsenal_depth":
                tag = _depth_tag(metrics, str(row.role))
            elif dimension == "arsenal_concentration":
                tag = (
                    "Concentrated Arsenal"
                    if metrics["top_two_usage"] >= 85.0
                    else (
                        "Distributed Arsenal"
                        if metrics["top_two_usage"] <= 55.0 and metrics["effective_size"] >= 4.0
                        else "Balanced Arsenal"
                    )
                )
            elif dimension == "primary_pair":
                if metrics["secondary"] is not None and metrics["secondary_usage"] >= 10.0:
                    tag = f"{metrics['primary']}-{metrics['secondary']} Primary Pair"
                else:
                    reason = "secondary_pitch_below_10_pct"
            elif dimension == "arm_slot":
                if row.arm_angle_coverage_pct >= 70.0 and metrics["arm_median"] is not None:
                    tag = _arm_slot(metrics["arm_median"], str(row.throws))
                else:
                    reason = "arm_angle_coverage_below_70_pct"
            item.update(
                {
                    "tag": tag,
                    "assignment_status": "supported" if tag is not None else "unavailable",
                    "unassigned_reason": reason,
                }
            )
            output.append(item)
    return pd.DataFrame(output)


def _audit(tags: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": int(len(tags)),
        "entities": int(tags[["year", "player_id", "role"]].drop_duplicates().shape[0]),
        "duplicate_entity_dimensions": int(tags.duplicated(["year", "player_id", "role", "dimension"]).sum()),
        "supported_rows": int(tags["tag"].notna().sum()),
        "by_dimension": [
            {
                "dimension": dimension,
                "rows": int(len(group)),
                "supported": int(group["tag"].notna().sum()),
                "unavailable": int(group["tag"].isna().sum()),
            }
            for dimension, group in tags.groupby("dimension", sort=True)
        ],
    }


def build_player_archetype_slice2a(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    warehouse = pd.read_parquet(pitcher_warehouse_path(root))
    pitch_types = pd.concat([_pitch_type_rows(year, root) for year in YEARS], ignore_index=True)
    tags = _tag_rows(warehouse, pitch_types)
    path = slice2a_tags_path(root)
    _write_parquet(tags, path)
    audit = _audit(tags)
    examples = tags[
        tags["year"].eq(2026)
        & tags["display_name"].isin(["Paul Sewald", "Seth Lugo", "Trey Yesavage", "Chris Sale"])
    ][["display_name", "role", "dimension", "tag", "effective_arsenal_size", "top_two_usage_pct", "arm_angle_median", "arm_slot_consistency"]]
    payload = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if audit["duplicate_entity_dimensions"] == 0 else "invalid",
        "publication_status": "research_only_full_season_descriptive",
        "artifacts": {"pitcher_tags": str(path)},
        "artifact_fingerprints": {
            "pitcher_tags_sha256": _sha256(path),
            "pitcher_warehouse_sha256": _sha256(pitcher_warehouse_path(root)),
        },
        "thresholds": {
            "eligible": "Slice 1 archetype_eligible: at least 100 role pitches and not low-volume position-player pitching",
            "core_pitch": "usage >= 10% and at least 20 pitches",
            "support_pitch": "usage >= 5% and at least 10 pitches",
            "show_me_pitch": "usage >= 1% and at least 5 pitches",
            "two_pitch": "top-two usage >= 85% and inverse-Simpson effective arsenal <= 2.5",
            "versatile": "at least 6 support pitches or effective arsenal >= 5.0",
            "primary_pair": "second pitch usage >= 10%",
            "arm_slot": {"Overhand": ">=60", "High 3/4": "45-<60", "3/4": "30-<45", "Low 3/4": "15-<30", "Sidearm": "5-<15", "Submarine": "<5"},
            "arm_slot_support": "season-role Arm Angle coverage >= 70%",
            "arm_slot_consistency": "supported pitch-type range <5 degrees is consistent; >=8 degrees is pitch-dependent",
        },
        "audit": audit,
        "examples": examples.where(pd.notna(examples), None).to_dict(orient="records"),
        "warnings": [
            "These tags are transparent rules, not learned mixture components and not quality grades.",
            "Pitch classifications inherit Statcast pitch_type labels and can change when MLB reclassifies a pitch.",
            "Effective arsenal size measures usage diversity; it does not prove every listed pitch is equally effective.",
            "Arm Slot uses official tracked Arm Angle only; low-coverage rows remain unassigned and are never inferred from release coordinates.",
            "All tags are full-season descriptive and cannot be used as same-season pre-pitch beliefs.",
        ],
    }
    contract = slice2a_contract_path(root)
    temporary = contract.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(contract)
    return payload


def get_player_archetype_slice2a(data_dir: Path | None = None) -> dict[str, Any]:
    path = slice2a_contract_path(data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Player archetype Slice 2A contract not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def render_slice2a_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Player Archetypes & Pitch Strategy · Slice 2A Transparent Tags",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Coverage",
        "",
        "| Dimension | Rows | Supported | Unavailable |",
        "|---|---:|---:|---:|",
    ]
    for row in payload["audit"]["by_dimension"]:
        lines.append(f"| {row['dimension']} | {row['rows']:,} | {row['supported']:,} | {row['unavailable']:,} |")
    lines.extend(
        [
            "",
            "## 2026 examples",
            "",
            "| Player | Role | Dimension | Tag | Effective arsenal | Top-two usage | Arm angle | Consistency |",
            "|---|---|---|---|---:|---:|---:|---|",
        ]
    )
    for row in payload["examples"]:
        lines.append(
            f"| {row['display_name']} | {row['role']} | {row['dimension']} | {row['tag'] or '—'} | "
            f"{row['effective_arsenal_size']:.2f} | {row['top_two_usage_pct']:.1f}% | "
            f"{row['arm_angle_median']:.1f}° | {row['arm_slot_consistency'] or '—'} |"
        )
    lines.extend(["", "## Warnings", "", *[f"- {warning}" for warning in payload["warnings"]], ""])
    return "\n".join(lines)
