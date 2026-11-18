"""Align immutable official events with Statcast physics; build separate research observations."""
from __future__ import annotations
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.decision_temporal_common import ROOT,BASE,OUT,align,save

RAW=['pitch_uid','pitch_number','pitch_type','pitcher','batter','release_speed','release_spin_rate','release_extension',
     'release_pos_x','release_pos_z','pfx_x','pfx_z','spin_axis','arm_angle','plate_x','plate_z','sz_bot','sz_top','stand','p_throws']

def build(year:int)->None:
    OUT.mkdir(parents=True,exist_ok=True)
    with duckdb.connect(str(ROOT/f'MLB{year}/mlb_{year}.duckdb'),read_only=True,config={'threads':1}) as raw:
        frame=raw.execute('SELECT game_pk,at_bat_number,'+','.join(RAW)+" FROM pitches WHERE game_type='R' ORDER BY game_pk,at_bat_number,pitch_number").fetch_arrow_table()
    source=defaultdict(lambda:defaultdict(list))
    for row in frame.to_pylist():source[row.pop('game_pk')][row.pop('at_bat_number')].append(row)
    del frame
    inventory=pq.read_table(ROOT/f'research/decision_support_slice1_20261112/feed_inventory_{year}.parquet').to_pylist()
    fields={'event_id':pa.string(),'alignment_status':pa.string()}
    for key in RAW:fields[key]=pa.string() if key in {'pitch_uid','pitch_type','stand','p_throws'} else pa.float64()
    schema=pa.schema([pa.field(k,v) for k,v in fields.items()]);tmp=OUT/f'alignment_{year}.tmp.parquet'
    writer=pq.ParquetWriter(tmp,schema,compression='zstd');counts=defaultdict(int);batch=[]
    for i,entry in enumerate(inventory,1):
        path=Path(entry['path']);packed=path.read_bytes()
        if hashlib.sha256(packed).hexdigest()!=entry['compressed_sha256']:raise ValueError('Official snapshot drift')
        payload=json.loads(gzip.decompress(packed));pk=int(entry['game_pk'])
        for play in payload['liveData']['plays']['allPlays']:
            ab=int(play['atBatIndex'])+1;events=[e for e in play.get('playEvents',[]) if e.get('isPitch')]
            official=[]
            for event in events:
                pd=event.get('pitchData',{});xy=pd.get('coordinates',{})
                official.append({'speed':pd.get('startSpeed'),'type':event.get('details',{}).get('type',{}).get('code'),'x':xy.get('pX'),'z':xy.get('pZ')})
            rows=source.get(pk,{}).get(ab,[])
            # Automatic balls/strikes without a delivered pitch have no tracked physics.
            rows=[r for r in rows if r['release_speed'] is not None or r['plate_x'] is not None]
            matched=align(official,rows)
            for j,event in enumerate(events):
                row=rows[matched[j]] if j in matched else dict.fromkeys(RAW)
                status='validated_order' if j in matched else 'unmatched_or_ambiguous'
                batch.append({'event_id':f"{pk}:{ab}:{event['index']}",'alignment_status':status,**row});counts[status]+=1
        if i%80==0 or i==len(inventory):
            writer.write_table(pa.Table.from_pylist(batch,schema=schema));batch=[]
            print(f'{year}: physics alignment {i}/{len(inventory)}',flush=True)
    writer.close();tmp.replace(OUT/f'alignment_{year}.parquet');del source
    c=duckdb.connect(config={'threads':2});q=lambda p:p.as_posix()
    c.execute(f"CREATE VIEW e AS SELECT * FROM read_parquet('{q(BASE/f'events_{year}.parquet')}')")
    c.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{q(BASE/f'plays_{year}.parquet')}')")
    c.execute(f"CREATE VIEW a AS SELECT * FROM read_parquet('{q(BASE/f'appearances_{year}.parquet')}')")
    c.execute(f"CREATE VIEW roster AS SELECT * FROM read_parquet('{q(BASE/f'roster_{year}.parquet')}')")
    c.execute(f"CREATE VIEW m AS SELECT * FROM read_parquet('{q(OUT/f'alignment_{year}.parquet')}')")
    bad=c.execute(f"SELECT DISTINCT game_pk FROM read_parquet('{q(BASE/f'chronology_issues_{year}.parquet')}')").fetchall()
    badids=','.join(str(r[0]) for r in bad) or '-1'
    c.execute(f"""CREATE TABLE obs AS WITH ev AS (
      SELECT *,lag(home_score_after) OVER w pre_h,lag(away_score_after) OVER w pre_a,
       lead(outs_before) OVER w next_outs,lead(base_state_before) OVER w next_base,
       lead(balls_before) OVER w next_balls,lead(strikes_before) OVER w next_strikes,
       lead(event_index) OVER w next_index
      FROM e WINDOW w AS(PARTITION BY game_pk,at_bat_number ORDER BY event_index)),
      result AS(SELECT *,max(CASE WHEN half='top' THEN away_score_after ELSE home_score_after END)
       OVER(PARTITION BY game_pk,inning,half) half_final_score,
       max(epoch(try_cast(end_time AS TIMESTAMPTZ))) OVER(PARTITION BY game_pk) game_completed_at FROM p)
      SELECT ev.year,ev.game_pk,ev.at_bat_number,ev.event_id,ev.event_index,ev.appearance_id,ev.pitcher_id,ev.batter_id,
       ev.inning,ev.half,ev.balls_before,ev.strikes_before,ev.outs_before,ev.base_state_before,
       coalesce(pre_h,p.home_score_before) home_before,coalesce(pre_a,p.away_score_before) away_before,
       CASE WHEN ev.half='top' THEN ev.away_score_after-coalesce(pre_a,p.away_score_before)
         ELSE ev.home_score_after-coalesce(pre_h,p.home_score_before) END runs_on_event,
       coalesce(next_outs,p.outs_after) post_outs,coalesce(next_base,p.base_state_after) post_base,
       CASE WHEN next_index IS NULL AND p.is_batter_faced THEN 0 ELSE next_balls END post_balls,
       CASE WHEN next_index IS NULL AND p.is_batter_faced THEN 0 ELSE next_strikes END post_strikes,
       p.half_final_score-CASE WHEN ev.half='top' THEN coalesce(pre_a,p.away_score_before) ELSE coalesce(pre_h,p.home_score_before) END remaining_runs,
       p.game_completed_at,p.scheduled_innings,a.role,epoch(try_cast(a.entry_time AS TIMESTAMPTZ)) entry_at,
       epoch(try_cast(a.exit_time AS TIMESTAMPTZ)) closed_at,
       epoch(try_cast(ev.event_time AS TIMESTAMPTZ)) event_at,
       epoch(try_cast(ev.end_time AS TIMESTAMPTZ)) observed_at,
       ev.game_pk NOT IN ({badids}) AND ev.time_basis<>'play_start_fallback' AND NOT p.runner_index_missing
        AND ev.base_state_before BETWEEN 0 AND 7 AND ev.outs_before BETWEEN 0 AND 2
        AND coalesce(next_base,p.base_state_after) BETWEEN 0 AND 7
        AND epoch(try_cast(ev.end_time AS TIMESTAMPTZ))>=epoch(try_cast(ev.event_time AS TIMESTAMPTZ)) source_valid,
       EXISTS(SELECT 1 FROM roster r WHERE r.game_pk=ev.game_pk AND r.player_id=ev.pitcher_id AND r.position_code='1') roster_pitcher,
       m.* EXCLUDE(event_id),
       (m.plate_z-m.sz_bot)/nullif(m.sz_top-m.sz_bot,0) plate_z_norm,
       cos(m.spin_axis*pi()/180) spin_cos,sin(m.spin_axis*pi()/180) spin_sin,
       CASE WHEN p_throws='L' THEN 1 WHEN p_throws='R' THEN 0 END throw_left,
       CASE WHEN stand='L' THEN 1 WHEN stand='R' THEN 0 END bat_left
      FROM ev JOIN result p USING(game_pk,at_bat_number) JOIN a USING(appearance_id) LEFT JOIN m USING(event_id)
      WHERE ev.is_pitch""")
    for i,kind in enumerate(['FF','SI','FC','FA','SL','ST','CU','KC','CS','SV','CH','FS','FO','KN','EP','SC']):
        if i==0:c.execute('ALTER TABLE obs ADD COLUMN pitch_type_code INTEGER')
        c.execute('UPDATE obs SET pitch_type_code=? WHERE pitch_type=?',[i,kind])
    counts.update(dict(c.execute("SELECT 'rows',count(*) FROM obs UNION ALL SELECT 'source_valid',count(*) FROM obs WHERE source_valid").fetchall()))
    dest=OUT/f'observations_{year}.parquet'
    c.execute(f"COPY obs TO '{q(dest)}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    save(OUT/f'observations_{year}.json',{'year':year,**counts});c.close()
    print(f'{year}: observations {dict(counts)}',flush=True)

def references()->None:
    c=duckdb.connect(config={'threads':2});path=(OUT/'observations_*.parquet').as_posix()
    c.execute(f"CREATE VIEW obs AS SELECT * EXCLUDE(roster_pitcher) FROM read_parquet('{path}',union_by_name=true)")
    c.execute(f"CREATE VIEW roster AS SELECT * FROM read_parquet('{(BASE/'roster_*.parquet').as_posix()}')")
    c.execute("""CREATE TABLE refs AS WITH ap AS(
      SELECT pitcher_id,appearance_id,pitch_type,greatest(max(closed_at),max(observed_at)) closed_at,count(*) n,
       sum(release_speed) velo,sum(pfx_x) hb,sum(pfx_z) ivb
      FROM obs WHERE pitch_type IN ('FF','SI','FC') AND alignment_status='validated_order'
       AND release_speed IS NOT NULL AND pfx_x IS NOT NULL AND pfx_z IS NOT NULL GROUP BY ALL),
      hist AS(SELECT *,sum(n) OVER w total_n,sum(velo) OVER w total_v,sum(hb) OVER w total_h,sum(ivb) OVER w total_z
       FROM ap WINDOW w AS(PARTITION BY pitcher_id,pitch_type ORDER BY closed_at,appearance_id ROWS UNBOUNDED PRECEDING)),
      entries AS(SELECT DISTINCT pitcher_id,appearance_id,entry_at FROM obs),
      wanted AS(SELECT e.*,t.pitch_type FROM entries e CROSS JOIN (VALUES ('FF'),('SI'),('FC')) t(pitch_type)),
      joined AS(SELECT w.*,h.closed_at reference_closed_at,h.total_n,h.total_v/nullif(h.total_n,0) ref_velo,
        h.total_h/nullif(h.total_n,0) ref_hb,h.total_z/nullif(h.total_n,0) ref_ivb
       FROM wanted w ASOF LEFT JOIN hist h ON w.pitcher_id=h.pitcher_id AND w.pitch_type=h.pitch_type AND w.entry_at>h.closed_at)
      SELECT * FROM joined QUALIFY row_number() OVER(PARTITION BY appearance_id ORDER BY total_n DESC NULLS LAST,pitch_type)=1""")
    assert c.execute('SELECT count(*) FROM refs WHERE reference_closed_at>=entry_at').fetchone()[0]==0
    c.execute(f"COPY refs TO '{(OUT/'prior_fastball_refs.parquet').as_posix()}' (FORMAT PARQUET)")
    for year in range(2021,2027):
        c.execute(f"""COPY(SELECT o.*,r.reference_closed_at,r.total_n prior_fb_n,
         CASE WHEN r.total_n>=20 THEN release_speed-r.ref_velo END prior_velo_delta,
         CASE WHEN r.total_n>=20 THEN pfx_x-r.ref_hb END prior_hb_delta,
         CASE WHEN r.total_n>=20 THEN pfx_z-r.ref_ivb END prior_ivb_delta,
         EXISTS(SELECT 1 FROM roster rr WHERE rr.game_pk=o.game_pk AND rr.player_id=o.pitcher_id AND rr.position_code='1') roster_pitcher
         FROM obs o JOIN refs r USING(appearance_id) WHERE o.year={year})
         TO '{(OUT/f'features_{year}.parquet').as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)""")
        print(f'{year}: strictly prior fastball references exported',flush=True)
    c.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--year',type=int);p.add_argument('--references',action='store_true');args=p.parse_args()
    if args.year:build(args.year)
    if args.references:references()
