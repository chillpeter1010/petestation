"""Slice 13: actor-aligned signal ablations; frozen 2025 outcomes stay closed."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import warnings

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_baselines as b

OUT = b.ROOT / 'data/research/decision_ablation_v1'
SIGNALS = ['quality', 'physical', 'command']
PLUS = ['option_stuff', 'option_location']
SUPPORT_NUM = ['state_reliability', 'state_age_hours', 'option_stuff_n', 'option_location_n', 'plus_age_hours']
SUPPORT_CAT = ['state_scope', 'state_status', 'plus_support']
VARIANTS = {
    'baseline': [], 'plus': PLUS, 'quality': ['quality'], 'physical': ['physical'], 'command': ['command'],
    'three_signals': SIGNALS, 'all': PLUS + SIGNALS,
    'without_quality': PLUS + ['physical', 'command'],
    'without_physical': PLUS + ['quality', 'command'],
    'without_command': PLUS + ['quality', 'physical'],
}


def features() -> None:
    with b.connection() as c:
        path = (b.TEMPORAL / 'scored_20*.parquet').as_posix()
        c.execute(f"""CREATE TABLE closed_plus AS SELECT pitcher_id,appearance_id,plus_model_id,
            greatest(max(closed_at),max(observed_at)) available_at,max(plus_train_cutoff) train_cutoff,
            avg(research_stuff_plus) stuff_mean,avg(research_location_plus) location_mean,
            count(research_stuff_plus) stuff_n,count(research_location_plus) location_n
            FROM read_parquet('{path}') WHERE source_valid AND roster_pitcher AND alignment_status='validated_order'
            GROUP BY ALL""")
        c.table('closed_plus').write_parquet(str(OUT/'closed_plus.parquet'), compression='zstd')
        for year in b.YEARS:
            for name, path in [('f', b.OUT/f'observed_features_{year}.parquet'),
                               ('s', b.PREP/f'signal_features_{year}.parquet')]:
                c.read_parquet(str(path)).create_view(name, replace=True)
            cases = ' '.join(f"WHEN f.decision_at>={pd.Timestamp(fold['score_start'],tz='UTC').timestamp()} AND f.decision_at<{pd.Timestamp(fold['score_end'],tz='UTC').timestamp()} THEN 'decision_temporal_research_v1:plus:{fold['id']}'" for fold in b.FOLDS)
            c.execute(f"""CREATE OR REPLACE TABLE requests AS SELECT f.* EXCLUDE(observed_action),
                CASE {cases} END AS wanted_model,s.prior_prefix_stuff,s.prior_prefix_location,
                s.stuff_n,s.location_n,s.plus_observed_at,s.plus_train_cutoff
                FROM f JOIN s USING(decision_id)""")
            c.execute("""CREATE OR REPLACE TABLE enhanced AS SELECT q.* EXCLUDE(wanted_model,prior_prefix_stuff,
                prior_prefix_location,stuff_n,location_n,plus_observed_at,plus_train_cutoff),
                CASE WHEN is_current THEN prior_prefix_stuff ELSE p.stuff_mean END option_stuff,
                CASE WHEN is_current THEN prior_prefix_location ELSE p.location_mean END option_location,
                CASE WHEN is_current THEN q.stuff_n ELSE p.stuff_n END option_stuff_n,
                CASE WHEN is_current THEN q.location_n ELSE p.location_n END option_location_n,
                CASE WHEN is_current THEN plus_observed_at ELSE p.available_at END option_plus_at,
                CASE WHEN is_current THEN plus_train_cutoff ELSE p.train_cutoff END option_plus_cutoff,
                CASE WHEN is_current THEN 'observed_current_prefix' ELSE 'last_closed_appearance_not_readiness' END plus_scope
                FROM requests q ASOF LEFT JOIN closed_plus p ON q.option_pitcher_id=p.pitcher_id
                    AND q.wanted_model=p.plus_model_id AND q.decision_at>p.available_at""")
            bad = c.execute('SELECT count(*) FROM enhanced WHERE option_plus_at>=decision_at OR option_plus_cutoff>option_plus_at OR state_available_at>=decision_at').fetchone()[0]
            assert bad == 0
            frame = c.table('enhanced').fetchdf()
            frame['state_age_hours'] = (frame.decision_at-frame.state_available_at)/3600
            frame['plus_age_hours'] = (frame.decision_at-frame.option_plus_at)/3600
            frame['plus_support'] = np.where(frame[PLUS].notna().all(axis=1), 'both', 'partial_or_unavailable')
            frame['complete_support'] = frame[PLUS+SIGNALS].notna().all(axis=1)
            frame.to_parquet(OUT/f'features_{year}.parquet', index=False, compression='zstd')
            print(f'{year}: actor-aligned signals {int(frame.complete_support.sum()):,}/{len(frame):,}; time violations={bad}', flush=True)


def protocol() -> dict:
    paths = [Path(__file__), Path(b.__file__), b.OUT/'protocol.json', b.OUT/'matchup.joblib', OUT/'closed_plus.parquet']
    paths += [OUT/f'features_{year}.parquet' for year in b.YEARS]
    return {'version':'decision_ablation_v1', 'input_sha256':{str(p.relative_to(b.ROOT)):b.digest(p) for p in paths},
        'split':{'train':[2021,2022,2023], 'selection_and_diagnostics':[2024], 'locked_test':[2025], 'score_only':[2026]},
        'variants':VARIANTS, 'support_numeric':SUPPORT_NUM, 'support_categorical':SUPPORT_CAT,
        'settings':{'alpha':.001,'ability_pooling':20,'learner':b.LEARNER},
        'cohorts':'complete-case common training and validation denominators for all 10 variants; additional full-cohort missing-aware baseline/all comparison',
        'support_control':'same support age/n/reliability/scope in every baseline; incremental scores cannot win merely by exposing missingness',
        'actor_alignment':'current prefix only for actual continuation; actual incoming option uses past closed state/Plus; never outgoing signals for incoming outcome',
        'gate':'log-loss paired game-cluster 95% upper bound < 0 and Brier lower; no >=500-PA role/current subgroup log-loss harm >0.005; no convergence warning; full-cohort replication required for general-use promotion',
        'uncertainty':'100 paired game-cluster bootstrap replicates; 2024 selection diagnostics are not independent confirmation',
        'baseline_reference':'frozen Slice12 full-cohort matchup remains separately reported; all ablation comparisons refit on their identical cohort',
        'constraints':'no 2025/2026 outcome metrics, individual ranking, causality or formal model replacement'}


def freeze() -> None:
    path=OUT/'protocol.json'; value=protocol()
    if path.exists() and json.loads(path.read_text('utf-8'))!=value:
        raise ValueError('Frozen ablation protocol changed; create a new explicit version')
    b.save_json(path,value)
    print('Slice13 protocol frozen',flush=True)


def load(year: int, labels: bool) -> pd.DataFrame:
    with b.connection() as c:
        c.read_parquet(str(OUT/f'features_{year}.parquet')).create_view('f')
        if not labels:return c.table('f').fetchdf()
        c.read_parquet(str(b.PREP/f'clean_labels_{year}.parquet')).create_view('l')
        frame=c.execute('''SELECT f.*,l.observed_pa_result,l.runs_to_pa_end,l.outs_after,
            CASE WHEN l.outs_after=3 THEN 0 ELSE l.base_state_after END post_base,l.pa_end_at
            FROM f JOIN l USING(decision_id) WHERE l.organic_pa_eligible''').fetchdf()
    return b.clean_model_frame(frame)[0]


def design(frame: pd.DataFrame, variant: str, prior: np.ndarray) -> pd.DataFrame:
    x=b.design(frame,'matchup',20,prior)
    for name in SUPPORT_NUM+VARIANTS[variant]:x[name]=pd.to_numeric(frame[name],errors='coerce').replace([np.inf,-np.inf],np.nan)
    for name in SUPPORT_CAT:x[name]=frame[name].astype('string').fillna('unknown').astype(str)
    return x


def make_model(variant: str):
    numeric=b.LEVELS['matchup'][0]+SUPPORT_NUM+VARIANTS[variant]
    categorical=b.LEVELS['matchup'][1]+SUPPORT_CAT
    transform=ColumnTransformer([
        ('numeric',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True,add_indicator=True),StandardScaler()),numeric),
        ('categorical',OneHotEncoder(handle_unknown='ignore',sparse_output=False),categorical)])
    return make_pipeline(transform,SGDClassifier(alpha=.001,**b.LEARNER))


def compare(frame: pd.DataFrame, p: np.ndarray, base: np.ndarray) -> dict:
    y=frame.target.to_numpy();idx=np.arange(len(y))
    cluster=b.cluster_difference(frame,-np.log(base[idx,y]),-np.log(p[idx,y]))
    subgroups=[]
    for key, group in frame.groupby(['outgoing_role','is_current']):
        indices=group.index.to_numpy();yp=y[indices]
        subgroups.append({'role':key[0],'is_current':bool(key[1]),'n':len(indices),
            'log_loss_delta':float((-np.log(p[indices,yp])+np.log(base[indices,yp])).mean())})
    value=b.metrics(y,p); base_value=b.metrics(y,base)
    harm=any(g['n']>=500 and g['log_loss_delta']>.005 for g in subgroups)
    return {'metrics':value,'cluster_delta':cluster,'brier_delta':value['brier']-base_value['brier'],
        'subgroups':subgroups,'increment_gate':bool(cluster['game_cluster_95pct'][1]<0 and value['brier']<base_value['brier'] and not harm)}


def train() -> None:
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    frames=[load(year,True) for year in (2021,2022,2023,2024)]
    development=pd.concat(frames[:3],ignore_index=True); validation=frames[3]
    assert development.pa_end_at.max()<pd.Timestamp('2024-01-01',tz='UTC').timestamp()
    report={'version':'decision_ablation_v1','protocol_sha256':b.digest(OUT/'protocol.json'),
            'coverage':[{'year':2021+i,'n':len(f),'complete':int(f.complete_support.sum())} for i,f in enumerate(frames)],
            'cohorts':{},'test_outcome_metrics_examined':False,'formal_promotion':False}
    with threadpool_limits(limits=2):
        for cohort in ('complete','missing_aware'):
            train=development[development.complete_support].copy() if cohort=='complete' else development.copy()
            valid=validation[validation.complete_support].copy() if cohort=='complete' else validation.copy()
            train.reset_index(drop=True,inplace=True);valid.reset_index(drop=True,inplace=True)
            prior=np.bincount(train.target,minlength=9)/len(train)
            weights=1/train.groupby('game_pk').decision_id.transform('count').to_numpy();weights/=weights.mean()
            baseline=None;results={}
            for variant in VARIANTS if cohort=='complete' else ('baseline','all'):
                print(f'{cohort}/{variant}: fitting {len(train):,}, validating {len(valid):,}',flush=True)
                model=make_model(variant)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always',ConvergenceWarning)
                    model.fit(design(train,variant,prior),train.target,sgdclassifier__sample_weight=weights)
                p=b.probabilities(model,design(valid,variant,prior))
                if baseline is None:baseline=p.copy()
                result=compare(valid,p,baseline)
                result['convergence_warning']=any(isinstance(w.message,ConvergenceWarning) for w in caught)
                if result['convergence_warning']:result['increment_gate']=False
                results[variant]=result
                joblib.dump({'model':model,'variant':variant,'prior':prior},OUT/f'{cohort}_{variant}.joblib')
                out=valid[['decision_id','game_pk','outgoing_role','is_current']].copy()
                for j,key in enumerate(b.OUTCOMES):out[f'p_{key}']=p[:,j]
                out.to_parquet(OUT/f'validation_{cohort}_{variant}.parquet',index=False,compression='zstd')
                print(f"{cohort}/{variant}: LL={result['metrics']['log_loss']:.6f}, Brier={result['metrics']['brier']:.6f}, increment_gate={result['increment_gate']}",flush=True)
            report['cohorts'][cohort]={'training_n':len(train),'validation_n':len(valid),'results':results}
    complete=report['cohorts']['complete']['results']
    supported=[key for key,r in complete.items() if key!='baseline' and r['increment_gate']]
    report['supported_subset_winner']=min(supported,key=lambda key:complete[key]['metrics']['log_loss']) if supported else 'baseline'
    broad=report['cohorts']['missing_aware']['results']['all']
    report['general_use_increment_supported']=bool(complete['all']['increment_gate'] and broad['increment_gate'])
    report['action_model']='Slice12 matchup baseline; signal trajectories/entry readiness are not projected into hypothetical future pitches'
    b.save_json(OUT/'validation.json',report)


def score() -> None:
    winner=json.loads((OUT/'validation.json').read_text('utf-8'))['supported_subset_winner']
    bundle=joblib.load(OUT/f'complete_{winner}.joblib')
    broad=joblib.load(OUT/'missing_aware_all.joblib')
    with threadpool_limits(limits=2):
        for year in (2025,2026):
            frame=load(year,False)
            out=frame[['decision_id','game_pk','complete_support']].copy()
            for name,fit,mask in [('supported_subset',bundle,frame.complete_support),('missing_aware_all',broad,np.ones(len(frame),dtype=bool))]:
                p=b.probabilities(fit['model'],design(frame.loc[mask],fit['variant'],fit['prior']))
                for j,key in enumerate(b.OUTCOMES):out.loc[mask,f'{name}_p_{key}']=p[:,j]
            out.to_parquet(OUT/f'predictions_{year}.parquet',index=False,compression='zstd')
            print(f'{year}: Slice13 frozen predictions only, no outcome metrics',flush=True)


def finalize() -> None:
    report=json.loads((OUT/'validation.json').read_text('utf-8'))
    b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_slice13_v1.json',report)
    files=[{'path':p.name,'bytes':p.stat().st_size,'sha256':b.digest(p)} for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='manifest.json']
    b.save_json(OUT/'manifest.json',{'version':'decision_ablation_v1','files':files})
    print(f'Slice13 evidence: {len(files)} hashes',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['features','freeze','train','score','finalize'])
    stage=parser.parse_args().stage;OUT.mkdir(parents=True,exist_ok=True)
    globals()[stage]()
