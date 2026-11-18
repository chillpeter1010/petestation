"""Slice 10: past-only WE / RE24 / PA-LI reference, independent of action evaluation."""
from __future__ import annotations
from pathlib import Path
import sys
import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss,log_loss
from threadpoolctl import threadpool_limits
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.decision_temporal_common import BASE,OUT,ROOT,FOLDS,VERSION,save
from scripts.train_decision_temporal_plus import epoch

COLS=['inning','bottom','scheduled_innings','score_diff','outs','base_state','balls','strikes']

def re_fit(train:pd.DataFrame)->dict:
    base=train.groupby(['outs','base_state']).remaining_runs.agg(['mean','std','count'])
    detailed=train.groupby(['outs','base_state','extra']).remaining_runs.agg(['sum','std','count'])
    table={}
    for (o,b),r in base.iterrows():
        for extra in [0,1]:
            k=(o,b,extra);n=int(detailed.loc[k,'count']) if k in detailed.index else 0
            total=float(detailed.loc[k,'sum']) if n else 0
            sd=float(detailed.loc[k,'std']) if n>1 else float(r['std'])
            table[tuple(map(int,k))]={'mean':(total+50*float(r['mean']))/(n+50),'n':n,'base_n':int(r['count']),
              'se':sd/np.sqrt(max(n,1)) if np.isfinite(sd) else None,'backoff':n<30}
    return table

def re_get(frame:pd.DataFrame,table:dict)->list[dict|None]:
    result=[]
    for o,b,e in frame[['outs','base_state','extra']].itertuples(index=False,name=None):
        if pd.notna(o) and o>=3:result.append({'mean':0.,'n':None,'se':0.,'backoff':False})
        elif all(pd.notna(v) for v in (o,b,e)):result.append(table.get((int(o),int(b),int(e))))
        else:result.append(None)
    return result

def we_predict(bundle:dict,frame:pd.DataFrame)->np.ndarray:
    raw=bundle['we'].decision_function(frame[COLS]);return bundle['calibration'].predict_proba(raw.reshape(-1,1))[:,1]

def post_state(frame:pd.DataFrame,runs:np.ndarray,outs:np.ndarray,bases:np.ndarray)->tuple[pd.DataFrame,np.ndarray]:
    post=frame[COLS].copy();diff=post.score_diff.to_numpy()+np.where(post.bottom.to_numpy()==1,runs,-runs)
    inning=post.inning.to_numpy();bottom=post.bottom.to_numpy();scheduled=post.scheduled_innings.to_numpy()
    terminal=np.full(len(frame),np.nan)
    terminal[(inning>=scheduled)&(bottom==1)&(diff>0)]=1.
    terminal[(inning>=scheduled)&(bottom==0)&(outs>=3)&(diff>0)]=1.
    over=(inning>=scheduled)&(bottom==1)&(outs>=3)&(diff!=0)
    terminal[over]=(diff[over]>0).astype(float)
    change=outs>=3;newinning=inning+((bottom==1)&change)
    newbottom=np.where(change,1-bottom,bottom)
    post['inning']=newinning;post['bottom']=newbottom;post['score_diff']=diff
    post['outs']=np.where(change,0,outs)
    post['base_state']=np.where(change,np.where(newinning>scheduled,2,0),bases)
    post['balls']=0;post['strikes']=0
    return post,terminal

def transition_fit(train:pd.DataFrame)->dict:
    valid=train[train.completed_batter_play&train.post_outs.between(0,3)&train.post_base.between(0,7)&train.runs.between(0,4)].copy()
    result={}
    for key,group in valid.groupby(['outs','base_state','extra']):
        chosen=group;backoff=False
        if len(group)<30:chosen=valid[(valid.outs==key[0])&(valid.base_state==key[1])];backoff=True
        distribution=chosen.groupby(['runs','post_outs','post_base']).size()
        result[tuple(map(int,key))]={'n':len(chosen),'backoff':backoff,
            'events':[(int(r),int(o),int(b),float(n/len(chosen))) for (r,o,b),n in distribution.items()]}
    return result

def expected_swing(bundle:dict,frame:pd.DataFrame)->tuple[np.ndarray,np.ndarray,np.ndarray]:
    output=np.full(len(frame),np.nan);support=np.zeros(len(frame),dtype=int);backoff=np.zeros(len(frame),dtype=bool)
    keys=frame[['outs','base_state','extra']]
    base_we=we_predict(bundle,frame)
    for key,indices in keys.groupby(['outs','base_state','extra']).groups.items():
        trans=bundle['transitions'].get(tuple(map(int,key)))
        if trans is None or trans['n']<30:continue
        idx=frame.index.get_indexer(indices);subset=frame.loc[indices];swing=np.zeros(len(subset))
        # All alternatives originate from prior reference transitions, not this game's realized outcome.
        for runs,outs,bases,p in trans['events']:
            post,terminal=post_state(subset,np.full(len(subset),runs),np.full(len(subset),outs),np.full(len(subset),bases))
            future=we_predict(bundle,post);known=np.isfinite(terminal);future[known]=terminal[known]
            swing+=p*np.abs(future-base_we[idx])
        output[idx]=swing;support[idx]=trans['n'];backoff[idx]=trans['backoff']
    return output,support,backoff

def build_frame(c:duckdb.DuckDBPyConnection)->None:
    c.execute(f"CREATE VIEW d AS SELECT * FROM read_parquet('{(BASE/'decisions_*.parquet').as_posix()}')")
    c.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{(BASE/'plays_*.parquet').as_posix()}')")
    c.execute(f"CREATE VIEW w AS SELECT decision_id,source_clock_valid FROM read_parquet('{(BASE/'workload_20*.parquet').as_posix()}')")
    c.execute("""CREATE TABLE context AS WITH results AS(SELECT *,
      max(CASE WHEN half='top' THEN away_score_after ELSE home_score_after END) OVER(PARTITION BY game_pk,inning,half) half_final,
      arg_max(home_score_after,at_bat_number) OVER(PARTITION BY game_pk) final_h,
      arg_max(away_score_after,at_bat_number) OVER(PARTITION BY game_pk) final_a,
      max(epoch(try_cast(end_time AS TIMESTAMPTZ))) OVER(PARTITION BY game_pk) game_completed_at FROM p)
      SELECT d.year,d.game_pk,d.decision_id,d.outcome_key,epoch(try_cast(d.decision_time AS TIMESTAMPTZ)) decision_at,
       p.game_completed_at,d.inning,CASE WHEN d.half='bottom' THEN 1 ELSE 0 END bottom,p.scheduled_innings,
       d.home_score-d.away_score score_diff,d.outs,d.base_state,d.balls,d.strikes,
       CASE WHEN d.inning>p.scheduled_innings THEN 1 ELSE 0 END extra,
       d.base_state_known AND w.source_clock_valid AND d.time_basis<>'play_start_fallback' source_valid,
       p.half_final-CASE WHEN d.half='top' THEN d.away_score ELSE d.home_score END remaining_runs,
       CASE WHEN p.final_h>p.final_a THEN 1 WHEN p.final_h<p.final_a THEN 0 END home_win,
       CASE WHEN d.half='top' THEN p.away_score_after-d.away_score ELSE p.home_score_after-d.home_score END runs,
       p.outs_after post_outs,p.base_state_after post_base,d.completed_batter_play,
       p.is_complete,p.runner_index_missing
      FROM d JOIN results p USING(outcome_key) JOIN w USING(decision_id)""")

def run()->None:
    c=duckdb.connect(config={'threads':2,'memory_limit':'2GB'});build_frame(c);metas=[];coverage=[]
    with threadpool_limits(limits=2):
        for fold in FOLDS:
            cutoff=epoch(fold['train_end']);print(f"{fold['id']}: context prior-reference fit",flush=True)
            train=c.execute('SELECT * FROM context WHERE decision_at<? AND game_completed_at<? AND source_valid AND is_complete AND NOT runner_index_missing AND home_win IS NOT NULL AND remaining_runs>=0 AND outs BETWEEN 0 AND 2 AND base_state BETWEEN 0 AND 7',[cutoff,cutoff]).fetchdf()
            games=train[['game_pk','game_completed_at']].drop_duplicates().sort_values(['game_completed_at','game_pk'])
            fit_games=set(games.iloc[:int(.8*len(games))].game_pk);fit=train[train.game_pk.isin(fit_games)];cal=train[~train.game_pk.isin(fit_games)]
            model=HistGradientBoostingClassifier(max_iter=90,max_leaf_nodes=15,learning_rate=.08,min_samples_leaf=80,
                l2_regularization=10,max_bins=128,early_stopping=False,random_state=20261114)
            weights=1/fit.groupby('game_pk').decision_id.transform('count').to_numpy()
            model.fit(fit[COLS],fit.home_win.astype(int),sample_weight=weights)
            calibration=LogisticRegression(C=1.,random_state=20261114)
            calibration.fit(model.decision_function(cal[COLS]).reshape(-1,1),cal.home_win.astype(int),
                sample_weight=1/cal.groupby('game_pk').decision_id.transform('count').to_numpy())
            bundle={'we':model,'calibration':calibration,'re':re_fit(train),'transitions':transition_fit(train),'model_id':VERSION+':context:'+fold['id']}
            # Fixed pooled per-PA training reference; no current-season WPA normalization.
            unique=train[COLS+['extra']].drop_duplicates().reset_index(drop=True)
            print(f"{fold['id']}: expected prior PA swing, {len(unique):,} unique reference states",flush=True)
            swing,n,backoff=expected_swing(bundle,unique);unique['swing']=swing
            joined=train.merge(unique,on=COLS+['extra'],how='left');normalizer=float(joined.swing.mean())
            assert normalizer>0;bundle['li_normalizer']=normalizer
            directory=OUT/'models'/fold['id'];directory.mkdir(parents=True,exist_ok=True);joblib.dump(bundle,directory/'context.joblib')
            meta={'model_id':bundle['model_id'],'fold':fold,'reference_games':len(games),'fit_games':len(fit_games),'calibration_games':len(games)-len(fit_games),
              'reference_rows':len(train),'maximum_label_available_at':float(train.game_completed_at.max()),'we_features':COLS,
              're_states':len(bundle['re']),'li_normalizer':normalizer,'li_scope':'Research PA-LI: expected absolute neutral-WE swing over completed batter transitions; not an exact FanGraphs LI reproduction.',
              'we_calibration':'Chronological 80/20 game split, fixed Platt logistic; no held-out-year calibration.',
              'limitations':['No team-strength, park, roster or forthcoming action effects in neutral WE.','Partial-pooling RE sampling SE omits model and clustering uncertainty.',
                  'Walkoffs and seven-inning termination explicit; extra innings use automatic runner at second.','LI does not include bullpen opportunity cost or recommend an action.'],
              'formal_replacement':False}
            assert meta['maximum_label_available_at']<cutoff
            for year in range(2021,2027):
                if epoch(f'{year+1}-01-01')<=epoch(fold['score_start']) or epoch(f'{year}-01-01')>=epoch(fold['score_end']):continue
                score=c.execute('SELECT * FROM context WHERE year=? AND decision_at>=? AND decision_at<?',[year,epoch(fold['score_start']),epoch(fold['score_end'])]).fetchdf()
                known=score.source_valid.fillna(False)&score.outs.between(0,2)&score.base_state.between(0,7)
                # Unknown states remain unavailable; HGB's missing-value support is not a state-repair policy.
                valid=score.loc[known].copy();unique=valid[COLS+['extra']].drop_duplicates().reset_index(drop=True)
                swing,support,backoff=expected_swing(bundle,unique)
                unique['research_pa_li']=swing/normalizer;unique['li_reference_n']=support;unique['li_backoff']=backoff
                valid=valid.merge(unique,on=COLS+['extra'],how='left');valid['research_home_we']=we_predict(bundle,valid)
                re_rows=re_get(valid,bundle['re']);valid['research_re']= [r['mean'] if r else np.nan for r in re_rows]
                valid['re_reference_n']=[r['n'] if r else 0 for r in re_rows];valid['re_sampling_se']=[r['se'] if r else np.nan for r in re_rows]
                valid['re_backoff']=[r['backoff'] if r else True for r in re_rows]
                # Realized labels are separate files; these never enter predecision context outputs.
                post,terminal=post_state(valid,valid.runs.to_numpy(),valid.post_outs.to_numpy(),valid.post_base.to_numpy())
                future=we_predict(bundle,post);terminal_valid=np.isfinite(terminal);future[terminal_valid]=terminal[terminal_valid]
                label=valid[['decision_id','outcome_key','game_pk','game_completed_at']].copy()
                label['modeled_home_wpa']=future-valid.research_home_we.to_numpy()
                re_post=pd.DataFrame({'outs':valid.post_outs,'base_state':valid.post_base,'extra':valid.extra})
                postre=np.asarray([r['mean'] if r else np.nan for r in re_get(re_post,bundle['re'])])
                label['modeled_defense_re24']=valid.research_re.to_numpy()-valid.runs.to_numpy()-postre
                label['context_model_id']=bundle['model_id'];label['label_scope']='next recorded play; not causal substitution attribution'
                label.to_parquet(OUT/f'context_labels_{year}.parquet',index=False,compression='zstd')
                feature_cols=['decision_id','research_home_we','research_re','re_reference_n','re_sampling_se','re_backoff','research_pa_li','li_reference_n','li_backoff']
                result=score[['year','game_pk','decision_id','decision_at']].merge(valid[feature_cols],on='decision_id',how='left')
                result['context_model_id']=bundle['model_id'];result['context_train_cutoff']=cutoff
                result['status']=np.where(result.research_home_we.isna(),'unknown_or_unsafe_source','available')
                result.to_parquet(OUT/f'context_features_{year}.parquet',index=False,compression='zstd')
                full=c.execute('SELECT count(*) FROM context WHERE year=?',[year]).fetchone()[0]
                coverage.append({'year':year,'decisions':full,'scored_window':len(result),'we':int(result.research_home_we.notna().sum()),'re':int(result.research_re.notna().sum()),'li':int(result.research_pa_li.notna().sum())})
                print(f'{year}: context coverage WE {coverage[-1]["we"]:,}, RE {coverage[-1]["re"]:,}, PA-LI {coverage[-1]["li"]:,}',flush=True)
                if year==2024:
                    check=valid[valid.home_win.notna()];pred=check.research_home_we.to_numpy();truth=check.home_win.astype(int).to_numpy()
                    bins=[]
                    for left in np.arange(0,1,.1):
                        mask=(pred>=left)&(pred<left+.1)
                        if mask.any():bins.append({'lower':round(float(left),1),'n':int(mask.sum()),'predicted':float(pred[mask].mean()),'observed':float(truth[mask].mean())})
                    meta['validation_2024']={'n':len(check),'brier':float(brier_score_loss(truth,pred)),'log_loss':float(log_loss(truth,pred)),
                        'constant_train_home_win_brier':float(brier_score_loss(truth,np.full(len(truth),train.home_win.mean()))),'calibration_bins':bins,
                        'scope':'Fixed validation diagnostic; observations clustered by game, not independent rows. No 2025/2026 performance examination.'}
            save(directory/'context_metadata.json',meta);metas.append(meta)
    save(ROOT/'sample/petehub_pitcher_decision_slice10_v1.json',{'slice':10,'version':VERSION,'years':coverage,'models':metas,
      'missing_li_filled_with_one':False,'outcomes_separate':True,'xwpa_action_model_trained':False,'individual_ranking_allowed':False})

if __name__=='__main__':run()
