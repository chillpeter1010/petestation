from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path


CONTRACT_VERSION = "catcher_pitch_calling_prework_v1"
DEFAULT_YEARS = tuple(range(2021, 2027))
REFERENCE_YEAR = 2026


def catcher_prework_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "catcher_pitch_calling_prework.json"


def catcher_prework_report_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "PLAYER_ARCHETYPES_PITCH_STRATEGY.md"


def _pct(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) * 100.0 / float(denominator), 2) if denominator else 0.0


def _audit_year(year: int, root: Path) -> dict[str, Any]:
    path = get_season_duckdb_path(year, root)
    if not path.exists():
        return {"year": int(year), "status": "missing", "source": str(path)}

    required = {
        "game_type", "game_pk", "pitcher", "batter", "fielder_2", "pitch_type",
        "balls", "strikes", "stand", "outs_when_up", "on_1b", "on_2b", "on_3b",
    }
    with duckdb.connect(str(path), read_only=True) as connection:
        available = {row[0] for row in connection.execute("DESCRIBE pitches").fetchall()}
        missing = sorted(required - available)
        if missing:
            return {"year": int(year), "status": "missing_columns", "missing_columns": missing, "source": str(path)}

        row = connection.execute(
            """
            WITH regular AS (
                SELECT *,
                       concat(CAST(balls AS VARCHAR), '-', CAST(strikes AS VARCHAR)) AS count_state,
                       concat(
                           CASE WHEN on_1b IS NULL THEN '0' ELSE '1' END,
                           CASE WHEN on_2b IS NULL THEN '0' ELSE '1' END,
                           CASE WHEN on_3b IS NULL THEN '0' ELSE '1' END
                       ) AS base_state
                FROM pitches
                WHERE game_type = 'R' AND pitcher IS NOT NULL AND batter IS NOT NULL
            ),
            eligible AS (
                SELECT * FROM regular
                WHERE pitch_type IS NOT NULL AND fielder_2 IS NOT NULL
            ),
            catchers AS (
                SELECT fielder_2, count(*) AS pitches, count(DISTINCT game_pk) AS games,
                       count(DISTINCT pitcher) AS pitchers
                FROM eligible GROUP BY fielder_2
            ),
            pairs AS (
                SELECT pitcher, fielder_2, count(*) AS pitches
                FROM eligible GROUP BY pitcher, fielder_2
            ),
            catcher_cells AS (
                SELECT fielder_2, count_state, stand, outs_when_up, base_state, count(*) AS pitches
                FROM eligible GROUP BY ALL
            ),
            pair_cells AS (
                SELECT pitcher, fielder_2, count_state, stand, outs_when_up, base_state, count(*) AS pitches
                FROM eligible GROUP BY ALL
            )
            SELECT
                (SELECT count(*) FROM regular) AS regular_pitches,
                (SELECT count(fielder_2) FROM regular) AS catcher_linked_pitches,
                (SELECT count(*) FROM eligible) AS model_eligible_pitches,
                (SELECT count(*) FROM catchers) AS catchers,
                (SELECT count(*) FROM catchers WHERE pitches >= 500) AS catchers_500,
                (SELECT median(pitches) FROM catchers) AS median_catcher_pitches,
                (SELECT count(*) FROM pairs) AS pitcher_catcher_pairs,
                (SELECT count(*) FROM pairs WHERE pitches >= 100) AS pairs_100,
                (SELECT median(pitches) FROM pairs) AS median_pair_pitches,
                (SELECT count(*) FROM catcher_cells) AS catcher_context_cells,
                (SELECT count(*) FROM catcher_cells WHERE pitches >= 20) AS catcher_cells_20,
                (SELECT count(*) FROM catcher_cells WHERE pitches >= 50) AS catcher_cells_50,
                (SELECT count(*) FROM pair_cells) AS pair_context_cells,
                (SELECT count(*) FROM pair_cells WHERE pitches >= 20) AS pair_cells_20,
                (SELECT count(*) FROM pair_cells WHERE pitches >= 50) AS pair_cells_50
            """
        ).fetchone()
        names = [item[0] for item in connection.description]

    values = dict(zip(names, row, strict=True))
    return {
        "year": int(year),
        "status": "ready",
        "source": str(path),
        **{key: int(value or 0) for key, value in values.items()},
        "catcher_id_coverage_pct": _pct(values["catcher_linked_pitches"], values["regular_pitches"]),
        "catcher_cells_20_pct": _pct(values["catcher_cells_20"], values["catcher_context_cells"]),
        "catcher_cells_50_pct": _pct(values["catcher_cells_50"], values["catcher_context_cells"]),
        "pair_cells_20_pct": _pct(values["pair_cells_20"], values["pair_context_cells"]),
        "pair_cells_50_pct": _pct(values["pair_cells_50"], values["pair_context_cells"]),
    }


def _chronological_support(year: int, root: Path) -> dict[str, Any]:
    path = get_season_duckdb_path(year, root)
    with duckdb.connect(str(path), read_only=True) as connection:
        row = connection.execute(
            """
            WITH eligible AS (
                SELECT *,
                       concat(CAST(balls AS VARCHAR), '-', CAST(strikes AS VARCHAR)) AS count_state,
                       concat(
                           CASE WHEN on_1b IS NULL THEN '0' ELSE '1' END,
                           CASE WHEN on_2b IS NULL THEN '0' ELSE '1' END,
                           CASE WHEN on_3b IS NULL THEN '0' ELSE '1' END
                       ) AS base_state
                FROM pitches
                WHERE game_type = 'R' AND pitcher IS NOT NULL AND batter IS NOT NULL
                  AND fielder_2 IS NOT NULL AND pitch_type IS NOT NULL
            ),
            ordered AS (
                SELECT *,
                       row_number() OVER (
                           PARTITION BY pitcher, batter
                           ORDER BY game_date, game_pk, at_bat_number, pitch_number
                       ) - 1 AS prior_h2h,
                       row_number() OVER (
                           PARTITION BY fielder_2, count_state, stand, outs_when_up, base_state
                           ORDER BY game_date, game_pk, at_bat_number, pitch_number
                       ) - 1 AS prior_catcher_context,
                       row_number() OVER (
                           PARTITION BY pitcher, fielder_2, count_state, stand, outs_when_up, base_state
                           ORDER BY game_date, game_pk, at_bat_number, pitch_number
                       ) - 1 AS prior_pair_context,
                       row_number() OVER (
                           PARTITION BY pitcher, count_state, stand
                           ORDER BY game_date, game_pk, at_bat_number, pitch_number
                       ) - 1 AS prior_pitcher_count_stand
                FROM eligible
            )
            SELECT count(*) AS pitches,
                   avg(CAST(prior_h2h >= 5 AS INTEGER)) * 100 AS h2h_5,
                   avg(CAST(prior_h2h >= 10 AS INTEGER)) * 100 AS h2h_10,
                   avg(CAST(prior_h2h >= 20 AS INTEGER)) * 100 AS h2h_20,
                   avg(CAST(prior_catcher_context >= 5 AS INTEGER)) * 100 AS catcher_context_5,
                   avg(CAST(prior_catcher_context >= 10 AS INTEGER)) * 100 AS catcher_context_10,
                   avg(CAST(prior_catcher_context >= 20 AS INTEGER)) * 100 AS catcher_context_20,
                   avg(CAST(prior_pair_context >= 5 AS INTEGER)) * 100 AS pair_context_5,
                   avg(CAST(prior_pair_context >= 10 AS INTEGER)) * 100 AS pair_context_10,
                   avg(CAST(prior_pair_context >= 20 AS INTEGER)) * 100 AS pair_context_20,
                   avg(CAST(prior_pitcher_count_stand >= 5 AS INTEGER)) * 100 AS pitcher_count_stand_5,
                   avg(CAST(prior_pitcher_count_stand >= 10 AS INTEGER)) * 100 AS pitcher_count_stand_10,
                   avg(CAST(prior_pitcher_count_stand >= 20 AS INTEGER)) * 100 AS pitcher_count_stand_20
            FROM ordered
            """
        ).fetchone()
        names = [item[0] for item in connection.description]
    values = dict(zip(names, row, strict=True))
    return {
        "year": int(year),
        "pitches": int(values.pop("pitches") or 0),
        **{key: round(float(value or 0), 2) for key, value in values.items()},
    }


def build_catcher_pitch_calling_prework(
    years: tuple[int, ...] = DEFAULT_YEARS,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    coverage = [_audit_year(int(year), root) for year in years]
    payload = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if all(row["status"] == "ready" for row in coverage) else "partial",
        "scope": {"years": [int(year) for year in years], "reference_year": REFERENCE_YEAR},
        "coverage": coverage,
        "chronological_support": _chronological_support(REFERENCE_YEAR, root),
        "slice4_contract": {
            "direct_pre_pitch_features": [
                "pitcher_id", "batter_id", "catcher_id", "balls", "strikes", "batter_side",
                "outs", "base_state", "inning", "score_margin", "prior_pitch", "prior_result",
            ],
            "chronological_priors": [
                "pitcher_count_side_mix", "catcher_context_residual", "pitcher_catcher_pair_residual",
                "batter_archetype_prior", "head_to_head_prior", "available_arsenal",
            ],
            "backoff_order": [
                "role_and_archetype", "pitcher_count_side", "catcher_residual",
                "pitcher_catcher_pair", "head_to_head_when_supported",
            ],
            "minimum_rules": {
                "do_not_materialize_full_cartesian_probability_table": True,
                "all_rolling_features_use_strictly_earlier_pitches": True,
                "same_season_full_year_tags_forbidden": True,
                "unseen_or_low_support_states_back_off": True,
                "catcher_effect_requires_pitcher_and_team_adjustment": True,
            },
        },
        "interpretation_policy": {
            "allowed": "catcher-associated pitch-selection tendency after pitcher, arsenal and context adjustment",
            "forbidden": "causal catcher pitch-calling skill or responsibility for an observed outcome",
            "reason": "Statcast observes the catcher on the field, not who selected the pitch; pitcher, catcher, coach and PitchCom agency are not separately identified.",
        },
        "decision": "proceed_with_hierarchical_features_not_sparse_cross_tabs",
    }
    output = catcher_prework_path(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def get_catcher_pitch_calling_prework(data_dir: Path | None = None) -> dict[str, Any]:
    return json.loads(catcher_prework_path(data_dir).read_text(encoding="utf-8"))


def render_catcher_prework_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Catcher Pitch-Calling Prework",
        "",
        f"Contract: `{payload['contract_version']}`  ",
        f"Status: **{payload['status']}**  ",
        f"Decision: `{payload['decision']}`",
        "",
        "## Coverage and sparsity",
        "",
        "| Year | Catcher ID | Catchers | Median pitches | Catcher context ≥20 | Pitcher-catcher context ≥20 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["coverage"]:
        if row["status"] != "ready":
            lines.append(f"| {row['year']} | unavailable | - | - | - | - |")
            continue
        lines.append(
            f"| {row['year']} | {row['catcher_id_coverage_pct']:.2f}% | {row['catchers']} | "
            f"{row['median_catcher_pitches']:,} | {row['catcher_cells_20_pct']:.2f}% | {row['pair_cells_20_pct']:.2f}% |"
        )
    support = payload["chronological_support"]
    lines.extend(
        [
            "",
            f"## Strictly prior support ({support['year']})",
            "",
            "| Prior level | ≥5 prior pitches | ≥10 | ≥20 |",
            "|---|---:|---:|---:|",
            f"| Pitcher × count × batter side | {support['pitcher_count_stand_5']:.2f}% | {support['pitcher_count_stand_10']:.2f}% | {support['pitcher_count_stand_20']:.2f}% |",
            f"| Catcher × full context | {support['catcher_context_5']:.2f}% | {support['catcher_context_10']:.2f}% | {support['catcher_context_20']:.2f}% |",
            f"| Pitcher × catcher × full context | {support['pair_context_5']:.2f}% | {support['pair_context_10']:.2f}% | {support['pair_context_20']:.2f}% |",
            f"| Pitcher × batter head-to-head | {support['h2h_5']:.2f}% | {support['h2h_10']:.2f}% | {support['h2h_20']:.2f}% |",
            "",
            "## Frozen interpretation",
            "",
            "Use hierarchical priors, shrinkage and model interactions. Do not materialize every condition combination as an independent probability cell.",
            "Catcher features describe catcher-associated tendencies only after pitcher, arsenal, team and context adjustment. They do not identify who called the pitch and cannot be presented as causal catcher skill.",
            "",
        ]
    )
    return "\n".join(lines)
