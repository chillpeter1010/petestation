"""Targeted Slice 2 repairs from immutable Savant snapshots; no model refresh."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[2] / "data"
OUT = ROOT / "research/decision_support_slice2_20261114"


def qi(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def sync_metadata(year: int, root: Path, output: Path) -> bool:
    path=root/f"MLB{year}/mlb_{year}_meta.json"
    if not path.exists():return False
    before=output/'before'/f'meta_{year}.json'
    if not before.exists():before.write_bytes(path.read_bytes())
    payload=json.loads(path.read_text(encoding='utf-8'))
    with duckdb.connect(str(root/f'MLB{year}/mlb_{year}.duckdb'),read_only=True) as c:
        count=c.execute('SELECT count(*) FROM pitches').fetchone()[0]
    for key in ['pitches_rows','pitch_rows']:
        if key in payload:payload[key]=count
    payload['decision_repair']={'version':'slice2_20261114','effective_data_root':str(root),'source_snapshots':str(output/'sources')}
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    return True


def repair_game(year: int, pk: int, root: Path = ROOT, output: Path = OUT) -> dict:
    snapshot = output / "sources" / f"statcast_{pk}.csv.gz"
    backups = output / "before"
    backups.mkdir(parents=True, exist_ok=True)
    db = root / f"MLB{year}/mlb_{year}.duckdb"
    print(f"{year}/{pk}: prepare and validate snapshot", flush=True)
    # Explicit writer scope is the two authorized games only; every other game is fingerprinted.
    with duckdb.connect(str(db), config={"threads": 1}) as c:
        columns = c.execute("DESCRIBE pitches").fetchall()
        c.execute("CREATE TEMP TABLE downloaded AS SELECT * FROM read_csv(?,all_varchar=true)", [str(snapshot)])
        raw_cols = {r[0] for r in c.execute("DESCRIBE downloaded").fetchall()}
        ids = c.execute("SELECT DISTINCT try_cast(game_pk AS BIGINT) FROM downloaded").fetchall()
        if ids != [(pk,)]:
            raise ValueError(f"Unexpected game IDs: {ids}")
        extra = {
            "pitcher_id": "pitcher", "batter_id": "batter", "season_year": str(year),
            "pitch_uid": "game_pk || '_' || at_bat_number || '_' || pitch_number",
            "pitcher_team": "CASE WHEN inning_topbot='Top' THEN home_team ELSE away_team END",
            "offense_team": "CASE WHEN inning_topbot='Top' THEN away_team ELSE home_team END",
            "batter_team": "CASE WHEN inning_topbot='Top' THEN away_team ELSE home_team END",
        }
        expressions = []
        for name, dtype, *_ in columns:
            value = qi(name) if name in raw_cols else extra.get(name, "NULL")
            expressions.append(f"try_cast({value} AS {dtype}) AS {qi(name)}")
        c.execute("CREATE TEMP TABLE replacement AS SELECT " + ",".join(expressions) + " FROM downloaded")
        n, unique = c.execute("SELECT count(*),count(DISTINCT pitch_uid) FROM replacement").fetchone()
        if n != unique or n < 100:
            raise ValueError("Incomplete or duplicate replacement")
        before = c.execute("SELECT count(*) FROM pitches WHERE game_pk=?", [pk]).fetchone()[0]
        backup = backups / f"pitches_{year}_{pk}.parquet"
        if not backup.exists():
            c.execute(f"COPY (SELECT * FROM pitches WHERE game_pk={pk}) TO '{backup.as_posix()}' (FORMAT PARQUET)")
            c.execute(f"COPY (SELECT * FROM games WHERE game_pk={pk}) TO '{(backups/f'games_{year}_{pk}.parquet').as_posix()}' (FORMAT PARQUET)")
        original_count = c.execute("SELECT count(*) FROM read_parquet(?)", [str(backup)]).fetchone()[0]
        unrelated_before = c.execute("SELECT count(*),bit_xor(hash(pitches)) FROM pitches WHERE game_pk<>?", [pk]).fetchone()
        c.execute("BEGIN")
        try:
            c.execute("DELETE FROM pitches WHERE game_pk=?", [pk])
            c.execute("INSERT INTO pitches SELECT * FROM replacement")
            c.execute("""UPDATE games SET total_pitches=(SELECT count(*) FROM replacement),
                total_plate_appearances=(SELECT count(DISTINCT at_bat_number) FROM replacement) WHERE game_pk=?""", [pk])
            c.execute("UPDATE season_meta SET value=cast((SELECT count(*) FROM pitches) AS VARCHAR) WHERE key='pitch_rows'")
            unrelated_after = c.execute("SELECT count(*),bit_xor(hash(pitches)) FROM pitches WHERE game_pk<>?", [pk]).fetchone()
            if unrelated_before != unrelated_after:
                raise ValueError("Unrelated games changed")
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
    # Keep the local CSV cache in agreement, preserving its original column set and all other rows.
    csv_path = root / f"MLB{year}/mlb_{year}_pitches.csv.gz"
    temp = csv_path.with_name(f"mlb_{year}_decision_repair.tmp.csv.gz")
    print(f"{year}/{pk}: synchronize local CSV cache", flush=True)
    with duckdb.connect(":memory:", config={"threads": 1}) as c:
        c.execute("CREATE TABLE original AS SELECT * FROM read_csv(?,all_varchar=true)", [str(csv_path)])
        csv_columns = [r[0] for r in c.execute("DESCRIBE original").fetchall()]
        c.execute("CREATE TABLE incoming AS SELECT * FROM read_csv(?,all_varchar=true)", [str(snapshot)])
        available = {r[0] for r in c.execute("DESCRIBE incoming").fetchall()}
        selected = ",".join(qi(v) if v in available else f"NULL AS {qi(v)}" for v in csv_columns)
        c.execute(f"CREATE TABLE expected AS SELECT * FROM original WHERE game_pk<>'{pk}' UNION ALL SELECT {selected} FROM incoming")
        c.execute(f"COPY expected TO '{temp.as_posix()}' (FORMAT CSV,HEADER,COMPRESSION GZIP)")
        print(f"{year}/{pk}: CSV written; verify row round-trip", flush=True)
        # Full row multiset equality, not just counts, before atomically replacing the CSV.
        c.execute(f"CREATE VIEW written AS SELECT * FROM read_csv('{temp.as_posix().replace(chr(39), chr(39)*2)}',all_varchar=true)")
        difference = c.execute("SELECT count(*) FROM ((SELECT * FROM expected EXCEPT ALL SELECT * FROM written) UNION ALL (SELECT * FROM written EXCEPT ALL SELECT * FROM expected))").fetchone()[0]
        if difference:
            raise ValueError("CSV round-trip differs")
        csv_before = backups / f"csv_game_{year}_{pk}.parquet"
        if not csv_before.exists():
            c.execute(f"COPY (SELECT * FROM original WHERE game_pk='{pk}') TO '{csv_before.as_posix()}' (FORMAT PARQUET)")
    temp.replace(csv_path)
    metadata_synced=sync_metadata(year,root,output)
    report = {"year": year, "game_pk": pk, "before_rows": original_count, "at_run_before_rows": before, "after_rows": n,
              "unrelated_games_unchanged": True, "csv_roundtrip_exact": True,
              "metadata_synced":metadata_synced,
              "raw_snapshot": str(snapshot), "before_backup": str(backup),
              "formal_models_refitted": False, "tracking_imputed": False,
              "note": "Changed game derivatives are not silently overwritten; old formal exports remain frozen and require version-aware refresh later."}
    (output/f"repair_{year}.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return report


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for year, pk in [(2024, 746731), (2026, 823244)]:
        repair_game(year, pk)
