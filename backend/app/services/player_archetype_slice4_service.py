from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path
from app.services.player_archetype_slice3_service import slice3_roster_path


CONTRACT_VERSION = "player_archetype_slice4_decision_states_v1"
DEFAULT_YEARS = tuple(range(2021, 2027))


def slice4_warehouse_path(year: int, data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / f"player_archetype_pitch_decisions_{int(year)}_v1.parquet"


def slice4_contract_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice4.json"


def slice4_report_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "PLAYER_ARCHETYPES_PITCH_STRATEGY.md"


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _warehouse_query(year: int, roster_path: Path) -> str:
    return f"""
        WITH eligible AS (
            SELECT
                {int(year)}::INTEGER AS year,
                CAST(game_date AS DATE) AS game_date,
                CAST(game_pk AS BIGINT) AS game_pk,
                CAST(at_bat_number AS INTEGER) AS at_bat_number,
                CAST(pitch_number AS INTEGER) AS pitch_number,
                CAST(pitcher AS BIGINT) AS pitcher_id,
                CAST(batter AS BIGINT) AS batter_id,
                CAST(fielder_2 AS BIGINT) AS catcher_id,
                nullif(CAST(player_name AS VARCHAR), '') AS pitcher_name,
                nullif(CAST(pitcher_team AS VARCHAR), '') AS pitcher_team,
                nullif(CAST(batter_team AS VARCHAR), '') AS batter_team,
                nullif(CAST(home_team AS VARCHAR), '') AS home_team,
                nullif(CAST(away_team AS VARCHAR), '') AS away_team,
                nullif(CAST(p_throws AS VARCHAR), '') AS pitcher_throws,
                nullif(CAST(stand AS VARCHAR), '') AS batter_side,
                CAST(balls AS INTEGER) AS balls,
                CAST(strikes AS INTEGER) AS strikes,
                concat(CAST(balls AS VARCHAR), '-', CAST(strikes AS VARCHAR)) AS count_state,
                CAST(outs_when_up AS INTEGER) AS outs,
                concat(
                    CASE WHEN on_1b IS NULL THEN '0' ELSE '1' END,
                    CASE WHEN on_2b IS NULL THEN '0' ELSE '1' END,
                    CASE WHEN on_3b IS NULL THEN '0' ELSE '1' END
                ) AS base_state,
                CAST((on_1b IS NOT NULL)::INTEGER + (on_2b IS NOT NULL)::INTEGER + (on_3b IS NOT NULL)::INTEGER AS INTEGER) AS runners_on,
                CAST(inning AS INTEGER) AS inning,
                nullif(CAST(inning_topbot AS VARCHAR), '') AS inning_half,
                CAST(coalesce(fld_score,
                    CASE WHEN inning_topbot = 'Top' THEN home_score ELSE away_score END) AS INTEGER) AS fielding_score,
                CAST(coalesce(bat_score,
                    CASE WHEN inning_topbot = 'Top' THEN away_score ELSE home_score END) AS INTEGER) AS batting_score,
                CAST(coalesce(fld_score,
                    CASE WHEN inning_topbot = 'Top' THEN home_score ELSE away_score END)
                    - coalesce(bat_score,
                    CASE WHEN inning_topbot = 'Top' THEN away_score ELSE home_score END) AS INTEGER) AS pitcher_score_margin,
                CAST(n_thruorder_pitcher AS INTEGER) AS times_through_order,
                CASE WHEN p_throws = stand THEN 'same_side' ELSE 'opposite_side' END AS platoon_state,
                CAST(pitch_type AS VARCHAR) AS target_pitch_type,
                CAST(pitch_name AS VARCHAR) AS target_pitch_name,
                CASE
                    WHEN pitch_type IN ('FF', 'SI', 'FC') THEN 'Fastball'
                    WHEN pitch_type IN ('SL', 'ST', 'CU', 'KC', 'SV') THEN 'Breaking'
                    WHEN pitch_type IN ('CH', 'FS', 'FO', 'SC') THEN 'Offspeed'
                    ELSE 'Other'
                END AS target_pitch_family,
                CAST(description AS VARCHAR) AS observed_description,
                CAST(events AS VARCHAR) AS observed_pa_event,
                CAST(release_speed AS DOUBLE) AS observed_release_speed,
                CAST(plate_x AS DOUBLE) AS observed_plate_x,
                CAST(plate_z AS DOUBLE) AS observed_plate_z,
                CAST(delta_run_exp AS DOUBLE) AS observed_delta_run_exp,
                coalesce(nullif(CAST(pitcher_team AS VARCHAR), ''),
                    CASE WHEN inning_topbot = 'Top' THEN home_team ELSE away_team END) AS fielding_team
            FROM season.pitches
            WHERE game_type = 'R'
              AND game_pk IS NOT NULL
              AND at_bat_number IS NOT NULL
              AND pitch_number IS NOT NULL
              AND pitcher IS NOT NULL
              AND batter IS NOT NULL
              AND fielder_2 IS NOT NULL
              AND pitch_type IS NOT NULL
        ),
        appearance_state AS (
            SELECT *,
                first_value(pitcher_id) OVER (
                    PARTITION BY game_pk, fielding_team
                    ORDER BY at_bat_number, pitch_number
                ) AS game_starting_pitcher_id,
                row_number() OVER (
                    PARTITION BY game_pk, pitcher_id
                    ORDER BY at_bat_number, pitch_number
                ) AS appearance_pitch_number,
                lag(target_pitch_type) OVER (
                    PARTITION BY game_pk, at_bat_number
                    ORDER BY pitch_number
                ) AS prior_pitch_type,
                lag(target_pitch_family) OVER (
                    PARTITION BY game_pk, at_bat_number
                    ORDER BY pitch_number
                ) AS prior_pitch_family,
                lag(observed_description) OVER (
                    PARTITION BY game_pk, at_bat_number
                    ORDER BY pitch_number
                ) AS prior_pitch_result,
                lag(observed_release_speed) OVER (
                    PARTITION BY game_pk, at_bat_number
                    ORDER BY pitch_number
                ) AS prior_release_speed,
                lag(observed_plate_x) OVER (
                    PARTITION BY game_pk, at_bat_number
                    ORDER BY pitch_number
                ) AS prior_plate_x,
                lag(observed_plate_z) OVER (
                    PARTITION BY game_pk, at_bat_number
                    ORDER BY pitch_number
                ) AS prior_plate_z,
                lag(pitch_number) OVER (
                    PARTITION BY game_pk, at_bat_number
                    ORDER BY pitch_number
                ) AS prior_pitch_number
            FROM eligible
        ),
        role_state AS (
            SELECT *,
                CASE WHEN pitcher_id = game_starting_pitcher_id THEN 'SP' ELSE 'RP' END AS pitcher_role
            FROM appearance_state
        ),
        chronological AS (
            SELECT *,
                row_number() OVER (
                    PARTITION BY pitcher_id, pitcher_role
                    ORDER BY game_date, game_pk, at_bat_number, pitch_number
                ) - 1 AS prior_pitcher_pitches,
                row_number() OVER (
                    PARTITION BY batter_id
                    ORDER BY game_date, game_pk, at_bat_number, pitch_number
                ) - 1 AS prior_batter_pitches,
                row_number() OVER (
                    PARTITION BY catcher_id
                    ORDER BY game_date, game_pk, at_bat_number, pitch_number
                ) - 1 AS prior_catcher_pitches,
                row_number() OVER (
                    PARTITION BY pitcher_id, catcher_id
                    ORDER BY game_date, game_pk, at_bat_number, pitch_number
                ) - 1 AS prior_pair_pitches,
                row_number() OVER (
                    PARTITION BY pitcher_id, pitcher_role, balls, strikes, batter_side
                    ORDER BY game_date, game_pk, at_bat_number, pitch_number
                ) - 1 AS prior_pitcher_count_side_pitches,
                row_number() OVER (
                    PARTITION BY catcher_id, balls, strikes, batter_side, outs, base_state
                    ORDER BY game_date, game_pk, at_bat_number, pitch_number
                ) - 1 AS prior_catcher_context_pitches,
                row_number() OVER (
                    PARTITION BY pitcher_id, catcher_id, balls, strikes, batter_side, outs, base_state
                    ORDER BY game_date, game_pk, at_bat_number, pitch_number
                ) - 1 AS prior_pair_context_pitches,
                row_number() OVER (
                    PARTITION BY pitcher_id, batter_id
                    ORDER BY game_date, game_pk, at_bat_number, pitch_number
                ) - 1 AS prior_h2h_pitches,
                list(DISTINCT target_pitch_type) OVER (
                    PARTITION BY pitcher_id, pitcher_role
                    ORDER BY game_date, game_pk, at_bat_number, pitch_number
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ) AS prior_available_arsenal,
                histogram(target_pitch_type) OVER (
                    PARTITION BY pitcher_id, pitcher_role, balls, strikes, batter_side
                    ORDER BY game_date, game_pk, at_bat_number, pitch_number
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ) AS prior_pitcher_count_side_mix,
                histogram(target_pitch_type) OVER (
                    PARTITION BY catcher_id, balls, strikes, batter_side, outs, base_state
                    ORDER BY game_date, game_pk, at_bat_number, pitch_number
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ) AS prior_catcher_context_mix,
                histogram(target_pitch_type) OVER (
                    PARTITION BY pitcher_id, catcher_id, balls, strikes, batter_side, outs, base_state
                    ORDER BY game_date, game_pk, at_bat_number, pitch_number
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ) AS prior_pair_context_mix,
                histogram(target_pitch_type) OVER (
                    PARTITION BY pitcher_id, batter_id
                    ORDER BY game_date, game_pk, at_bat_number, pitch_number
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ) AS prior_h2h_mix
            FROM role_state
        ),
        tags AS (
            SELECT * FROM read_parquet('{_sql_path(roster_path)}')
        )
        SELECT
            concat(CAST(c.year AS VARCHAR), ':', CAST(c.game_pk AS VARCHAR), ':',
                   CAST(c.at_bat_number AS VARCHAR), ':', CAST(c.pitch_number AS VARCHAR), ':',
                   CAST(c.pitcher_id AS VARCHAR)) AS decision_id,
            c.* EXCLUDE (fielding_team, game_starting_pitcher_id),
            CASE
                WHEN c.prior_pair_context_pitches >= 20 THEN 'pitcher_catcher_context'
                WHEN c.prior_pitcher_count_side_pitches >= 20 THEN 'pitcher_count_side'
                WHEN c.prior_catcher_context_pitches >= 20 THEN 'catcher_context'
                WHEN c.prior_pitcher_pitches >= 20 THEN 'pitcher_role'
                ELSE 'role_archetype'
            END AS context_backoff_level,
            CASE
                WHEN c.prior_h2h_pitches >= 20 THEN 'supported'
                WHEN c.prior_h2h_pitches >= 5 THEN 'limited'
                ELSE 'unavailable'
            END AS h2h_support_level,
            {int(year) - 1}::INTEGER AS prior_tag_year,
            pt.sample_reliability AS pitcher_prior_tag_reliability,
            pt.sample_status AS pitcher_prior_tag_status,
            pt.tag_1 AS pitcher_prior_tag_1,
            pt.tag_1_dimension AS pitcher_prior_tag_1_dimension,
            pt.tag_2 AS pitcher_prior_tag_2,
            pt.tag_2_dimension AS pitcher_prior_tag_2_dimension,
            pt.tag_3 AS pitcher_prior_tag_3,
            pt.tag_3_dimension AS pitcher_prior_tag_3_dimension,
            pt.tag_4 AS pitcher_prior_tag_4,
            pt.tag_4_dimension AS pitcher_prior_tag_4_dimension,
            bt.sample_reliability AS batter_prior_tag_reliability,
            bt.sample_status AS batter_prior_tag_status,
            bt.tag_1 AS batter_prior_tag_1,
            bt.tag_1_dimension AS batter_prior_tag_1_dimension,
            bt.tag_2 AS batter_prior_tag_2,
            bt.tag_2_dimension AS batter_prior_tag_2_dimension,
            bt.tag_3 AS batter_prior_tag_3,
            bt.tag_3_dimension AS batter_prior_tag_3_dimension,
            bt.tag_4 AS batter_prior_tag_4,
            bt.tag_4_dimension AS batter_prior_tag_4_dimension,
            'strictly_prior_pitch_or_prior_season' AS feature_time_scope
        FROM chronological c
        LEFT JOIN tags pt
          ON pt.population = 'pitcher'
         AND pt.year = {int(year) - 1}
         AND pt.player_id = c.pitcher_id
         AND pt.role = c.pitcher_role
        LEFT JOIN tags bt
          ON bt.population = 'batter'
         AND bt.year = {int(year) - 1}
         AND bt.player_id = c.batter_id
         AND bt.role = 'Batter'
        ORDER BY c.game_date, c.game_pk, c.at_bat_number, c.pitch_number
    """


def _build_year(year: int, root: Path, roster: Path) -> dict[str, Any]:
    db_path = get_season_duckdb_path(year, root)
    if not db_path.exists():
        return {"year": int(year), "status": "missing_source", "source": str(db_path)}

    output = slice4_warehouse_path(year, root)
    temporary = output.with_suffix(".tmp.parquet")
    output.parent.mkdir(parents=True, exist_ok=True)
    if temporary.exists():
        temporary.unlink()

    query = _warehouse_query(year, roster)
    with duckdb.connect() as connection:
        connection.execute(f"ATTACH '{_sql_path(db_path)}' AS season (READ_ONLY)")
        connection.execute(
            f"COPY ({query}) TO '{_sql_path(temporary)}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
        )
    temporary.replace(output)
    return _audit_year(year, db_path, output)


def _audit_year(year: int, db_path: Path, output: Path) -> dict[str, Any]:
    with duckdb.connect() as connection:
        connection.execute(f"ATTACH '{_sql_path(db_path)}' AS season (READ_ONLY)")
        expected = int(
            connection.execute(
                """
                SELECT count(*) FROM season.pitches
                WHERE game_type = 'R' AND game_pk IS NOT NULL AND at_bat_number IS NOT NULL
                  AND pitch_number IS NOT NULL AND pitcher IS NOT NULL AND batter IS NOT NULL
                  AND fielder_2 IS NOT NULL AND pitch_type IS NOT NULL
                """
            ).fetchone()[0]
        )
        row = connection.execute(
            f"""
            WITH w AS (SELECT * FROM read_parquet('{_sql_path(output)}'))
            SELECT
                count(*) AS rows,
                count(*) - count(DISTINCT decision_id) AS duplicate_decision_ids,
                count(*) FILTER (WHERE decision_id IS NULL OR game_pk IS NULL OR pitcher_id IS NULL OR batter_id IS NULL) AS null_key_rows,
                count(*) FILTER (WHERE prior_pitch_number IS NOT NULL AND prior_pitch_number >= pitch_number) AS pa_boundary_errors,
                count(*) FILTER (WHERE prior_pitcher_pitches < 0 OR prior_batter_pitches < 0 OR prior_catcher_pitches < 0
                                  OR prior_pair_pitches < 0 OR prior_pitcher_count_side_pitches < 0
                                  OR prior_catcher_context_pitches < 0 OR prior_pair_context_pitches < 0
                                  OR prior_h2h_pitches < 0) AS negative_prior_rows,
                count(*) FILTER (WHERE prior_tag_year <> year - 1) AS tag_year_errors,
                count(*) FILTER (
                    WHERE coalesce(list_sum(map_values(prior_pitcher_count_side_mix)), 0)
                          <> prior_pitcher_count_side_pitches
                       OR coalesce(list_sum(map_values(prior_catcher_context_mix)), 0)
                          <> prior_catcher_context_pitches
                       OR coalesce(list_sum(map_values(prior_pair_context_mix)), 0)
                          <> prior_pair_context_pitches
                       OR coalesce(list_sum(map_values(prior_h2h_mix)), 0)
                          <> prior_h2h_pitches
                ) AS prior_map_mismatch_rows,
                count(*) FILTER (WHERE pitcher_prior_tag_1 IS NOT NULL) AS pitcher_prior_tag_rows,
                count(*) FILTER (WHERE batter_prior_tag_1 IS NOT NULL) AS batter_prior_tag_rows,
                count(*) FILTER (WHERE prior_pitcher_pitches = 0) AS pitcher_cold_start_rows,
                count(DISTINCT target_pitch_type) AS target_pitch_types
            FROM w
            """
        ).fetchone()
        names = [item[0] for item in connection.description]
        values = dict(zip(names, row, strict=True))
        backoff_rows = connection.execute(
            f"""
            SELECT context_backoff_level, count(*) AS rows
            FROM read_parquet('{_sql_path(output)}')
            GROUP BY 1 ORDER BY rows DESC
            """
        ).fetchall()
        h2h_rows = connection.execute(
            f"""
            SELECT h2h_support_level, count(*) AS rows
            FROM read_parquet('{_sql_path(output)}')
            GROUP BY 1 ORDER BY rows DESC
            """
        ).fetchall()

    rows = int(values["rows"])
    return {
        "year": int(year),
        "status": "ready",
        "source": str(db_path),
        "output": str(output),
        "sha256": _sha256(output),
        "bytes": int(output.stat().st_size),
        "source_eligible_rows": expected,
        **{key: int(value or 0) for key, value in values.items()},
        "source_row_match": rows == expected,
        "pitcher_prior_tag_coverage_pct": round(int(values["pitcher_prior_tag_rows"]) * 100 / rows, 2) if rows else 0.0,
        "batter_prior_tag_coverage_pct": round(int(values["batter_prior_tag_rows"]) * 100 / rows, 2) if rows else 0.0,
        "context_backoff": {str(level): int(count) for level, count in backoff_rows},
        "h2h_support": {str(level): int(count) for level, count in h2h_rows},
    }


def build_player_archetype_slice4(
    years: tuple[int, ...] = DEFAULT_YEARS,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    roster = slice3_roster_path(root)
    if not roster.exists():
        raise FileNotFoundError(roster)

    audits = [_build_year(int(year), root, roster) for year in years]
    ready = [row for row in audits if row["status"] == "ready"]
    integrity_passed = bool(ready) and all(
        row["source_row_match"]
        and row["duplicate_decision_ids"] == 0
        and row["null_key_rows"] == 0
        and row["pa_boundary_errors"] == 0
        and row["negative_prior_rows"] == 0
        and row["tag_year_errors"] == 0
        and row["prior_map_mismatch_rows"] == 0
        for row in ready
    )
    payload = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if len(ready) == len(years) and integrity_passed else "partial",
        "scope": {"years": [int(year) for year in years], "grain": "one_row_per_observed_pitch_decision"},
        "slices": {
            "4A": "Ordered pitch timeline, game state, plate-appearance-safe previous pitch and observed action/outcome labels.",
            "4B": "Prior-season pitcher/batter tags plus strictly earlier current-season pitcher, batter and arsenal state.",
            "4C": "Strictly prior catcher context, pitcher-catcher context and pitcher-batter head-to-head maps with support levels.",
            "4D": "Unique-key, row reconciliation, PA boundary, prior-map, tag-year and sparsity audits.",
        },
        "feature_policy": {
            "pre_pitch_features": "Columns without observed_ or target_ prefixes, excluding identifiers used only for joins.",
            "targets": ["target_pitch_type", "target_pitch_name", "target_pitch_family"],
            "post_decision_labels": [
                "observed_description", "observed_pa_event", "observed_release_speed",
                "observed_plate_x", "observed_plate_z", "observed_delta_run_exp",
            ],
            "current_season_full_year_tags_allowed": False,
            "catcher_causal_claim_allowed": False,
            "low_support_behavior": "Use context_backoff_level and h2h_support_level; never treat a missing map as zero preference.",
        },
        "audits": audits,
        "totals": {
            "rows": sum(row["rows"] for row in ready),
            "bytes": sum(row["bytes"] for row in ready),
            "pitcher_cold_start_rows": sum(row["pitcher_cold_start_rows"] for row in ready),
        },
        "integrity_passed": integrity_passed,
    }
    contract = slice4_contract_path(root)
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def get_player_archetype_slice4(data_dir: Path | None = None) -> dict[str, Any]:
    return json.loads(slice4_contract_path(data_dir).read_text(encoding="utf-8"))


def render_slice4_report(payload: dict[str, Any]) -> str:
    ready = [row for row in payload["audits"] if row["status"] == "ready"]
    total_rows = int(payload["totals"]["rows"])
    backoff = {
        level: sum(int(row["context_backoff"].get(level, 0)) for row in ready)
        for level in (
            "pitcher_catcher_context",
            "pitcher_count_side",
            "catcher_context",
            "pitcher_role",
            "role_archetype",
        )
    }
    h2h = {
        level: sum(int(row["h2h_support"].get(level, 0)) for row in ready)
        for level in ("supported", "limited", "unavailable")
    }
    lines = [
        "# Player Archetypes Slice 4 — Pitch-decision state warehouse",
        "",
        f"Contract: `{payload['contract_version']}`  ",
        f"Status: **{payload['status']}**  ",
        f"Integrity: **{'passed' if payload['integrity_passed'] else 'failed'}**  ",
        f"Rows: **{payload['totals']['rows']:,}**",
        "",
        "## A–D deliverables",
        "",
    ]
    for key, value in payload["slices"].items():
        lines.append(f"- **{key}:** {value}")
    lines.extend(
        [
            "",
            "## Yearly audit",
            "",
            "| Year | Rows | Size MB | Duplicate keys | PA boundary | Map mismatch | Pitcher prior tags | Batter prior tags |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in payload["audits"]:
        if row["status"] != "ready":
            lines.append(f"| {row['year']} | unavailable | - | - | - | - | - | - |")
            continue
        lines.append(
            f"| {row['year']} | {row['rows']:,} | {row['bytes'] / 1024 / 1024:.1f} | "
            f"{row['duplicate_decision_ids']} | {row['pa_boundary_errors']} | {row['prior_map_mismatch_rows']} | "
            f"{row['pitcher_prior_tag_coverage_pct']:.2f}% | {row['batter_prior_tag_coverage_pct']:.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Support and backoff profile",
            "",
            "The conservative single-level order is pitcher-catcher context → pitcher count/side → catcher context → pitcher role → role archetype. All prior maps remain available to later hierarchical models.",
            "",
            "| Level | Rows | Share |",
            "|---|---:|---:|",
        ]
    )
    for level, count in backoff.items():
        share = count * 100 / total_rows if total_rows else 0.0
        lines.append(f"| {level} | {count:,} | {share:.2f}% |")
    lines.extend(["", "| H2H support | Rows | Share |", "|---|---:|---:|"])
    for level, count in h2h.items():
        share = count * 100 / total_rows if total_rows else 0.0
        lines.append(f"| {level} | {count:,} | {share:.2f}% |")
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- `target_*` is the action to predict. `observed_*` is post-decision information and must never enter a pitch-choice model.",
            "- Prior maps are sufficient statistics from strictly earlier pitches; null means no prior support, not a zero preference.",
            "- Pitcher and batter tags come only from the prior season. Same-season full-year tags are forbidden.",
            "- Catcher and pairing fields are associative. They do not identify who called the pitch or establish causal catcher skill.",
            "",
        ]
    )
    return "\n".join(lines)
