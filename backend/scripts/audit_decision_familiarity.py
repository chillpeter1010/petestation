"""Explicit diagnostic revision: intersect frozen curves with identity-clean PA rows.

The13.5 attack features and13.6 model inputs are unchanged. Original descriptive
outputs remain available; this independently frozen diagnostic supersedes them.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler,SplineTransformer
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_batter_matchups as h

b,m=h.b,h.m
OUT=h.OUT/'familiarity_identity_clean_v2'


def protocol():
    paths=[Path(__file__),Path(h.__file__),Path(m.__file__),h.OUT/'protocol.json']
    paths += [folder/f'{name}_{y}.parquet' for y in range(2021,2025) for folder,name in [(h.OUT,'pa_stats'),(h.r.OUT,'curve_cohort')]]
    return {'version':'familiarity_identity_clean_v2','input_sha256':{str(p.relative_to(b.ROOT)):b.digest(p) for p in paths},
        'train':[2021,2022,2023],'validation':[2024],
        'eligibility':'inner intersection of frozen actual-actor curve cohort and identity-clean fully completed PA stats; exclude incomplete/complex/multiple-batter or conflicting identities before diagnostic nuisance fit',
        'models':'same predeclared13.5 Ridge100, count spline4knots/degree2, same control list, game x pitcher bootstrap200; no new threshold/feature/selection rule',
        'purpose':'repair diagnostic source alignment only;13.5 attack features and13.6 prediction inputs unchanged',
        'recommendation_allowed':False,'test_outcome_metrics_examined':False}


def main():
    OUT.mkdir(parents=True,exist_ok=True);value=protocol();path=OUT/'protocol.json'
    if path.exists() and json.loads(path.read_text('utf-8'))!=value:raise ValueError('Frozen clean diagnostic differs')
    b.save_json(path,value);frames=[];flows=[]
    for year in range(2021,2025):
        f=pd.read_parquet(h.r.OUT/f'curve_cohort_{year}.parquet')
        stats=pd.read_parquet(h.OUT/f'pa_stats_{year}.parquet').set_index('outcome_key')
        keep=f.outcome_key.isin(stats.index);flows.append({'year':year,'before':len(f),'excluded':int((~keep).sum()),'after':int(keep.sum())})
        f=f[keep].copy();stats=stats.reindex(f.outcome_key)
        for name,num,den in [('response_balls','balls_sum','count_n'),('response_strikes','strikes_sum','count_n'),('response_zone','zone_sum','zone_n')]:
            n=sum(stats[family+'_'+num].fillna(0).to_numpy() for family in h.FAMILIES+['unknown'])
            d=sum(stats[family+'_'+den].fillna(0).to_numpy() for family in h.FAMILIES+['unknown'])
            f[name]=np.divide(n,d,out=np.full(len(f),np.nan),where=d>0)
        f['contact_rate']=1-f.whiff_rate;frames.append(f)
    all_frame=pd.concat(frames,ignore_index=True);panels=[]
    numeric=m.CURVE_CONTROL_NUM+['pitches_before','response_balls','response_strikes','response_zone','stuff','location_value'];categorical=m.CURVE_CONTROL_CAT
    with threadpool_limits(limits=2):
        for role in ['SP','RP']:
            for metric in ['contact_rate','whiff_rate','ev']:
                t=all_frame[all_frame.year.lt(2024)&all_frame.role.eq(role)&all_frame[metric].notna()]
                v=all_frame[all_frame.year.eq(2024)&all_frame.role.eq(role)&all_frame[metric].notna()]
                print(f'Clean13.5 diagnostic {role}/{metric}: {len(t):,}/{len(v):,}',flush=True)
                transform=ColumnTransformer([('numeric',make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler()),numeric),
                    ('spline',make_pipeline(SimpleImputer(strategy='median'),SplineTransformer(n_knots=4,degree=2,include_bias=False)),['pitches_before']),
                    ('categorical',OneHotEncoder(handle_unknown='ignore',sparse_output=True),categorical)],sparse_threshold=1.)
                fit=make_pipeline(transform,Ridge(alpha=100.,solver='lsqr',max_iter=200,tol=1e-4))
                weights=1/t.groupby('appearance_id').outcome_key.transform('count').to_numpy();weights/=weights.mean()
                fit.fit(m.clean_design(t,numeric,categorical),t[metric],ridge__sample_weight=weights)
                rt=t[metric].to_numpy()-fit.predict(m.clean_design(t,numeric,categorical));rv=v[metric].to_numpy()-fit.predict(m.clean_design(v,numeric,categorical))
                joblib.dump(fit,OUT/f'{role}_{metric}.joblib')
                for axis in ['encounter','prior_physical_pitches']:
                    panels.append({'role':role,'metric':metric,'axis':axis,'training':h.association_curve(t,rt,axis),'validation_2024':h.association_curve(v,rv,axis)})
    b.save_json(OUT/'summary.json',{'version':'familiarity_identity_clean_v2','protocol_sha256':b.digest(path),'flow':flows,'panels':panels,
        'scope':'conditional retained-pitcher association only; response controls never prediction inputs; cross-panel exploration, no psychological targeting or causal familiarity claim',
        'prediction_features_changed':False,'test_outcome_metrics_examined':False})
    print('Identity-clean diagnostic supersedes initial13.5 description; prediction inputs unchanged',flush=True)


if __name__=='__main__':main()
