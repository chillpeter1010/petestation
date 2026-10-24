from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path
from app.services.player_archetype_slice4_service import slice4_warehouse_path
from app.services.player_archetype_slice5_service import slice5_prediction_path


CONTRACT_VERSION = "player_archetype_slice5a_observed_location_v1"
YEAR = 2026
MEATBALL_X_MAX = 0.83 / 3.0


def slice5a_contract_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice5a_location.json"


def slice5a_pitch_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "player_archetype_slice5a_locations_2026.parquet"


def slice5a_report_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "PLAYER_ARCHETYPES_PITCH_STRATEGY.md"


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: Any, digits: int = 6) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return round(numeric, digits) if math.isfinite(numeric) else None


def _pitch_query(predictions: Path, warehouse: Path) -> str:
    swing_events = "'swinging_strike','swinging_strike_blocked','foul','foul_tip','foul_bunt','hit_into_play','hit_into_play_no_out','hit_into_play_score','missed_bunt'"
    return f"""
        WITH raw AS (
            SELECT
                concat(CAST({YEAR} AS VARCHAR), ':', CAST(game_pk AS VARCHAR), ':',
                       CAST(at_bat_number AS VARCHAR), ':', CAST(pitch_number AS VARCHAR), ':',
                       CAST(pitcher AS VARCHAR)) AS decision_id,
                CAST(zone AS INTEGER) AS statcast_zone,
                CAST(plate_x AS DOUBLE) AS raw_plate_x,
                CAST(plate_z AS DOUBLE) AS raw_plate_z,
                CAST(sz_top AS DOUBLE) AS sz_top,
                CAST(sz_bot AS DOUBLE) AS sz_bot,
                nullif(CAST(stand AS VARCHAR), '') AS raw_batter_side,
                nullif(CAST(description AS VARCHAR), '') AS raw_description,
                nullif(CAST(events AS VARCHAR), '') AS raw_pa_event
            FROM season.pitches
            WHERE game_type = 'R'
              AND game_pk IS NOT NULL AND at_bat_number IS NOT NULL AND pitch_number IS NOT NULL
              AND pitcher IS NOT NULL AND batter IS NOT NULL AND fielder_2 IS NOT NULL
              AND pitch_type IS NOT NULL
        ),
        joined AS (
            SELECT
                p.*,
                w.pitcher_name,
                w.pitcher_team,
                w.pitcher_role,
                w.batter_side,
                w.count_state,
                w.outs,
                w.base_state,
                w.inning,
                w.target_pitch_name,
                w.observed_description,
                w.observed_pa_event,
                w.observed_delta_run_exp,
                r.statcast_zone,
                coalesce(r.raw_plate_x, w.observed_plate_x) AS plate_x,
                coalesce(r.raw_plate_z, w.observed_plate_z) AS plate_z,
                r.sz_top,
                r.sz_bot,
                coalesce(r.raw_batter_side, w.batter_side) AS resolved_batter_side,
                coalesce(r.raw_description, w.observed_description) AS resolved_description,
                coalesce(r.raw_pa_event, w.observed_pa_event) AS resolved_pa_event
            FROM read_parquet('{_sql_path(predictions)}') p
            JOIN read_parquet('{_sql_path(warehouse)}') w USING (decision_id)
            LEFT JOIN raw r USING (decision_id)
        ),
        geometry AS (
            SELECT *,
                plate_x * CASE WHEN resolved_batter_side = 'L' THEN -1.0 ELSE 1.0 END AS plate_x_batter,
                (plate_z - sz_bot) / nullif(sz_top - sz_bot, 0) AS plate_z_norm,
                CASE target_pitch_family
                    WHEN 'Fastball' THEN prob_family_fastball
                    WHEN 'Breaking' THEN prob_family_breaking
                    WHEN 'Offspeed' THEN prob_family_offspeed
                    ELSE prob_family_other
                END AS chosen_family_probability
            FROM joined
        ),
        bands AS (
            SELECT *,
                CASE
                    WHEN statcast_zone IN (2, 5, 8) THEN 'Middle'
                    WHEN statcast_zone IN (1, 4, 7) THEN CASE WHEN resolved_batter_side = 'L' THEN 'Away' ELSE 'Inside' END
                    WHEN statcast_zone IN (3, 6, 9) THEN CASE WHEN resolved_batter_side = 'L' THEN 'Inside' ELSE 'Away' END
                    WHEN plate_x_batter IS NULL THEN 'Unavailable'
                    WHEN plate_x_batter < {-MEATBALL_X_MAX:.12f} THEN 'Inside'
                    WHEN plate_x_batter > {MEATBALL_X_MAX:.12f} THEN 'Away'
                    ELSE 'Middle'
                END AS horizontal_band,
                CASE
                    WHEN statcast_zone IN (1, 2, 3) THEN 'High'
                    WHEN statcast_zone IN (4, 5, 6) THEN 'Middle'
                    WHEN statcast_zone IN (7, 8, 9) THEN 'Low'
                    WHEN plate_z_norm IS NULL THEN 'Unavailable'
                    WHEN plate_z_norm < 1.0 / 3.0 THEN 'Low'
                    WHEN plate_z_norm > 2.0 / 3.0 THEN 'High'
                    ELSE 'Middle'
                END AS vertical_band
            FROM geometry
        )
        SELECT
            decision_id, year, game_date, game_pk, at_bat_number, pitch_number,
            pitcher_id, pitcher_name, pitcher_team, pitcher_role, batter_id, catcher_id,
            resolved_batter_side AS batter_side, count_state, outs, base_state, inning,
            target_pitch_family, target_pitch_code, target_pitch_name,
            predicted_family, predicted_pitch_type, family_confidence, family_entropy,
            chosen_family_probability,
            -ln(greatest(chosen_family_probability, 1e-12)) AS chosen_family_surprisal,
            statcast_zone, plate_x, plate_z, sz_top, sz_bot, plate_x_batter, plate_z_norm,
            horizontal_band, vertical_band,
            concat(horizontal_band, '-', vertical_band) AS location_bucket,
            CASE
                WHEN statcast_zone IS NOT NULL THEN statcast_zone = 5
                WHEN abs(plate_x) <= {MEATBALL_X_MAX:.12f}
                 AND plate_z_norm BETWEEN 1.0 / 3.0 AND 2.0 / 3.0 THEN true
                ELSE false
            END AS is_meatball_proxy,
            CASE
                WHEN statcast_zone IS NOT NULL THEN 'statcast_zone_5'
                WHEN plate_x IS NOT NULL AND plate_z_norm IS NOT NULL THEN 'coordinate_middle_third_fallback'
                ELSE 'unavailable_false'
            END AS meatball_source,
            resolved_description AS observed_description,
            resolved_pa_event AS observed_pa_event,
            observed_delta_run_exp,
            lower(coalesce(resolved_description, '')) IN ({swing_events}) AS is_swing,
            lower(coalesce(resolved_description, '')) IN ('hit_into_play','hit_into_play_no_out','hit_into_play_score') AS is_in_play,
            lower(coalesce(resolved_pa_event, '')) = 'home_run' AS is_home_run,
            'observed_post_pitch_explanation_only' AS feature_time_scope
        FROM bands
        ORDER BY game_date, game_pk, at_bat_number, pitch_number
    """


def _rows(connection: duckdb.DuckDBPyConnection, query: str) -> list[dict[str, Any]]:
    frame = connection.execute(query).fetchdf()
    return [
        {key: (_number(value) if isinstance(value, float) else value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def build_player_archetype_slice5a(data_dir: Path | None = None) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    predictions = slice5_prediction_path(root)
    warehouse = slice4_warehouse_path(YEAR, root)
    season_db = get_season_duckdb_path(YEAR, root)
    for source in (predictions, warehouse, season_db):
        if not source.exists():
            raise FileNotFoundError(source)

    output = slice5a_pitch_path(root)
    temporary = output.with_suffix(".tmp.parquet")
    output.parent.mkdir(parents=True, exist_ok=True)
    if temporary.exists():
        temporary.unlink()

    with duckdb.connect() as connection:
        connection.execute(f"ATTACH '{_sql_path(season_db)}' AS season (READ_ONLY)")
        connection.execute(
            f"COPY ({_pitch_query(predictions, warehouse)}) TO '{_sql_path(temporary)}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
        )
    temporary.replace(output)

    path = _sql_path(output)
    with duckdb.connect() as connection:
        audit = connection.execute(
            f"""
            SELECT count(*) AS row_count,
                   count(*) - count(DISTINCT decision_id) duplicate_decision_ids,
                   count(*) FILTER (WHERE statcast_zone IS NOT NULL) zone_rows,
                   count(*) FILTER (WHERE plate_x IS NOT NULL AND plate_z IS NOT NULL) coordinate_rows,
                   count(*) FILTER (WHERE plate_z_norm IS NOT NULL) normalized_vertical_rows,
                   count(*) FILTER (WHERE is_meatball_proxy) meatballs,
                   100.0 * count(*) FILTER (WHERE is_meatball_proxy) / count(*) meatball_pct,
                   count(*) FILTER (WHERE feature_time_scope <> 'observed_post_pitch_explanation_only') bad_time_scope
            FROM read_parquet('{path}')
            """
        ).fetchone()
        family = _rows(
            connection,
            f"""
            SELECT target_pitch_family AS pitch_family, count(*) pitches,
                   count(*) FILTER (WHERE is_meatball_proxy) meatballs,
                   100.0 * avg(is_meatball_proxy::INTEGER) meatball_pct,
                   100.0 * avg(is_swing::INTEGER) FILTER (WHERE is_meatball_proxy) meatball_swing_pct,
                   avg(observed_delta_run_exp) FILTER (WHERE is_meatball_proxy) meatball_avg_delta_run_exp,
                   avg(observed_delta_run_exp) FILTER (WHERE NOT is_meatball_proxy) non_meatball_avg_delta_run_exp
            FROM read_parquet('{path}') GROUP BY 1 ORDER BY pitches DESC
            """,
        )
        cells = _rows(
            connection,
            f"""
            SELECT horizontal_band, vertical_band, location_bucket, count(*) pitches,
                   100.0 * count(*) / sum(count(*)) OVER () pitch_pct,
                   avg(observed_delta_run_exp) avg_delta_run_exp
            FROM read_parquet('{path}') GROUP BY ALL ORDER BY pitches DESC
            """,
        )
        example = _rows(
            connection,
            f"""
            SELECT pitch_number, count_state, target_pitch_code, observed_description,
                   statcast_zone, round(plate_x, 3) plate_x, round(plate_z_norm, 3) plate_z_norm,
                   horizontal_band, vertical_band, is_meatball_proxy, observed_pa_event
            FROM read_parquet('{path}')
            WHERE game_pk = 823926 AND pitcher_id = 808967 AND batter_id = 543510 AND at_bat_number = 44
            ORDER BY pitch_number
            """,
        )

    rows = int(audit[0])
    payload = {
        "contract_version": CONTRACT_VERSION,
        "status": "ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "year": YEAR,
            "grain": "one_row_per_slice5_pitch_decision",
            "purpose": "Observed post-pitch location explanation for the frozen Slice 5 strategy probabilities.",
        },
        "location_contract": {
            "horizontal": "Statcast zones 1-9 use their official columns, mirrored by batter side; out-of-zone rows use batter-relative plate_x thirds.",
            "vertical": "Statcast zones 1-9 use their official rows; out-of-zone rows use batter-specific normalized strike-zone thirds.",
            "batter_relative_sign": "Positive is Away and negative is Inside after mirroring left-handed batters.",
            "measurement_plane": "2026 Statcast plate_x/plate_z are measured at middle-of-plate for ABS alignment.",
        },
        "meatball_contract": {
            "display_name": "Meatball%",
            "primary_rule": "Statcast zone == 5 (middle-middle).",
            "fallback_rule": "Only when zone is missing: abs(plate_x) <= 0.83/3 and normalized plate_z is between 1/3 and 2/3.",
            "denominator": "All Slice 5 eligible pitch decisions.",
            "interpretation": "Observed middle-middle exposure proxy; not proof that the pitcher missed the intended target.",
            "not_equivalent_to": ["the full strike zone", "the broader Heart zone", "a bad result", "catcher target miss"],
        },
        "audit": {
            "rows": rows,
            "duplicate_decision_ids": int(audit[1]),
            "zone_rows": int(audit[2]),
            "zone_coverage": _number(audit[2] / rows if rows else 0),
            "coordinate_rows": int(audit[3]),
            "coordinate_coverage": _number(audit[3] / rows if rows else 0),
            "normalized_vertical_rows": int(audit[4]),
            "normalized_vertical_coverage": _number(audit[4] / rows if rows else 0),
            "meatballs": int(audit[5]),
            "meatball_pct": _number(audit[6]),
            "bad_time_scope_rows": int(audit[7]),
        },
        "by_pitch_family": family,
        "location_cells": cells,
        "case_823926_yamamoto_mccann": example,
        "release_gate": {
            "observed_location_layer_ready": bool(rows and audit[1] == 0 and audit[7] == 0),
            "true_missed_target_supported": False,
            "slice5_model_retrained": False,
            "slice6_use": "May be used as an observed outcome/explanation after overlap gates; never as a pre-pitch feature for the frozen test.",
        },
        "artifacts": {
            "pitch_locations_2026": str(output),
            "pitch_locations_2026_sha256": _sha256(output),
        },
    }
    contract = slice5a_contract_path(root)
    contract.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return payload


def get_player_archetype_slice5a(data_dir: Path | None = None) -> dict[str, Any]:
    return json.loads(slice5a_contract_path(data_dir).read_text(encoding="utf-8"))


def render_slice5a_report(payload: dict[str, Any]) -> str:
    audit = payload["audit"]
    lines = [
        "# Player Archetypes Slice 5A — Observed location and Meatball proxy",
        "",
        f"Contract: `{payload['contract_version']}`  ",
        f"Status: **{payload['status']}**  ",
        "",
        "## Definition",
        "",
        "- `Meatball%` uses Statcast zone 5: the middle third horizontally and vertically, not the full strike zone or the broader Heart zone.",
        "- If Statcast zone is missing, the fallback uses the batter-specific strike-zone middle third from `plate_x`, `plate_z`, `sz_top`, and `sz_bot`.",
        "- It is an observed middle-middle exposure proxy. Without intended target or catcher glove coordinates, it is not a verified command miss.",
        "- Inside/Away is mirrored to the batter's side; vertical location is normalized to each batter's recorded zone.",
        "",
        "## 2026 coverage",
        "",
        f"- Rows: **{audit['rows']:,}**; duplicate decision IDs: **{audit['duplicate_decision_ids']}**.",
        f"- Zone coverage: **{audit['zone_coverage']:.3%}**; coordinate coverage: **{audit['coordinate_coverage']:.3%}**; normalized vertical coverage: **{audit['normalized_vertical_coverage']:.3%}**.",
        f"- Meatballs: **{audit['meatballs']:,} / {audit['rows']:,} = {audit['meatball_pct']:.3f}%**.",
        "",
        "## By pitch family",
        "",
        "| Family | Pitches | Meatballs | Meatball% | Meatball swing% | Meatball RE24 | Other RE24 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["by_pitch_family"]:
        lines.append(
            f"| {row['pitch_family']} | {int(row['pitches']):,} | {int(row['meatballs']):,} | "
            f"{row['meatball_pct']:.3f}% | {row['meatball_swing_pct']:.3f}% | "
            f"{row['meatball_avg_delta_run_exp']:.5f} | {row['non_meatball_avg_delta_run_exp']:.5f} |"
        )
    lines.extend(
        [
            "",
            "## Yamamoto vs. McCann, game 823926",
            "",
            "| Pitch | Count | Type | Result | Zone | X | Z norm | Horizontal | Vertical | Meatball | PA event |",
            "|---:|---|---|---|---:|---:|---:|---|---|---|---|",
        ]
    )
    for row in payload["case_823926_yamamoto_mccann"]:
        lines.append(
            f"| {row['pitch_number']} | {row['count_state']} | {row['target_pitch_code']} | {row['observed_description']} | "
            f"{row['statcast_zone']} | {row['plate_x']:.3f} | {row['plate_z_norm']:.3f} | {row['horizontal_band']} | "
            f"{row['vertical_band']} | {row['is_meatball_proxy']} | {row['observed_pa_event'] or ''} |"
        )
    lines.extend(
        [
            "",
            "The home-run pitch is not automatically called a miss: if it did not finish zone 5, Meatball% leaves it unflagged. Outcome and location remain separate.",
            "",
            "## Boundary for Slice 6",
            "",
            "This layer is post-pitch explanation only. The frozen Slice 5 choice probabilities were not retrained, and 2026 remains an already-open test set. Slice 6 may condition descriptive value summaries on these observed cells only after overlap and support gates; it cannot claim an unobserved alternative location was factual.",
            "",
        ]
    )
    return "\n".join(lines)
