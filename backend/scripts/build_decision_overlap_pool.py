"""Explicit post-diagnostic probability-mass correction; core v1 stays frozen.

The original two-stage product was conditional on incoming actor belonging to
the RP pool. Preserve an explicit outside-pool mass before actor IP weights.
"""
from pathlib import Path
import argparse
import sys
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_overlap as q
OUT=q.ROOT/'data/research/decision_overlap_pool_revision_v2'


def save(name,value):q.b.save_json(OUT/name,value)


def actor_mass(change,pool,choice):return np.asarray(change)*np.asarray(pool)*np.asarray(choice)


def protocol():
    paths=[Path(__file__),Path(q.__file__),q.OUT/'protocol.json',q.OUT/'core_manifest.json',q.OUT/'summary.json']
    return {'version':'decision_overlap_pool_mass_v2','input_sha256':{p.relative_to(q.ROOT).as_posix():q.b.digest(p) for p in paths},
        'reason':'explicit correction after core2024 diagnostic review: core change*conditional actor score omitted probability of changing outside nominal RP pool; preserve original core artifacts, no threshold tuning or independent-test claim',
        'method':'P(actor)=P(change|X)*P(in nominal RP pool|change,X)*P(actor|change,in pool,X); outside pool has mass P(change)*(1-P(in pool|change,X)); plus continue sums1',
        'membership':'fit only actually changed development decisions, same strict forward years and80/20 game-time fit/cal; same fixed binary HGB7/60 and late-time Platt, same predecision NUM/CAT; no labels as prediction features; zero RP options implies membership0',
        'support':'same predeclared conditional>=.02, corrected actor joint>=.005, own development selected>=20, prior RP>=5 and development cell support; screening only, core balance gates and operational unknown still block promotion',
        'test2025_outcomes_examined':False,'recommendation_allowed':False,'stop':'15'}


def freeze():
    OUT.mkdir(exist_ok=True);value=protocol();path=OUT/'protocol.json'
    if path.exists():assert q.read(path)==value
    save('protocol.json',value);print('Slice15 explicit outside-pool mass revision frozen; original diagnostics retained',flush=True)


def run():
    assert q.read(OUT/'protocol.json')==protocol();reports=[]
    original=q.read(q.OUT/'summary.json')
    for year in [2022,2023,2024]:
        for role in ['SP','RP']:
            past=pd.concat([pd.read_parquet(q.OUT/f'boundaries_{y}.parquet') for y in range(2021,year)],ignore_index=True)
            cutoff=pd.Timestamp(f'{year}-01-01',tz='UTC').timestamp()
            past=past[past.role.eq(role)&past.changed.eq(1)&past.game_closed_at.lt(cutoff)].copy()
            past['pool_member']=past.choice_observed.astype(int);fit,cal,flow=q.partition(past)
            valid=pd.read_parquet(q.OUT/f'scored_{year}_{role}_boundaries.parquet')
            assert cal.game_closed_at.max()<valid.decision_at.min()
            print(f'Slice15 pool mass {year}/{role}: {len(fit):,} fit / {len(cal):,} calibration changes',flush=True)
            with threadpool_limits(limits=2):bundle=q.binary_fit(fit,cal,'pool_member');prob=q.binary_predict(bundle,valid)
            prob=np.where(valid.rp_count.fillna(0).gt(0),prob,0.)
            valid['pool_membership_probability']=prob
            valid['outside_pool_probability']=valid.propensity*(1-prob)
            joblib.dump(bundle,OUT/f'membership_{year}_{role}.joblib')
            splits=pd.concat([f[['decision_id','game_pk','decision_at','game_closed_at']].assign(partition=name) for name,f in [('fit',fit),('calibration',cal)]],ignore_index=True)
            splits.to_parquet(OUT/f'split_{year}_{role}.parquet',index=False)
            predictions=valid[['decision_id','game_pk','role','propensity','pool_membership_probability','outside_pool_probability']]
            predictions.to_parquet(OUT/f'probabilities_{year}_{role}.parquet',index=False)
            candidates=pd.read_parquet(q.OUT/f'candidate_support_{year}_{role}.parquet')
            candidates=candidates.merge(predictions[['decision_id','pool_membership_probability']],on='decision_id',validate='many_to_one')
            candidates['core_conditional_score']=candidates.joint_probability
            candidates['joint_probability']=actor_mass(candidates.propensity,candidates.pool_membership_probability,candidates.choice_probability)
            candidates['statistical_support']=candidates.choice_probability.ge(.02)&candidates.joint_probability.ge(.005)&candidates.prior_selected.ge(20)&candidates.prior_observed_relief.ge(5)&candidates.past_cell_support
            candidates.to_parquet(OUT/f'candidate_support_{year}_{role}.parquet',index=False,compression='zstd')
            chosen=candidates[candidates.chosen.eq(1)];supported=chosen[chosen.statistical_support]
            row=next(dict(x) for x in original['candidate_support'] if x['year']==year and x['role']==role)
            row.update({'statistically_supported_options':int(candidates.statistical_support.sum()),'chosen_supported':len(supported),
                'joint_weight_sensitivity':[{'cap':cap,**q.weight_summary(q.cap_weights(1/supported.joint_probability.to_numpy(),cap))} for cap in q.CAPS],
                'membership_metrics':q.binary_metrics(valid.loc[valid.changed.eq(1),'choice_observed'].astype(int).to_numpy(),prob[valid.changed.eq(1)],bundle['prior']),
                'membership_flow':flow,'fit_last_label':float(fit.game_closed_at.max()),'cal_first_decision':float(cal.decision_at.min()),'cal_last_label':float(cal.game_closed_at.max()),
                'validation_first_decision':float(valid.decision_at.min()),'joint_probability_scope':'corrected full assignment mass with explicit outside-RP-pool residual'})
            reports.append(row)
    save('summary.json',{'version':'decision_overlap_pool_mass_v2','candidate_support':reports,'recommendation_allowed':False,'test2025_outcomes_examined':False,'stop':'15'})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['freeze','run']);args=parser.parse_args();globals()[args.stage]()
