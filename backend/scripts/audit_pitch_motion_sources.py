"""Read-only local motion-data inventory; never fetch or modify season data."""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUTPUT = DATA / "sample/petehub_pitch_motion_data_audit_v1.json"
FIELDS = [
    "arm_angle", "release_pos_x", "release_pos_y", "release_pos_z", "release_extension",
    "release_speed", "vx0", "vy0", "vz0", "ax", "ay", "az", "plate_x", "plate_z",
    "sz_top", "sz_bot", "bat_speed", "swing_length", "attack_angle", "attack_direction",
    "swing_path_tilt", "intercept_ball_minus_batter_pos_x_inches",
    "intercept_ball_minus_batter_pos_y_inches", "miss_distance", "launch_speed", "launch_angle",
]
# The explicit denominator includes bunts, and is reported separately from all rows.
SWING = "description IN ('swinging_strike','swinging_strike_blocked','foul','foul_tip','hit_into_play','foul_bunt','missed_bunt','bunt_foul_tip')"


def records(cursor):
    names = [x[0] for x in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def finite(field):
    return f'isfinite("{field}")'


def audit_database(path):
    with duckdb.connect(str(path), read_only=True) as db:
        tables = [x[0] for x in db.execute("SHOW TABLES").fetchall()]
        table = "pitches_enriched" if "pitches_enriched" in tables else "pitches"
        schema = {t: records(db.execute(f'DESCRIBE "{t}"')) for t in tables}
        cols = {x["column_name"] for x in schema[table]}
        counts = records(db.execute(f"SELECT count(*) AS rows, count(DISTINCT pitcher) AS pitchers, count(DISTINCT batter) AS batters, min(game_date) AS first_date, max(game_date) AS last_date FROM {table}"))[0]
        counts["first_date"] = str(counts["first_date"])
        counts["last_date"] = str(counts["last_date"])
        present = [f for f in FIELDS if f in cols]
        expr = ",".join(f'count(*) FILTER (WHERE {finite(f)}) AS "{f}"' for f in present)
        valid = records(db.execute(f"SELECT {expr} FROM {table}"))[0]
        release = " AND ".join(finite(f) for f in ["release_pos_x", "release_pos_y", "release_pos_z"])
        trajectory = " AND ".join(finite(f) for f in ["release_pos_x", "release_pos_y", "release_pos_z", "vx0", "vy0", "vz0", "ax", "ay", "az"])
        combined = records(db.execute(f"""SELECT
            count(*) FILTER (WHERE {release}) AS release_xyz,
            count(*) FILTER (WHERE {trajectory}) AS trajectory_inputs,
            count(*) FILTER (WHERE {finite('sz_top')} AND {finite('sz_bot')} AND sz_top>sz_bot AND sz_bot>0) AS ordered_positive_zone,
            count(*) FILTER (WHERE p_throws IN ('L','R')) AS pitcher_hand_lr,
            count(*) FILTER (WHERE stand IN ('L','R')) AS batter_side_lr,
            count(*) FILTER (WHERE arm_angle BETWEEN -90 AND 90) AS arm_angle_in_broad_range,
            count(DISTINCT pitcher) FILTER (WHERE {finite('arm_angle')}) AS pitchers_with_any_arm_angle,
            count(DISTINCT batter) FILTER (WHERE {finite('bat_speed')}) AS batters_with_any_bat_speed,
            count(*) FILTER (WHERE {SWING}) AS swing_event_rows
            FROM {table}"""))[0]
        swings = records(db.execute(f"SELECT {expr} FROM {table} WHERE {SWING}"))[0]
        details = {}
        if "2026" in path.name:
            details = {
                "game_types": records(db.execute(f"SELECT game_type, count(*) AS rows FROM {table} GROUP BY 1 ORDER BY 1")),
                "hand_values": {f: records(db.execute(f'SELECT "{f}" AS value,count(*) AS rows FROM {table} GROUP BY 1 ORDER BY 1')) for f in ["p_throws", "stand"]},
                "arm_angle_range": records(db.execute(f"SELECT min(arm_angle) AS minimum,max(arm_angle) AS maximum FROM {table} WHERE isfinite(arm_angle)"))[0],
                "pitchers_without_arm_angle": records(db.execute(f"SELECT pitcher,any_value(player_name) AS name,count(*) AS rows FROM {table} GROUP BY pitcher HAVING count(*) FILTER (WHERE isfinite(arm_angle))=0 ORDER BY rows DESC")),
                "pitch_identity_duplicates": db.execute(f"SELECT count(*) FROM (SELECT game_pk,at_bat_number,pitch_number FROM {table} GROUP BY ALL HAVING count(*)>1)").fetchone()[0],
                "base_rows": db.execute("SELECT count(*) FROM pitches").fetchone()[0],
                "player_master_columns": [x["column_name"] for x in schema.get("player_master", [])],
            }
        return {
            "source": str(path.relative_to(ROOT)), "modified_at_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            "table": table, **counts, "finite_counts_all_rows": valid,
            "missing_columns": [f for f in FIELDS if f not in cols], "combined": combined,
            "finite_counts_swing_event_rows": swings,
            "bio_or_frame_columns_any_table": {t: [x["column_name"] for x in rows if re.search(r'height|weight|bat_tip|bat_handle|joint|skeleton|frame_time|pose', x["column_name"], re.I)] for t, rows in schema.items()},
            **details,
        }


def cache_audit():
    roster_files = list((DATA / "MLB2026/official_active_rosters").glob("*.json"))
    rosters = [json.loads(p.read_text(encoding="utf-8")) for p in roster_files]
    players = [p for r in rosters for p in r.get("players", [])]
    boxes = list((DATA / "MLB2026/game_boxscores").glob("*.json"))
    people = []
    for p in boxes:
        payload = json.loads(p.read_text(encoding="utf-8"))
        for team in payload.get("teams", {}).values():
            people.extend(x.get("person", {}) for x in team.get("players", {}).values())
    timing = []
    for p in sorted((DATA / "MissDistance").glob("2026*.csv")):
        with p.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            timing.append({"source": str(p.relative_to(ROOT)), "rows": len(rows), "players": len({r.get("id") for r in rows}), "columns": reader.fieldnames})
    # Filenames only: no auth databases or unrelated private contents are read.
    candidates = [str(p.relative_to(ROOT)) for base in [DATA / f"MLB{y}" for y in range(2021, 2027)] for p in base.rglob("*") if p.is_file() and re.search(r'people|biograph|player_bio|skeleton|bat_path|motion_capture|\.glb$|\.gltf$', p.name, re.I)]
    return {
        "scope": "2026 normalized roster and raw boxscore caches; 2026 timing CSV; season-folder bio/motion filename search only",
        "roster_files": [str(p.relative_to(ROOT)) for p in roster_files],
        "roster_player_entries": len(players), "roster_player_columns": sorted({k for p in players for k in p}),
        "roster_retrieved_at": {r.get("team_code"): r.get("retrieved_at") for r in rosters},
        "boxscore_files": len(boxes), "boxscore_distinct_people": len({p.get("id") for p in people}),
        "boxscore_person_columns": sorted({k for p in people for k in p}),
        "boxscore_people_with_height": len({p.get("id") for p in people if p.get("height")}),
        "boxscore_people_with_weight": len({p.get("id") for p in people if p.get("weight")}),
        "timing_summaries": timing, "bio_or_motion_filename_candidates": candidates,
    }


if __name__ == "__main__":
    report = {
        "schema_version": "pitch_motion_data_audit_v1", "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Existing local data only. No network, backfill, source mutation, model production or visual validation.",
        "count_semantics": "All local table rows (all game types), not a complete-league certification. Finite counts exclude null/NaN/Inf; presence is not physical correctness. Swing-event denominator includes listed bunt events. Body height is not sz_top or release_pos_z.",
        "source_review": {
            "replay_arm_angle": "Database and Movement contain arm_angle; game_pitcher_analysis_service.py replay scalar_columns currently omits it. No API change performed.",
            "player_bio": "active_roster_service.py requests hydrate=person but retains identity/jersey/position/status only; height/weight/career batSide/pitchHand are not retained by that contract.",
            "motion_limits": "No frame-level skeleton/bat-tip/handle/time series found in inspected tables/caches. Scalar arm angle, bat speed, attack angles and intercept offsets do not uniquely specify a full-body motion or exact contact time.",
            "follow_up": "Versioned nullable bio and replay motion availability before generic rig production. This audit does not complete F2.3/F2.4/F2.5.",
        },
        "limitations": [
            "No verification that local season download covers every league game; no physical plausibility/trajectory closure or browser test in this audit.",
            "2026 roster/boxscore cache review is scoped, not all teams or every possible upstream payload. No external API fetched.",
            "A broader recursive CSV header search was stopped without results; its coverage is excluded. No claim that every unrelated CSV/research file lacks bio.",
        ],
        "seasons": [],
    }
    for path in sorted(DATA.glob("MLB*/mlb_*.duckdb")):
        item = audit_database(path)
        report["seasons"].append(item)
        print(json.dumps({k: item[k] for k in ["source", "rows", "finite_counts_all_rows", "combined"]}), flush=True)
    report["caches"] = cache_audit()
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}", flush=True)
