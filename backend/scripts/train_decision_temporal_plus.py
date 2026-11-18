"""Slices 6/7: expanding research Plus with training-owned run references and artifacts."""
from __future__ import annotations
import json
from pathlib import Path
import sys
from datetime import datetime,timezone
import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.decision_temporal_common import OUT,ROOT,FOLDS,PHYSICAL,LOCATION,VERSION,protocol,fingerprint,save

def epoch(day:str)->float:return datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()

def run_table(frame:pd.DataFrame)->dict:
    """Count-state RE estimated only from past completed games; count shrinkage to base/out."""
    valid=frame.loc[(frame.remaining_runs>=0)&frame.base_state_before.between(0,7)&frame.outs_before.between(0,2)]
    by=valid.groupby(['outs_before','base_state_before']).remaining_runs.agg(['mean','count'])
    count=valid.groupby(['outs_before','base_state_before','balls_before','strikes_before']).remaining_runs.agg(['sum','count'])
    result={}
    for (o,b),r in by.iterrows():
        for balls in range(4):
            for strikes in range(3):
                k=(o,b,balls,strikes)
                n=float(count.loc[k,'count']) if k in count.index else 0
                total=float(count.loc[k,'sum']) if n else 0
                result[tuple(map(int,k))]=(total+50*float(r['mean']))/(n+50)
    return result

def targets(frame:pd.DataFrame,table:dict)->np.ndarray:
    def get(post:bool)->np.ndarray:
        columns=['post_outs','post_base','post_balls','post_strikes'] if post else ['outs_before','base_state_before','balls_before','strikes_before']
        result=[]
        for o,b,ball,strike in frame[columns].itertuples(index=False,name=None):
            if pd.notna(o) and o>=3:result.append(0.)
            elif all(pd.notna(v) for v in (o,b,ball,strike)):result.append(table.get(tuple(int(v) for v in (o,b,ball,strike)),np.nan))
            else:result.append(np.nan)
        return np.asarray(result)
    return get(False)-frame.runs_on_event.to_numpy()-get(True)

def fit()->None:
    spec=json.loads((OUT/'protocol.json').read_text('utf-8'))
    assert spec==protocol(),'Frozen protocol changed'
    c=duckdb.connect(config={'threads':2})
    c.execute(f"CREATE VIEW f AS SELECT * FROM read_parquet('{(OUT/'features_*.parquet').as_posix()}')")
    metadata=[]
    with threadpool_limits(limits=2):
        for fold in FOLDS:
            cutoff=epoch(fold['train_end']);start=epoch(fold['score_start']);end=epoch(fold['score_end'])
            directory=OUT/'models'/fold['id'];directory.mkdir(parents=True,exist_ok=True)
            print(f"{fold['id']}: reading prior completed games",flush=True)
            history=c.execute('SELECT * FROM f WHERE observed_at<? AND game_completed_at<? AND source_valid AND roster_pitcher AND alignment_status=\'validated_order\' AND role IN (\'SP\',\'RP\')',[cutoff,cutoff]).fetchdf()
            table=run_table(history)
            # Sampling depends on canonical identity, never on a target or pitcher outcome.
            history['sample_hash']=pd.util.hash_pandas_object(history.event_id,index=False).to_numpy()
            history=history.nsmallest(spec['maximum_training_rows'],'sample_hash').copy()
            y=targets(history,table)
            okay=np.isfinite(y)&history.plate_x.notna()&history.plate_z_norm.notna()&history.release_speed.notna()&history.pfx_x.notna()&history.pfx_z.notna()
            history=history.loc[okay];y=y[okay]
            print(f"{fold['id']}: fitting research Location on {len(history):,} pitches",flush=True)
            location=HistGradientBoostingRegressor(**spec['hgb']).fit(history[LOCATION],y)
            loc_pred=location.predict(history[LOCATION])
            print(f"{fold['id']}: fitting research residual Stuff",flush=True)
            stuff=HistGradientBoostingRegressor(**spec['hgb']).fit(history[PHYSICAL],y-loc_pred)
            stuff_pred=stuff.predict(history[PHYSICAL])
            scales={'stuff':{'mean':float(stuff_pred.mean()),'sd':float(stuff_pred.std())},'location':{'mean':float(loc_pred.mean()),'sd':float(loc_pred.std())}}
            assert all(v['sd']>1e-8 for v in scales.values())
            model_id=VERSION+':plus:'+fold['id']
            bundle={'stuff':stuff,'location':location,'scales':scales,'re':table,'model_id':model_id,'train_end':fold['train_end']}
            joblib.dump(bundle,directory/'plus.joblib')
            meta={'model_id':model_id,'fold':fold,'protocol_sha256':fingerprint(spec),'train_rows':len(history),
                  'maximum_training_observed_at':float(history.observed_at.max()),'maximum_label_available_at':float(history.game_completed_at.max()),
                  'features':{'stuff':PHYSICAL,'location':LOCATION},'scales':scales,'method':spec['plus_method'],'formal_replacement':False}
            assert meta['maximum_label_available_at']<cutoff
            if fold['id']=='frozen_2024':
                validation=c.execute("SELECT * FROM f WHERE year=2024 AND source_valid AND roster_pitcher AND alignment_status='validated_order' AND role IN ('SP','RP')").fetchdf()
                truth=targets(validation,table);valid=np.isfinite(truth)&validation.plate_x.notna()&validation.plate_z_norm.notna()&validation.release_speed.notna()&validation.pfx_x.notna()&validation.pfx_z.notna()
                vf=validation.loc[valid];truth=truth[valid]
                lp=location.predict(vf[LOCATION]);sp=stuff.predict(vf[PHYSICAL]);baseline=float(y.mean())
                meta['validation_2024']={'n':len(truth),'mean_rmse':float(np.sqrt(np.mean((truth-baseline)**2))),
                    'location_rmse':float(np.sqrt(np.mean((truth-lp)**2))),'location_plus_residual_stuff_rmse':float(np.sqrt(np.mean((truth-lp-sp)**2))),
                    'scope':'Fixed 2024 diagnostic, no post-diagnostic tuning. No 2025/26 outcome metrics.'}
                del validation,vf
            save(directory/'plus_metadata.json',meta);metadata.append(meta)
            del history
            for year in range(2021,2027):
                if epoch(f'{year+1}-01-01')<=start or epoch(f'{year}-01-01')>=end:continue
                score=c.execute('SELECT * FROM f WHERE year=? AND observed_at>=? AND observed_at<?',[year,start,end]).fetchdf()
                score['research_stuff_plus']=np.nan;score['research_location_plus']=np.nan
                physical=score.source_valid.fillna(False)&score.roster_pitcher&score.alignment_status.eq('validated_order')&score.release_speed.notna()&score.pfx_x.notna()&score.pfx_z.notna()&score.pitch_type_code.notna()
                positional=score.source_valid.fillna(False)&score.roster_pitcher&score.alignment_status.eq('validated_order')&score.plate_x.notna()&score.plate_z_norm.between(-2,4)&score.pitch_type_code.notna()
                for key,valid,cols,model in [('stuff',physical,PHYSICAL,stuff),('location',positional,LOCATION,location)]:
                    scale=scales[key]
                    score.loc[valid,f'research_{key}_plus']=100+10*(model.predict(score.loc[valid,cols])-scale['mean'])/scale['sd']
                score['plus_model_id']=model_id;score['plus_train_cutoff']=cutoff
                assert (score.observed_at>=cutoff).all()
                score.to_parquet(OUT/f'scored_{year}_{fold["id"]}.parquet',index=False,compression='zstd')
                print(f"{fold['id']}: {year} scored {len(score):,}, Stuff {int(physical.sum()):,}, Location {int(positional.sum()):,}",flush=True)
    summary=[]
    for year in range(2021,2027):
        total=c.execute('SELECT count(*) FROM f WHERE year=?',[year]).fetchone()[0]
        row=c.execute(f"SELECT count(*),count(research_stuff_plus),count(research_location_plus),median(research_stuff_plus),median(research_location_plus) FROM read_parquet('{(OUT/f'scored_{year}_*.parquet').as_posix()}')").fetchone()
        summary.append(dict(zip(['year','physical_pitches','scored_window','stuff_available','location_available','stuff_median','location_median'],[year,total,*row])))
    save(ROOT/'sample/petehub_pitcher_decision_slice7_v1.json',{'slice':7,'version':VERSION,'years':summary,'models':metadata,'formal_replacement':False,'method':spec['plus_method'],'holdout_policy':spec['holdout_policy']})
    stage6=json.loads((ROOT/'sample/petehub_pitcher_decision_slice6_v1.json').read_text('utf-8'));stage6.update({'status':'implemented_and_checked','prior_reference_time_violations':0,'alignment':[json.loads((OUT/f'observations_{y}.json').read_text('utf-8')) for y in range(2021,2027)]});save(ROOT/'sample/petehub_pitcher_decision_slice6_v1.json',stage6)

if __name__=='__main__':fit()
