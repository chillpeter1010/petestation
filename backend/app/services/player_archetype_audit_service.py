from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path


CONTRACT_VERSION = "player_archetype_slice0_audit_v1"
DEFAULT_YEARS = tuple(range(2021, 2027))

PITCHER_RAW_FEATURES = (
    "release_speed",
    "release_spin_rate",
    "pfx_x",
    "pfx_z",
    "release_pos_x",
    "release_pos_z",
    "release_extension",
    "arm_angle",
    "plate_x",
    "plate_z",
)

BATTER_BIP_FEATURES = ("launch_speed", "launch_angle")
BATTER_SWING_FEATURES = (
    "bat_speed",
    "swing_length",
    "attack_angle",
    "attack_direction",
    "swing_path_tilt",
)

SWING_DESCRIPTIONS = (
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "hit_into_play",
    "missed_bunt",
    "foul_bunt",
)


def archetype_slice0_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice0_audit.json"


def archetype_slice0_report_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "PLAYER_ARCHETYPES_PITCH_STRATEGY.md"


def _pct(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) * 100.0 / float(denominator), 1)


def _csv_players(path: Path, id_columns: tuple[str, ...]) -> int | None:
    if not path.exists():
        return None
    frame = pd.read_csv(path, low_memory=False)
    for column in id_columns:
        if column in frame.columns:
            return int(pd.to_numeric(frame[column], errors="coerce").dropna().nunique())
    return int(len(frame))


def _pitcher_role_coverage(connection: duckdb.DuckDBPyConnection) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    counts = ",\n".join(f"count({column}) AS {column}_n" for column in PITCHER_RAW_FEATURES)
    sums = ",\n".join(f"sum({column}_n) AS {column}_n" for column in PITCHER_RAW_FEATURES)
    query = f"""
        WITH regular AS (
            SELECT pitcher,
                   game_pk,
                   coalesce(nullif(pitcher_team, ''),
                       CASE WHEN inning_topbot = 'Top' THEN home_team ELSE away_team END) AS fielding_team,
                   inning,
                   at_bat_number,
                   pitch_number,
                   {', '.join(PITCHER_RAW_FEATURES)}
            FROM pitches
            WHERE game_type = 'R' AND pitcher IS NOT NULL AND game_pk IS NOT NULL
        ),
        appearances AS (
            SELECT pitcher,
                   game_pk,
                   fielding_team,
                   min(coalesce(inning, 99) * 1000000 + coalesce(at_bat_number, 9999) * 100 + coalesce(pitch_number, 99)) AS first_sequence,
                   count(*) AS pitches,
                   {counts}
            FROM regular
            GROUP BY pitcher, game_pk, fielding_team
        ),
        classified AS (
            SELECT *,
                   CASE WHEN first_sequence = min(first_sequence) OVER (PARTITION BY game_pk, fielding_team)
                        THEN 'SP' ELSE 'RP' END AS role
            FROM appearances
        ),
        player_role AS (
            SELECT pitcher,
                   role,
                   count(*) AS appearances,
                   sum(pitches) AS pitches,
                   {sums}
            FROM classified
            GROUP BY pitcher, role
        )
        SELECT * FROM player_role
    """
    frame = connection.execute(query).fetchdf()
    rows: list[dict[str, Any]] = []
    for role in ("SP", "RP"):
        group = frame[frame["role"].eq(role)].copy()
        qualified = group[group["pitches"].ge(100)]
        features = []
        for feature in PITCHER_RAW_FEATURES:
            observed = int(group[f"{feature}_n"].sum())
            pitches = int(group["pitches"].sum())
            supported_players = int(
                (qualified[f"{feature}_n"].div(qualified["pitches"]).fillna(0).ge(0.7)).sum()
            )
            features.append(
                {
                    "feature": feature,
                    "observed_pitches": observed,
                    "coverage_pct": _pct(observed, pitches),
                    "qualified_players_with_70pct_coverage": supported_players,
                }
            )
        rows.append(
            {
                "role": role,
                "players": int(group["pitcher"].nunique()),
                "qualified_players_100_pitches": int(len(qualified)),
                "appearances": int(group["appearances"].sum()),
                "pitches": int(group["pitches"].sum()),
                "features": features,
            }
        )
    duplicate_roles = int(frame.duplicated(["pitcher", "role"]).sum())
    return rows, {"player_role_rows": int(len(frame)), "duplicate_player_role_keys": duplicate_roles}


def _batter_coverage(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    swing_values = ", ".join(f"'{value}'" for value in SWING_DESCRIPTIONS)
    observed = ",\n".join(
        [f"count({column}) AS {column}_n" for column in BATTER_BIP_FEATURES + BATTER_SWING_FEATURES]
    )
    frame = connection.execute(
        f"""
        SELECT batter,
               count(*) AS pitches_seen,
               count(DISTINCT (game_pk, at_bat_number)) AS plate_appearances,
               count(*) FILTER (WHERE type = 'X') AS balls_in_play,
               count(*) FILTER (WHERE description IN ({swing_values})) AS swings,
               {observed}
        FROM pitches
        WHERE game_type = 'R' AND batter IS NOT NULL AND game_pk IS NOT NULL
        GROUP BY batter
        """
    ).fetchdf()
    qualified = frame[frame["plate_appearances"].ge(100)].copy()
    features = []
    for feature in BATTER_BIP_FEATURES + BATTER_SWING_FEATURES:
        denominator = "balls_in_play" if feature in BATTER_BIP_FEATURES else "swings"
        denominator_total = int(frame[denominator].sum())
        observed_total = int(frame[f"{feature}_n"].sum())
        minimum = 50 if denominator == "balls_in_play" else 100
        eligible = qualified[qualified[denominator].ge(minimum)]
        supported = int(
            (eligible[f"{feature}_n"].div(eligible[denominator]).fillna(0).ge(0.7)).sum()
        )
        features.append(
            {
                "feature": feature,
                "denominator": denominator,
                "observed_rows": observed_total,
                "denominator_rows": denominator_total,
                "coverage_pct": _pct(observed_total, denominator_total),
                "qualified_players_with_70pct_coverage": supported,
            }
        )
    return {
        "players": int(frame["batter"].nunique()),
        "qualified_players_100_pa": int(len(qualified)),
        "plate_appearances": int(frame["plate_appearances"].sum()),
        "pitches_seen": int(frame["pitches_seen"].sum()),
        "features": features,
    }


def _season_source_coverage(year: int, root: Path, pitch_rows: int) -> dict[str, Any]:
    season_dir = root / f"MLB{year}"
    standard_pitcher = season_dir / f"{year}_all_pitcher_standard.csv"
    standard_batter = season_dir / f"{year}_all_batter_standard.csv"
    discipline = root / "Batter" / "discipline" / f"{year}_batter_discipline.csv"
    detailed_batter = root / "Batter" / f"{year}_batter_savant.csv"
    season_plus = root / "stuff+" / f"{year}_pitcher_stuff.csv"

    stuff_rows = 0
    stuff_pitchers = 0
    stuff_path = root / "derived" / "pitch_stuff_scores.sqlite3"
    if stuff_path.exists():
        with sqlite3.connect(stuff_path) as connection:
            stuff_rows, stuff_pitchers = connection.execute(
                "SELECT count(*), count(DISTINCT pitcher) FROM pitch_stuff_scores WHERE year = ?",
                (year,),
            ).fetchone()

    location_rows = 0
    location_pitchers = 0
    location_path = root / "derived" / "location_plus_scores.duckdb"
    if location_path.exists():
        table = f"location_pitch_scores_{year}"
        pitcher_table = f"location_pitcher_scores_{year}"
        with duckdb.connect(str(location_path), read_only=True) as connection:
            tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
            if table in tables:
                location_rows = int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
            if pitcher_table in tables:
                location_pitchers = int(connection.execute(f"SELECT count(*) FROM {pitcher_table}").fetchone()[0])

    return {
        "season_pitcher_standard_players": _csv_players(standard_pitcher, ("player_id", "MLBAMID")),
        "season_batter_standard_players": _csv_players(standard_batter, ("player_id", "MLBAMID")),
        "batter_discipline_players": _csv_players(discipline, ("MLBAMID", "player_id")),
        "detailed_batter_savant_players": _csv_players(detailed_batter, ("player_id", "MLBAMID")),
        "season_plus_pitchers": _csv_players(season_plus, ("MLBAMID", "player_id")),
        "per_pitch_stuff_rows": int(stuff_rows),
        "per_pitch_stuff_pitchers": int(stuff_pitchers),
        "per_pitch_stuff_coverage_pct": _pct(stuff_rows, pitch_rows),
        "per_pitch_location_rows": int(location_rows),
        "per_pitch_location_pitchers": int(location_pitchers),
        "per_pitch_location_coverage_pct": _pct(location_rows, pitch_rows),
    }


def _audit_year(year: int, root: Path) -> dict[str, Any]:
    path = get_season_duckdb_path(year, root)
    if not path.exists():
        return {"year": year, "status": "missing", "source": str(path)}
    with duckdb.connect(str(path), read_only=True) as connection:
        headline = connection.execute(
            """
            SELECT min(game_date) AS first_game_date,
                   max(game_date) AS last_game_date,
                   count(*) AS pitches,
                   count(DISTINCT pitcher) AS pitchers,
                   count(DISTINCT batter) AS batters,
                   count(DISTINCT (game_pk, at_bat_number)) AS plate_appearances
            FROM pitches
            WHERE game_type = 'R'
            """
        ).fetchone()
        roles, role_integrity = _pitcher_role_coverage(connection)
        batters = _batter_coverage(connection)
    pitch_rows = int(headline[2] or 0)
    return {
        "year": year,
        "status": "ready",
        "source": str(path),
        "first_game_date": str(headline[0]) if headline[0] is not None else None,
        "last_game_date": str(headline[1]) if headline[1] is not None else None,
        "pitches": pitch_rows,
        "pitchers": int(headline[3] or 0),
        "batters": int(headline[4] or 0),
        "plate_appearances": int(headline[5] or 0),
        "pitcher_roles": roles,
        "role_integrity": role_integrity,
        "batter_coverage": batters,
        "derived_sources": _season_source_coverage(year, root, pitch_rows),
    }


def _prior_archetype_audit(root: Path) -> dict[str, Any]:
    path = root / "derived" / "stamina_v2_archetypes_2026.parquet"
    result: dict[str, Any] = {
        "artifact": str(path),
        "exists": path.exists(),
        "contract_version": "stamina_v2_slice11_archetypes_v1",
        "unit": "pitcher-game start",
        "inputs": "mean Stuff+ and Location+ over appearance pitches 1–20",
        "bands": {"Low": "<95", "Average": "95–105", "High": ">105"},
        "minimum_support": "at least 10 non-null early pitches for both Stuff+ and Location+",
        "identity_decision": "retire_as_player_identity_keep_as_prior_work",
        "reason": "It describes one start's early state, uses fixed cut points and can assign the same pitcher to different cells; it is not a season-level data-driven player type.",
    }
    if not path.exists():
        return result
    with duckdb.connect() as connection:
        headline = connection.execute(
            """SELECT count(*) AS rows,
                      count(DISTINCT pitcher) AS pitchers,
                      count(DISTINCT (pitcher, game_pk)) AS appearances
               FROM read_parquet(?)""",
            [str(path)],
        ).fetchone()
        cells = connection.execute(
            """SELECT archetype_key, archetype_label, count(*) AS appearances,
                      count(DISTINCT pitcher) AS pitchers,
                      avg(early_stuff) AS early_stuff,
                      avg(early_location) AS early_location
               FROM read_parquet(?)
               GROUP BY archetype_key, archetype_label
               ORDER BY appearances DESC""",
            [str(path)],
        ).fetchall()
        duplicates = connection.execute(
            """SELECT count(*) FROM (
                   SELECT pitcher, game_pk, count(*) AS n
                   FROM read_parquet(?) GROUP BY pitcher, game_pk HAVING count(*) > 1
               )""",
            [str(path)],
        ).fetchone()[0]
    result.update(
        {
            "rows": int(headline[0]),
            "pitchers": int(headline[1]),
            "appearances": int(headline[2]),
            "duplicate_appearance_keys": int(duplicates),
            "cells": [
                {
                    "key": row[0],
                    "label": row[1],
                    "appearances": int(row[2]),
                    "pitchers": int(row[3]),
                    "share_pct": _pct(row[2], headline[0]),
                    "mean_early_stuff": round(float(row[4]), 2),
                    "mean_early_location": round(float(row[5]), 2),
                }
                for row in cells
            ],
        }
    )
    return result


def _feature_contracts() -> dict[str, list[dict[str, Any]]]:
    return {
        "pitcher": [
            {"block": "arsenal", "features": "pitch-family and exact-pitch-type usage", "direction": "style_not_quality", "denominator": "all classified pitches", "availability": "post_pitch_lag_required", "slice1_decision": "ready_2021_2026"},
            {"block": "shape", "features": "velocity, spin, horizontal/vertical movement", "direction": "pitch_type_dependent", "denominator": "tracked pitches by exact pitch type", "availability": "post_pitch_lag_required", "slice1_decision": "ready_2021_2026"},
            {"block": "release", "features": "release x/z, extension, arm angle", "direction": "style_and_stability", "denominator": "tracked pitches by exact pitch type", "availability": "post_pitch_lag_required", "slice1_decision": "ready_with_arm_angle_missingness_flag"},
            {"block": "quality", "features": "season Stuff+, Location+, Pitching+", "direction": "higher_is_better", "denominator": "model-scored pitches", "availability": "season_end_descriptive_only", "slice1_decision": "ready_2021_2026_season_level"},
            {"block": "quality", "features": "per-pitch Stuff+", "direction": "higher_is_better", "denominator": "model-scored pitches", "availability": "post_pitch_lag_required", "slice1_decision": "ready_2023_2026_only"},
            {"block": "command", "features": "plate location, zone/shadow/chase/heart/waste and Location+", "direction": "metric_dependent", "denominator": "all valid locations or applicable swings", "availability": "post_pitch_lag_required", "slice1_decision": "ready_2021_2026"},
            {"block": "approach", "features": "count mix, platoon mix, pitch-family transitions", "direction": "style_not_quality", "denominator": "classified pitches or adjacent pitch pairs", "availability": "post_pitch_lag_required", "slice1_decision": "ready_2021_2026"},
            {"block": "workload", "features": "SP/RP role, appearances, pitches per appearance and rest", "direction": "context_not_quality", "denominator": "pitcher-game appearances", "availability": "pre_pitch_after_lagging", "slice1_decision": "ready_2021_2026"},
        ],
        "batter": [
            {"block": "decision", "features": "zone swing, chase, first-pitch swing and take behavior", "direction": "metric_dependent", "denominator": "eligible pitches", "availability": "post_pitch_lag_required", "slice1_decision": "ready_2021_2026_from_raw"},
            {"block": "contact", "features": "contact, whiff and miss by pitch family", "direction": "metric_dependent", "denominator": "swings", "availability": "post_pitch_lag_required", "slice1_decision": "ready_2021_2026_from_raw"},
            {"block": "damage", "features": "exit velocity, launch angle, barrel and hard-hit", "direction": "metric_dependent", "denominator": "tracked batted balls", "availability": "post_pitch_lag_required", "slice1_decision": "ready_2021_2026_with_bip_support"},
            {"block": "swing_shape", "features": "bat speed, swing length, attack angle/direction and path tilt", "direction": "style_and_quality", "denominator": "tracked swings", "availability": "post_pitch_lag_required", "slice1_decision": "ready_2024_2026_2023_partial"},
            {"block": "matchup", "features": "pitch-family response and platoon split", "direction": "higher_result_is_better", "denominator": "pitches, swings or batted balls within matchup", "availability": "post_pitch_lag_required", "slice1_decision": "ready_2021_2026_with_shrinkage"},
        ],
    }


def build_player_archetype_slice0_audit(
    data_dir: Path | None = None,
    years: tuple[int, ...] = DEFAULT_YEARS,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    coverage = [_audit_year(year, root) for year in years]
    payload = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if all(row["status"] == "ready" for row in coverage) else "partial",
        "publication_status": "research_only",
        "scope": {
            "years": list(years),
            "game_type": "R",
            "pitcher_unit": "player-season-role",
            "batter_unit": "player-season",
        },
        "support_policy": {
            "pitcher_qualified": "at least 100 pitches in a season-role; exact pitch-type features later require at least 30 pitches",
            "batter_qualified": "at least 100 plate appearances; swing features require at least 100 swings and batted-ball features at least 50 balls in play",
            "coverage_supported": "at least 70% non-null observations within the feature's own denominator",
            "low_sample": "retain the player with reliability and null tags; never force 3–4 labels",
        },
        "prior_work": _prior_archetype_audit(root),
        "feature_contracts": _feature_contracts(),
        "year_coverage": coverage,
        "slice1_decision": {
            "proceed": True,
            "warehouse_split": "separate pitcher-season-role and batter-season tables",
            "usable_all_years": ["pitch repertoire", "pitch shape", "release geometry", "plate location", "pitcher approach", "batter decision/contact/damage", "season-level Plus"],
            "restricted": ["per-pitch Stuff+ starts in 2023", "batter swing-shape is reliable from 2024 and only partial in 2023", "2026 arm angle requires an explicit missingness flag"],
            "excluded_as_identity": ["old per-start 3x3 Stuff+/Location+ cell", "future-season or full-season values in chronological belief features"],
        },
        "warnings": [
            "Full-season tags are retrospective descriptions; they must not be joined to earlier pitches as if known at the time.",
            "Raw row coverage and qualified-player coverage use feature-specific denominators and must not be compared as if they were the same sample.",
            "SP/RP in this audit is the first fielding-team pitcher versus later pitchers in each game; opener-like starts remain SP until a later eligibility slice says otherwise.",
            "Natural tag prevalence need not be balanced. Slice 3 imbalance thresholds trigger review rather than automatic re-clustering.",
        ],
    }
    output = archetype_slice0_path(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)
    return payload


def get_player_archetype_slice0_audit(data_dir: Path | None = None) -> dict[str, Any]:
    path = archetype_slice0_path(data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Player archetype Slice 0 audit not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def render_player_archetype_slice0_report(payload: dict[str, Any]) -> str:
    prior = payload["prior_work"]
    lines = [
        "# Player Archetypes & Pitch Strategy · Slice 0 Audit",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## 結論",
        "",
        "- 可以進入 Slice 1，但投手與打者必須分開建 season warehouse，投手還要保留 SP／RP 兩種身分。",
        "- 2021–2026 的原始球路、球速、轉速、位移、出手點與落點資料足以作為共同骨架。",
        "- Per-pitch Stuff+ 只把 2023–2026 視為完整主樣本；2021 僅部分回填，2022 沒有，不可把缺值補成聯盟平均。",
        "- 打者 bat speed／swing shape 以 2024–2026 為主；2023 只能列為部分覆蓋，2021–2022 不使用。",
        "- 舊 3×3 是單場前20球狀態，不是球員整季 archetype；保留作歷史比較，不帶入新身分標籤。",
        "",
        "## 舊 3×3 盤點",
        "",
        f"Artifact共有 {prior.get('rows', 0):,} 個 pitcher-game starts、{prior.get('pitchers', 0):,} 位投手，重複鍵 {prior.get('duplicate_appearance_keys', 0)}。分類門檻為 Stuff+／Location+ 各自 Low <95、Average 95–105、High >105。",
        "",
        "| Cell | Starts | Pitchers | Share | Mean early Stuff+ | Mean early Location+ |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in prior.get("cells", []):
        lines.append(
            f"| {row['label']} | {row['appearances']:,} | {row['pitchers']:,} | {row['share_pct']:.1f}% | {row['mean_early_stuff']:.2f} | {row['mean_early_location']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## 年度與玩家覆蓋",
            "",
            "Qualified pitcher = 該 season-role 至少100球；qualified batter = 至少100 PA。Season Plus欄是現有CSV內的球員數，不等同所有曾出賽投手。",
            "",
            "| Year | Pitches | Raw pitchers | Qualified SP | Qualified RP | Raw batters | Qualified batters | Per-pitch Stuff+ | Per-pitch Location+ | Season Plus pitchers |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["year_coverage"]:
        roles = {item["role"]: item for item in row["pitcher_roles"]}
        sources = row["derived_sources"]
        lines.append(
            f"| {row['year']} | {row['pitches']:,} | {row['pitchers']:,} | {roles['SP']['qualified_players_100_pitches']:,} | {roles['RP']['qualified_players_100_pitches']:,} | {row['batters']:,} | {row['batter_coverage']['qualified_players_100_pa']:,} | {sources['per_pitch_stuff_coverage_pct']:.1f}% | {sources['per_pitch_location_coverage_pct']:.1f}% | {sources['season_plus_pitchers'] or '—'} |"
        )
    lines.extend(
        [
            "",
            "## 關鍵缺值與年代限制",
            "",
            "| Year | SP arm angle | RP arm angle | Batter swing-shape | Discipline export | Detailed batter Savant |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["year_coverage"]:
        role_features = {
            role["role"]: {feature["feature"]: feature for feature in role["features"]}
            for role in row["pitcher_roles"]
        }
        batter_features = {feature["feature"]: feature for feature in row["batter_coverage"]["features"]}
        sources = row["derived_sources"]
        lines.append(
            f"| {row['year']} | {role_features['SP']['arm_angle']['coverage_pct']:.1f}% | {role_features['RP']['arm_angle']['coverage_pct']:.1f}% | {batter_features['bat_speed']['coverage_pct']:.1f}% | {sources['batter_discipline_players'] or '—'} | {sources['detailed_batter_savant_players'] or '—'} |"
        )
    lines.extend(
        [
            "",
            "## Slice 1 資料契約",
            "",
            "| Population | Block | Denominator | Point-in-time rule | Decision |",
            "|---|---|---|---|---|",
        ]
    )
    for population in ("pitcher", "batter"):
        for item in payload["feature_contracts"][population]:
            lines.append(
                f"| {population} | {item['block']} | {item['denominator']} | {item['availability']} | {item['slice1_decision']} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            *[f"- {warning}" for warning in payload["warnings"]],
            "",
        ]
    )
    return "\n".join(lines)
