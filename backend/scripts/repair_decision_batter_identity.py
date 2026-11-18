"""Repair only batter IDs affected by pinch-runner parsing, with a field-level audit."""
from pathlib import Path
import gzip
import hashlib
import json
import sys
import duckdb
import pandas as pd
import pyarrow.parquet as pq
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.pitcher_decision_ledger import parse_game
from app.services.decision_temporal_common import BASE,ROOT,OUT,save

def run():
    c=duckdb.connect(config={'threads':2});audit=[]
    existing=OUT/'batter_identity_repair.json'
    if existing.exists():
        # Re-running must verify the completed repair, never replace its original
        # field-level evidence with an empty "nothing changed" report.
        saved=json.loads(existing.read_text('utf-8'))
        for row in saved['years']:
            year=row['year']
            for name,key in [('events','event_id'),('decisions','decision_id')]:
                changes=OUT/f'batter_identity_changes_{name}_{year}.parquet';target=BASE/f'{name}_{year}.parquet'
                bad=c.execute(f"SELECT count(*) FROM read_parquet('{changes.as_posix()}') f LEFT JOIN read_parquet('{target.as_posix()}') e USING({key}) WHERE e.{key} IS NULL OR e.batter_id IS DISTINCT FROM f.correct_batter_id").fetchone()[0]
                assert bad==0,f'Previously repaired identities changed: {year} {name}'
        print('Existing batter-identity repair verified; original backups and audit preserved.',flush=True)
        return
    for year in range(2021,2027):
        games=[r[0] for r in c.execute("SELECT DISTINCT game_pk FROM read_parquet(?) WHERE batter<>batter_id",[str(OUT/f'features_{year}.parquet')]).fetchall()]
        efix=[];dfix=[]
        inventory={r['game_pk']:r for r in pq.read_table(ROOT/f'research/decision_support_slice1_20261112/feed_inventory_{year}.parquet').to_pylist()}
        for i,pk in enumerate(games,1):
            entry=inventory[pk];packed=Path(entry['path']).read_bytes();assert hashlib.sha256(packed).hexdigest()==entry['compressed_sha256']
            rows=parse_game(year,json.loads(gzip.decompress(packed)))
            efix.extend({'event_id':r['event_id'],'correct_batter_id':r['batter_id']} for r in rows['events'])
            dfix.extend({'decision_id':r['decision_id'],'correct_batter_id':r['batter_id']} for r in rows['decisions'])
            if i%100==0:print(f'{year}: identity review {i}/{len(games)} games',flush=True)
        changes={}
        for name,fix,key in [('events',efix,'event_id'),('decisions',dfix,'decision_id')]:
            if not fix:continue
            target=BASE/f'{name}_{year}.parquet';original=c.execute('SELECT * FROM read_parquet(?)',[str(target)]).fetchdf()
            patched=original.merge(pd.DataFrame(fix),on=key,how='left',validate='one_to_one')
            changed=patched.correct_batter_id.notna()&(patched.batter_id!=patched.correct_batter_id)
            evidence=patched.loc[changed,[key,'batter_id','correct_batter_id']]
            evidence.to_parquet(OUT/f'batter_identity_changes_{name}_{year}.parquet',index=False)
            patched['batter_id']=patched.correct_batter_id.fillna(patched.batter_id).astype('Int64');patched=patched[original.columns]
            assert original.drop(columns='batter_id').equals(patched.drop(columns='batter_id'))
            backup=OUT/f'before_identity_{name}_{year}.parquet'
            if not backup.exists():backup.write_bytes(target.read_bytes())
            patched.to_parquet(target.with_suffix('.tmp.parquet'),index=False,compression='zstd');target.with_suffix('.tmp.parquet').replace(target)
            changes[name]=len(evidence)
        # Copy the corrected identity into research observations without changing model inputs/scores.
        c.execute(f"CREATE OR REPLACE VIEW corrected AS SELECT event_id,batter_id FROM read_parquet('{(BASE/f'events_{year}.parquet').as_posix()}')")
        for target in [OUT/f'observations_{year}.parquet',OUT/f'features_{year}.parquet',*OUT.glob(f'scored_{year}_*.parquet')]:
            temporary=target.with_suffix('.identity.tmp')
            c.execute(f"COPY(SELECT x.* REPLACE(e.batter_id AS batter_id) FROM read_parquet('{target.as_posix()}') x JOIN corrected e USING(event_id)) TO '{temporary.as_posix()}' (FORMAT PARQUET,COMPRESSION ZSTD)")
            temporary.replace(target)
        remaining=c.execute('SELECT count(*) FROM read_parquet(?) WHERE batter<>batter_id',[str(OUT/f'features_{year}.parquet')]).fetchone()[0]
        audit.append({'year':year,'reviewed_games':len(games),'changed':changes,'remaining_source_batter_disagreements':remaining})
        print(f'{year}: identity corrections {changes}, remaining source disagreements {remaining}',flush=True)
    save(OUT/'batter_identity_repair.json',{'reason':'Pinch-runner offensive substitution was incorrectly treated as batter substitution.','only_changed_field':'batter_id',
      'pitcher_and_time_and_count_unchanged':True,'model_features_unchanged':True,'years':audit})

if __name__=='__main__':run()
