from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import duckdb
import pandas as pd
import requests

from app.core.config import settings
from app.repositories.pitch_repository import get_season_duckdb_path, resolve_pitch_table


CONTRACT_VERSION = "catcher_descriptive_slice0_audit_v1"
DEFAULT_YEARS = tuple(range(2021, 2027))
LEGACY_WORKBOOK = Path(r"C:\轉移\mlbpython\ERA\catcher2025_processed.xlsx")
LEGACY_CERA_CODE = Path(r"C:\Users\郭睿承\Desktop\實習個案\abs2025\claude\cera_utils.py")
LEGACY_XERA_CODE = Path(r"C:\Users\郭睿承\Desktop\實習個案\abs2025\claude\build_estimated_xera.py")


def audit_output_path(data_dir: Path | None = None) -> Path:
    return Path(data_dir or settings.data_dir) / "derived" / "catcher_descriptive_slice0_audit.json"


def _fingerprint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "status": "missing"}
    payload = path.read_bytes()
    return {
        "path": str(path),
        "status": "present",
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "modified_at_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
    }


def baseball_ip_to_outs(value: object) -> int:
    """Convert baseball innings notation to outs and reject decimal arithmetic."""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        raise ValueError("Innings value is missing.")
    if "." not in text:
        return int(text) * 3
    innings, partial = text.split(".", 1)
    remainder = int((partial or "0")[0])
    if remainder not in {0, 1, 2}:
        raise ValueError(f"Invalid baseball innings remainder: {value}")
    return int(innings or 0) * 3 + remainder


def _legacy_data_dictionary(missing: dict[str, int]) -> list[dict[str, Any]]:
    common = {"year": 2025, "grain": "catcher-season-team/TOT static row"}
    rows = [
        ("Name", "Legacy catcher display name", "unknown upstream", "none", "partial"),
        ("Tm", "Team abbreviation or TOT for multi-team season", "unknown upstream", "none", "partial"),
        ("Inn", "Displayed catcher innings", "unknown upstream", "no raw outs", "failed"),
        ("SavRun", "Legacy runs saved field", "inferred from tERA minus ERA", "no formula lineage", "partial"),
        ("ERA", "Legacy catcher ERA (cERA candidate)", "unknown upstream", "no ER or outs", "failed"),
        ("RA9", "Legacy catcher runs allowed per nine", "unknown upstream", "no R or outs", "failed"),
        ("tERA", "Legacy pitcher-mix ERA baseline", "unknown upstream", "baseline population/weights absent", "failed"),
        ("tRA9", "Legacy pitcher-mix RA9 baseline", "unknown upstream", "baseline population/weights absent", "failed"),
        ("Framing", "Legacy framing value", "unknown upstream", "source/version absent", "failed"),
        ("FRV", "Legacy framing runs value", "unknown upstream", "source/version absent", "failed"),
        ("SR/Yr", "Legacy SavRun annualized to 1,200 displayed innings", "inferred arithmetic", "small-sample inflation", "partial"),
        ("SRA", "Legacy adjusted saved-runs field", "unknown constant offset from SavRun", "formula/meaning absent", "failed"),
        ("SRA/Yr", "Legacy SRA annualized to 1,200 displayed innings", "inferred arithmetic", "SRA meaning absent", "partial"),
    ]
    return [
        {
            "field": field,
            "working_definition": definition,
            "source": source,
            **common,
            "missing_rows": int(missing.get(field, 0)),
            "reproducibility": reproducibility,
            "limitation": limitation,
        }
        for field, definition, source, limitation, reproducibility in rows
    ]


def _read_xlsx_first_sheet(path: Path) -> tuple[list[str], pd.DataFrame, int]:
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        sheet_names = [
            item.attrib["name"] for item in workbook_root.findall(".//x:sheet", namespace)
        ]
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall("x:si", namespace):
                shared_strings.append("".join(node.text or "" for node in item.findall(".//x:t", namespace)))
        sheet_root = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    cells: dict[tuple[int, int], object] = {}
    formula_count = 0
    max_row = 0
    max_column = 0
    for cell in sheet_root.findall(".//x:c", namespace):
        reference = cell.attrib.get("r", "")
        match = re.fullmatch(r"([A-Z]+)(\d+)", reference)
        if not match:
            continue
        column_letters, row_text = match.groups()
        column_number = 0
        for character in column_letters:
            column_number = column_number * 26 + ord(character) - ord("A") + 1
        row_number = int(row_text)
        max_row = max(max_row, row_number)
        max_column = max(max_column, column_number)
        if cell.find("x:f", namespace) is not None:
            formula_count += 1
        value_node = cell.find("x:v", namespace)
        inline_node = cell.find("x:is", namespace)
        value: object = None
        if cell.attrib.get("t") == "s" and value_node is not None:
            value = shared_strings[int(value_node.text or 0)]
        elif cell.attrib.get("t") == "inlineStr" and inline_node is not None:
            value = "".join(node.text or "" for node in inline_node.findall(".//x:t", namespace))
        elif value_node is not None and value_node.text is not None:
            try:
                value = float(value_node.text)
            except ValueError:
                value = value_node.text
        cells[(row_number, column_number)] = value

    headers = [cells.get((1, column)) for column in range(1, max_column + 1)]
    rows = [
        [cells.get((row, column)) for column in range(1, max_column + 1)]
        for row in range(2, max_row + 1)
    ]
    return sheet_names, pd.DataFrame(rows, columns=headers), formula_count


def audit_legacy_workbook(path: Path = LEGACY_WORKBOOK) -> dict[str, Any]:
    result = _fingerprint(path)
    if result["status"] != "present":
        return result
    sheet_names, frame, formula_count = _read_xlsx_first_sheet(path)
    missing = {column: int(frame[column].isna().sum()) for column in frame.columns}
    numeric = frame.copy()
    for column in frame.columns:
        if column not in {"Name", "Tm"}:
            numeric[column] = pd.to_numeric(frame[column], errors="coerce")
    non_tot = numeric[frame["Tm"].ne("TOT")]
    inferred_savrun = (non_tot["tERA"] - non_tot["ERA"]) * non_tot["Inn"] / 9.0
    inferred_sryr = numeric["SavRun"] * 1200.0 / numeric["Inn"]
    inferred_srayr = numeric["SRA"] * 1200.0 / numeric["Inn"]
    invalid_innings = frame[
        frame["Inn"].map(lambda value: int(round(float(value) * 10)) % 10 not in {0, 1, 2})
    ][["Name", "Tm", "Inn"]]
    sra_offset = numeric["SRA"] - numeric["SavRun"]
    result.update(
        {
            "sheet_names": sheet_names,
            "rows": int(len(frame)),
            "columns": frame.columns.tolist(),
            "formula_cells": int(formula_count),
            "missing_rows": missing,
            "team_rows": int(frame["Tm"].ne("TOT").sum()),
            "multi_team_tot_rows": int(frame["Tm"].eq("TOT").sum()),
            "invalid_display_innings_rows": invalid_innings.to_dict(orient="records"),
            "inferred_identities": {
                "savrun_from_displayed_tera_minus_era_non_tot": {
                    "formula": "(tERA - ERA) * Inn / 9",
                    "mean_absolute_difference": round(float((numeric.loc[non_tot.index, "SavRun"] - inferred_savrun).abs().mean()), 6),
                    "max_absolute_difference": round(float((numeric.loc[non_tot.index, "SavRun"] - inferred_savrun).abs().max()), 6),
                    "status": "reconstructable_to_display_rounding_not_source_verified",
                },
                "sr_per_year": {
                    "formula": "SavRun * 1200 / Inn",
                    "max_absolute_difference": round(float((numeric["SR/Yr"] - inferred_sryr).abs().max()), 6),
                    "status": "reconstructable_but_uses_displayed_innings",
                },
                "sra_offset": {
                    "constant": float(sra_offset.iloc[0]),
                    "max_deviation_from_constant": float((sra_offset - sra_offset.iloc[0]).abs().max()),
                    "status": "arithmetic_reconstructable_semantics_unknown",
                },
                "sra_per_year": {
                    "formula": "SRA * 1200 / Inn",
                    "max_absolute_difference": round(float((numeric["SRA/Yr"] - inferred_srayr).abs().max()), 6),
                    "status": "reconstructable_but_source_metric_unknown",
                },
            },
            "data_dictionary": _legacy_data_dictionary(missing),
        }
    )
    return result


def _audit_year(year: int, root: Path) -> dict[str, Any]:
    path = get_season_duckdb_path(year, root)
    if not path.exists():
        return {"year": year, "status": "missing", "source": str(path)}
    with duckdb.connect(str(path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        table = resolve_pitch_table(tables)
        if not table:
            return {"year": year, "status": "missing_pitch_table", "source": str(path)}
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info('{table}')").fetchall()}
        cursor = connection.execute(
            f"""
            WITH regular AS (
                SELECT * FROM {table}
                WHERE game_type = 'R' AND pitcher IS NOT NULL
            ), terminal AS (
                SELECT * FROM regular WHERE events IS NOT NULL
            ), duplicate_pitch_keys AS (
                SELECT game_pk, at_bat_number, pitch_number
                FROM regular GROUP BY 1, 2, 3 HAVING count(*) > 1
            ), duplicate_pa_keys AS (
                SELECT game_pk, at_bat_number
                FROM terminal GROUP BY 1, 2 HAVING count(*) > 1
            )
            SELECT
                count(*) AS terminal_rows,
                (SELECT count(*) FROM regular) AS regular_pitches,
                count(DISTINCT game_pk) AS games,
                count(DISTINCT pitcher) AS pitchers,
                count(DISTINCT fielder_2) AS catchers,
                count(DISTINCT concat(CAST(pitcher AS VARCHAR), ':', CAST(fielder_2 AS VARCHAR))) AS pitcher_catcher_pairs,
                count(fielder_2) AS catcher_terminal_rows,
                count(outs_when_up) AS outs_state_rows,
                count(*) FILTER (WHERE bat_score IS NOT NULL AND post_bat_score IS NOT NULL) AS score_rows,
                sum(CASE WHEN events <> 'truncated_pa' THEN 1 ELSE 0 END) AS bf_event_rows,
                sum(CASE WHEN events = 'home_run' THEN 1 ELSE 0 END) AS hr,
                sum(CASE WHEN events IN ('walk', 'intent_walk') THEN 1 ELSE 0 END) AS bb_total,
                sum(CASE WHEN events = 'walk' THEN 1 ELSE 0 END) AS bb_unintentional,
                sum(CASE WHEN events = 'intent_walk' THEN 1 ELSE 0 END) AS intentional_walks,
                sum(CASE WHEN events = 'hit_by_pitch' THEN 1 ELSE 0 END) AS hbp,
                sum(CASE WHEN events IN ('strikeout', 'strikeout_double_play') THEN 1 ELSE 0 END) AS strikeouts,
                sum(post_bat_score - bat_score) AS runs_scored_while_current_pair,
                (SELECT count(*) FROM duplicate_pitch_keys) AS duplicate_pitch_keys,
                (SELECT count(*) FROM duplicate_pa_keys) AS duplicate_terminal_pa_keys,
                min(game_date) AS first_game_date,
                max(game_date) AS last_game_date
            FROM terminal
            """
        )
        values = dict(zip([column[0] for column in cursor.description], cursor.fetchone(), strict=True))
    return {
        "year": year,
        "status": "ready",
        "source": str(path),
        "source_table": table,
        "database_bytes": path.stat().st_size,
        "has_outs_on_play": "outs_on_play" in columns,
        "has_earned_run_flag": bool({"earned", "is_earned", "earned_run"} & columns),
        "has_official_pitcher_game_lines": "pitcher_game_lines" in tables,
        **{
            key: (str(value)[:10] if key.endswith("_date") else int(value or 0))
            for key, value in values.items()
        },
    }


def _audit_xera(root: Path) -> dict[str, Any]:
    model_path = root / "estimated_xera_model_2025.json"
    scored_path = root / "2026_pitcher_comparison_with_est_xera.csv"
    result = {
        "legacy_builder": _fingerprint(LEGACY_XERA_CODE),
        "model": _fingerprint(model_path),
        "scored_output": _fingerprint(scored_path),
    }
    if model_path.exists():
        model = json.loads(model_path.read_text(encoding="utf-8"))
        result["model_metrics"] = {
            key: model.get(key) for key in ["train_rows", "mae", "rmse", "r2"]
        }
        result["feature_count"] = len(model.get("features") or [])
    if scored_path.exists():
        frame = pd.read_csv(scored_path, low_memory=False)
        result["scored_rows"] = int(len(frame))
        result["est_xera_available_rows"] = int(pd.to_numeric(frame.get("est_xERA"), errors="coerce").notna().sum())
        result["cubic_xwoba_available_rows"] = int(pd.to_numeric(frame.get("xERA_xwoba_cubic"), errors="coerce").notna().sum())
    result["limitations"] = [
        "2025 pitcher-season OLS has in-sample metrics only and no chronological validation split.",
        "Overlapping xwOBA, xBA, wOBA and batted-ball features create collinearity/leakage risk.",
        "The output is a pitcher-season proxy and cannot be aggregated directly as cxERA/txERA.",
        "starter_reference_service.py relabels est_xERA as xERA for the starter dashboard.",
    ]
    return result


def _official_feed_probe(year: int, root: Path) -> dict[str, Any]:
    path = get_season_duckdb_path(year, root)
    with duckdb.connect(str(path), read_only=True) as connection:
        table = resolve_pitch_table({row[0] for row in connection.execute("SHOW TABLES").fetchall()})
        game_pk, runs, pa_rows = connection.execute(
            f"""
            SELECT game_pk, sum(post_bat_score - bat_score) AS runs,
                   count(*) FILTER (WHERE events IS NOT NULL) AS pa_rows
            FROM {table}
            WHERE game_type = 'R'
            GROUP BY 1
            ORDER BY runs DESC, game_pk
            LIMIT 1
            """
        ).fetchone()
        terminal = connection.execute(
            f"""
            SELECT at_bat_number, pitcher
            FROM {table}
            WHERE game_type = 'R' AND game_pk = ? AND events IS NOT NULL
            ORDER BY at_bat_number
            """,
            [int(game_pk)],
        ).fetchall()
    url = f"https://statsapi.mlb.com/api/v1.1/game/{int(game_pk)}/feed/live"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    plays = response.json().get("liveData", {}).get("plays", {}).get("allPlays", [])
    runner_details = [
        runner.get("details") or {}
        for play in plays
        for runner in (play.get("runners") or [])
    ]
    movements = [
        runner.get("movement") or {}
        for play in plays
        for runner in (play.get("runners") or [])
    ]
    scoring = [row for row in runner_details if row.get("isScoringEvent")]
    outs = [row for row in movements if row.get("isOut")]
    join_matches = sum(
        int(db_row[0]) == int(play.get("atBatIndex", -2)) + 1
        and int(db_row[1]) == int(((play.get("matchup") or {}).get("pitcher") or {}).get("id", -1))
        for db_row, play in zip(terminal, plays)
    )
    return {
        "year": year,
        "game_pk": int(game_pk),
        "source_url": url,
        "http_status": int(response.status_code),
        "statcast_runs": int(runs),
        "statcast_terminal_pa_rows": int(pa_rows),
        "official_feed_plays": len(plays),
        "at_bat_and_pitcher_join_matches": int(join_matches),
        "scoring_runners": len(scoring),
        "scoring_runner_earned_flag_rows": sum("earned" in row for row in scoring),
        "scoring_runner_responsible_pitcher_rows": sum(
            ((row.get("responsiblePitcher") or {}).get("id") is not None) for row in scoring
        ),
        "runner_out_movements": len(outs),
        "runner_out_number_rows": sum(row.get("outNumber") is not None for row in outs),
        "scope_note": "one deliberately high-scoring game per year; source feasibility probe, not full-year coverage proof",
    }


def _reconcile_2026_local_controls(root: Path) -> dict[str, Any]:
    path = get_season_duckdb_path(2026, root)
    if not path.exists():
        return {"status": "missing_2026_database"}
    with duckdb.connect(str(path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        table = resolve_pitch_table(tables)
        if not table or "pitcher_game_lines" not in tables:
            return {"status": "missing_required_tables"}
        derived = connection.execute(
            f"""
            WITH terminal AS (
                SELECT game_pk, pitcher, inning, inning_topbot, outs_when_up, events,
                       bat_score, post_bat_score, post_fld_score,
                       lead(inning) OVER (PARTITION BY game_pk ORDER BY at_bat_number) AS next_inning,
                       lead(inning_topbot) OVER (PARTITION BY game_pk ORDER BY at_bat_number) AS next_half,
                       lead(outs_when_up) OVER (PARTITION BY game_pk ORDER BY at_bat_number) AS next_outs
                FROM {table}
                WHERE game_type = 'R' AND events IS NOT NULL AND pitcher IS NOT NULL
            ), calculated AS (
                SELECT *,
                    CASE
                        WHEN next_inning = inning AND next_half = inning_topbot
                            THEN greatest(0, next_outs - outs_when_up)
                        WHEN next_inning IS NOT NULL THEN 3 - outs_when_up
                        WHEN inning_topbot = 'Bot' AND post_bat_score > post_fld_score THEN
                            CASE
                                WHEN events IN ('strikeout', 'field_out', 'force_out', 'fielders_choice_out', 'sac_fly', 'sac_bunt') THEN 1
                                WHEN events IN ('strikeout_double_play', 'grounded_into_double_play', 'double_play', 'sac_fly_double_play', 'sac_bunt_double_play') THEN 2
                                WHEN events = 'triple_play' THEN 3 ELSE 0
                            END
                        ELSE 3 - outs_when_up
                    END AS outs,
                    CASE WHEN events <> 'truncated_pa' THEN 1 ELSE 0 END AS bf,
                    post_bat_score - bat_score AS runs_scored,
                    CASE WHEN events IN ('walk', 'intent_walk') THEN 1 ELSE 0 END AS bb,
                    CASE WHEN events IN ('strikeout', 'strikeout_double_play') THEN 1 ELSE 0 END AS k
                FROM terminal
            )
            SELECT game_pk, pitcher, sum(outs) AS outs, sum(bf) AS bf,
                   sum(runs_scored) AS runs_scored, sum(bb) AS bb, sum(k) AS k
            FROM calculated GROUP BY 1, 2
            """
        ).fetchdf()
        official = connection.execute(
            """
            SELECT game_pk, pitcher_id, ip, runs, earned_runs, walks, strikeouts, batters_faced
            FROM pitcher_game_lines
            """
        ).fetchdf()

    official["official_outs"] = official["ip"].map(baseball_ip_to_outs)
    merged = official.merge(
        derived,
        left_on=["game_pk", "pitcher_id"],
        right_on=["game_pk", "pitcher"],
        how="outer",
        indicator=True,
    )
    comparisons: dict[str, Any] = {}
    for official_field, derived_field in [
        ("official_outs", "outs"),
        ("batters_faced", "bf"),
        ("runs", "runs_scored"),
        ("walks", "bb"),
        ("strikeouts", "k"),
    ]:
        official_values = pd.to_numeric(merged[official_field], errors="coerce")
        derived_values = pd.to_numeric(merged[derived_field], errors="coerce")
        difference = official_values - derived_values
        comparisons[official_field] = {
            "derived_field": derived_field,
            "official_total": int(official_values.sum()),
            "derived_total": int(derived_values.sum()),
            "compared_rows": int(difference.notna().sum()),
            "exact_rows": int(difference.eq(0).sum()),
            "mean_absolute_difference": round(float(difference.abs().mean()), 6),
            "max_absolute_difference": int(difference.abs().max()),
        }
    return {
        "status": "diagnostic_only",
        "official_pitcher_game_rows": int(len(official)),
        "derived_pitcher_game_rows": int(len(derived)),
        "matched_rows": int((merged["_merge"] == "both").sum()),
        "official_only_rows": int((merged["_merge"] == "left_only").sum()),
        "official_earned_runs_total": int(pd.to_numeric(official["earned_runs"], errors="coerce").sum()),
        "comparisons": comparisons,
        "known_partial_statcast_game": {
            "game_pk": 823244,
            "statcast_pitches": 10,
            "official_pitcher_line_pitches": 258,
        },
        "interpretation": "event HR/BB/K nearly reconcile after the known partial game; score deltas do not reconcile to pitcher-charged R because inherited runners remain charged to the responsible pitcher",
    }


def build_catcher_descriptive_slice0_audit(
    years: tuple[int, ...] = DEFAULT_YEARS,
    data_dir: Path | None = None,
    probe_official: bool = False,
) -> dict[str, Any]:
    root = Path(data_dir or settings.data_dir)
    coverage = [_audit_year(year, root) for year in years]
    payload = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready_for_slice1_source_backfill" if all(row["status"] == "ready" for row in coverage) else "partial",
        "scope": {
            "years": list(years),
            "claim_language": "descriptive observed association; not causal catcher value",
            "leaderboards_allowed": False,
        },
        "source_fingerprints": {
            "legacy_cera_code": _fingerprint(LEGACY_CERA_CODE),
            "starter_reference_service": _fingerprint(Path(__file__).with_name("starter_reference_service.py")),
        },
        "legacy_workbook": audit_legacy_workbook(),
        "xera_proxy": _audit_xera(root),
        "local_coverage": coverage,
        "official_source_probe": (
            [_official_feed_probe(year, root) for year in years]
            if probe_official
            else {"status": "not_run", "instruction": "rerun the builder with --probe-official"}
        ),
        "local_2026_reconciliation": _reconcile_2026_local_controls(root),
        "metric_source_status": {
            "outs": "not stored directly; derive from official runner out movements, then reconcile to pitcher-game IP",
            "bf": "terminal PA rows available; truncated/mid-PA cases require official-line reconciliation",
            "runs_scored_while_pair": "available from post_bat_score - bat_score",
            "pitcher_charged_runs": "requires official play feed responsiblePitcher backfill",
            "earned_runs": "requires official play feed earned/teamUnearned backfill",
            "hr": "available from terminal event home_run",
            "bb": "store walk and intent_walk separately; existing FIP builder excludes intent_walk",
            "hbp": "available from terminal event hit_by_pitch",
            "k": "available from strikeout and strikeout_double_play",
        },
        "slice1_contract": {
            "pair_grain": "one row per season, pitching_team_id, pitcher_id, catcher_id",
            "pair_unique_key": ["season", "pitching_team_id", "pitcher_id", "catcher_id"],
            "pa_unique_key": ["season", "game_pk", "at_bat_number"],
            "pitch_unique_key": ["season", "game_pk", "at_bat_number", "pitch_number"],
            "required_raw_fields": [
                "outs", "bf", "runs_scored_while_pair", "pitcher_charged_runs", "earned_runs",
                "hr", "bb_unintentional", "intentional_walks", "hbp", "k",
            ],
            "source_priority": [
                "immutable MLB Stats API game-feed snapshots for runner outs, responsible pitcher and earned flags",
                "year DuckDB Statcast rows for terminal catcher fielder_2, pitch/PA keys and pitch events",
                "official pitcher-game lines for pitcher reconciliation controls",
                "Baseball Reference By Catcher splits as comparison-only legacy reference",
                "static catcher2025_processed.xlsx as non-authoritative reconciliation target",
            ],
            "run_attribution_policy": {
                "preserve_both": ["runs_scored_while_pair", "pitcher_charged_runs", "earned_runs"],
                "responsible_catcher": "catcher on the PA where the responsible runner reached base",
                "current_catcher": "catcher on the scoring PA",
                "metric_choice": "freeze only after representative in-game catcher-change reconciliation; do not discard either field",
            },
            "reconciliation_tests": [
                "pair outs/BF/HR/BB/HBP/K sum to pitcher-team-season totals",
                "charged R/ER sum to official pitcher-game and pitcher-season lines",
                "runs_scored_while_pair sum to opponent team scoring within each game",
                "all outs are integers and displayed innings round-trip through outs",
                "pitch, PA and pair unique keys have zero duplicates",
                "traded pitchers/catchers remain separated by pitching_team_id and also aggregate to season TOT",
                "in-game catcher changes preserve current and responsible catcher IDs",
                "zero-denominator and single-catcher pitcher baselines remain unavailable",
            ],
        },
        "missing_sources": [
            "No repository DRS dataset or licensed/versioned DRS source is present.",
            "No explicit park-factor table is present; home/away team is only a venue proxy.",
            "Only 2026 currently has local official pitcher-game lines; 2021-2025 controls require backfill.",
            "No immutable MLB game-feed snapshots are present yet for runner responsibility/earned-run accounting.",
            "No documented 2021-2025 annual FIP constants are present; the 2026 estimator metadata contains only a legacy-calibrated constant.",
        ],
    }
    output = audit_output_path(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def get_catcher_descriptive_slice0_audit(data_dir: Path | None = None) -> dict[str, Any]:
    return json.loads(audit_output_path(data_dir).read_text(encoding="utf-8"))
