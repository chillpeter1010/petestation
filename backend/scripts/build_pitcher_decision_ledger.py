"""Slice 3 bounded-memory ledger builder; reuses official snapshots only."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.pitcher_decision_ledger import parse_game

ROOT = Path(__file__).resolve().parents[2] / "data"
OUT = ROOT / "research/decision_support_pipeline_20261114"
FLOATS = {"pre_home_we", "source_re24", "raw_home_wpa"}
BOOLS = {"is_pitch", "is_pitch_change", "zero_pitch", "is_complete", "is_batter_faced", "mid_pa_change",
         "runner_index_missing", "is_initial_start", "observed_change", "injury_observed_before", "mandatory_removed_pitcher",
         "compound_prelude", "completed_batter_play", "base_state_known", "is_out", "is_scoring"}
INTS = {"year", "game_pk", "at_bat_number", "event_index", "pitch_number", "inning", "balls", "strikes",
        "current_pitches", "current_bf", "pitch_count", "scheduled_innings", "entry_ab", "entry_event_index", "exit_ab", "exit_event_index",
        "pitches", "bf", "outs", "entry_inning", "last_inning", "home_score", "away_score", "base_state"}
STRING_IDS = {"event_id", "decision_id", "appearance_id", "play_id"}


def arrow_type(name: str) -> pa.DataType:
    if name in FLOATS: return pa.float64()
    if name in BOOLS: return pa.bool_()
    if name in INTS or name.endswith(("_before", "_after")) or (name.endswith("_id") and name not in STRING_IDS): return pa.int64()
    return pa.string()


class Writers:
    def __init__(self, output: Path, year: int):
        self.output, self.year = output, year
        self.writers = {}
        self.counts = Counter()

    def append(self, name: str, rows: list[dict]) -> None:
        if not rows: return
        if name not in self.writers:
            schema = pa.schema([pa.field(k,arrow_type(k)) for k in rows[0]])
            self.writers[name] = pq.ParquetWriter(self.output/f"{name}_{self.year}.tmp.parquet",schema,compression="zstd")
        writer = self.writers[name]
        writer.write_table(pa.Table.from_pylist(rows,schema=writer.schema))
        self.counts[name] += len(rows)

    def close(self) -> None:
        for name, writer in self.writers.items():
            writer.close()
            (self.output/f"{name}_{self.year}.tmp.parquet").replace(self.output/f"{name}_{self.year}.parquet")


def build(year: int, root: Path = ROOT, output: Path = OUT) -> dict:
    output.mkdir(parents=True,exist_ok=True)
    db = root/f"MLB{year}/mlb_{year}.duckdb"
    with duckdb.connect(str(db),read_only=True,config={"threads":1}) as c:
        local = c.execute("""SELECT game_pk,at_bat_number,first(home_win_exp ORDER BY pitch_number),
            CASE WHEN count(delta_pitcher_run_exp)=count(*) THEN sum(delta_pitcher_run_exp) END
            FROM pitches WHERE game_type='R' GROUP BY 1,2""").fetchall()
    by_game = defaultdict(dict)
    for pk, ab, we, re in local:
        by_game[int(pk)][int(ab)] = {"pre_home_we":we,"source_re24":re}
    del local
    inventory = pq.read_table(root/f"research/decision_support_slice1_20261112/feed_inventory_{year}.parquet").to_pylist()
    writers = Writers(output,year)
    batch = defaultdict(list)
    source_drift = []
    for i, entry in enumerate(inventory,1):
        path=Path(entry["path"])
        if not path.exists(): path=root/f"research/catcher_descriptive/slice1/raw_game_feeds/{year}/{entry['game_pk']}.json.gz"
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry["compressed_sha256"]:
            source_drift.append(entry["game_pk"])
            raise ValueError(f"Feed changed since Slice 1: {entry['game_pk']}")
        payload=json.loads(gzip.decompress(raw))
        tables=parse_game(year,payload,by_game.get(int(entry["game_pk"])))
        for name, rows in tables.items(): batch[name].extend(rows)
        if i%80==0 or i==len(inventory):
            for name, rows in batch.items(): writers.append(name,rows)
            batch.clear()
            print(f"{year}: ledger {i}/{len(inventory)} games",flush=True)
    writers.close()
    with duckdb.connect(":memory:",config={"threads":1}) as c:
        for name in writers.counts:
            path=(output/f"{name}_{year}.parquet").as_posix()
            c.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path}')")
        checks={
            "duplicate_event_keys":c.execute("SELECT count(*)-count(DISTINCT event_id) FROM events").fetchone()[0],
            "duplicate_play_keys":c.execute("SELECT count(*)-count(DISTINCT outcome_key) FROM plays").fetchone()[0],
            "duplicate_decision_keys":c.execute("SELECT count(*)-count(DISTINCT decision_id) FROM decisions").fetchone()[0],
            "unmatched_outcome_keys":c.execute("SELECT count(*) FROM decisions d LEFT JOIN plays p USING(outcome_key) WHERE p.outcome_key IS NULL").fetchone()[0],
        }
        assert not any(checks.values()),checks
        c.execute("""CREATE TABLE clock_issues AS WITH x AS(
            SELECT game_pk,event_id,try_cast(event_time AS TIMESTAMPTZ) t,time_basis,
            lag(try_cast(event_time AS TIMESTAMPTZ)) OVER(PARTITION BY game_pk ORDER BY at_bat_number,event_index) prior_t
            FROM events WHERE is_pitch)
            SELECT game_pk,event_id,cast(t AS VARCHAR) event_time,cast(prior_t AS VARCHAR) prior_time,time_basis
            FROM x WHERE t<prior_t OR time_basis='play_start_fallback' OR t IS NULL""")
        c.execute(f"COPY clock_issues TO '{(output/f'chronology_issues_{year}.parquet').as_posix()}' (FORMAT PARQUET)")
        counts={
            "physical_pitches":c.execute("SELECT count(*) FROM events WHERE is_pitch").fetchone()[0],
            "pitch_change_actions":c.execute("SELECT count(*) FROM events WHERE is_pitch_change").fetchone()[0],
            "completed_batters":c.execute("SELECT count(*) FROM plays WHERE is_batter_faced").fetchone()[0],
            "zero_pitch_plays":c.execute("SELECT count(*) FROM plays WHERE zero_pitch").fetchone()[0],
            "zero_pitch_appearances":c.execute("SELECT count(*) FROM appearances WHERE zero_pitch").fetchone()[0],
            "mid_pa_changes":c.execute("SELECT count(*) FROM plays WHERE mid_pa_change").fetchone()[0],
            "unpriced_wpa_plays":c.execute("SELECT count(*) FROM plays WHERE raw_home_wpa IS NULL").fetchone()[0],
            "uncertain_base_decisions":c.execute("SELECT count(*) FROM decisions WHERE NOT base_state_known").fetchone()[0],
            "removed_current_pitcher_boundaries":c.execute("SELECT count(*) FROM decisions WHERE mandatory_removed_pitcher").fetchone()[0],
            "source_clock_issue_games":c.execute("SELECT count(DISTINCT game_pk) FROM clock_issues").fetchone()[0],
            "invalid_known_base_states":c.execute("SELECT count(*) FROM decisions WHERE base_state_known AND (base_state IS NULL OR base_state NOT BETWEEN 0 AND 7)").fetchone()[0],
        }
        assert counts['invalid_known_base_states']==0
    report={"slice":3,"year":year,"games":len(inventory),"rows":dict(writers.counts),"counts":counts,"checks":checks,
        "source_drift":source_drift,"outcomes_stored_once":True,"formal_models_refitted":False,
        "limitations":["Minimum-batter permission is statutory, not knowledge of warm-up or medical clearance.",
            "Unpriced adjacent WE/RE boundaries remain null for Slice 10, not interpolated.",
            "Rare pitcher position switches, missing runner event indexes and compound substitutions remain explicit filters."]}
    (output/f"ledger_{year}.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report),flush=True)
    return report


if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p=argparse.ArgumentParser();p.add_argument("--year",type=int,required=True,choices=range(2021,2027));a=p.parse_args();build(a.year)
