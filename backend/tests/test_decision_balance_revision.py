import numpy as np
import pandas as pd
from scripts import build_decision_balance_revision as q


def test_balance_moment_gradient_matches_finite_difference():
    rng=np.random.default_rng(10);x=np.column_stack([np.ones(40),rng.normal(size=(40,3))]);y=rng.integers(0,2,size=40)
    beta=np.array([.1,.2,-.1,.05]);loss,gradient=q.balance_objective(beta,x,y)
    numerical=[]
    for j in range(len(beta)):
        delta=np.eye(len(beta))[j]*1e-6
        numerical.append((q.balance_objective(beta+delta,x,y)[0]-q.balance_objective(beta-delta,x,y)[0])/2e-6)
    assert np.isfinite(loss) and np.allclose(gradient,numerical,rtol=1e-5,atol=1e-7)


def test_overlap_weights_are_bounded_and_target_different_population_from_ipw():
    a=np.array([1,0,1,0]);p=np.array([.01,.99,.5,.5])
    overlap=q.balancing_weights(a,p,'overlap');ipw=q.balancing_weights(a,p,'ipw')
    assert np.allclose(overlap,[.99,.99,.5,.5]) and overlap.max()<=1
    assert ipw[0]==100 and ipw[2]==2


def test_model_feature_allowlist_has_no_old_clock_future_identity_or_missingness_label():
    denied={'changed','incoming_pitcher_id','old_decision_at','clock_gap_seconds','future_bad','future_observed','missing_reason','game_closed_at','batter_id'}
    assert not denied&set(q.CORE+q.STATE+q.FULLCAT)
    assert set(q.columns('logit_core')[0])<set(q.columns('logit_full')[0])


def test_core_ablation_is_still_judged_on_rich_benchmark_and_separation_fails():
    f=pd.DataFrame({name:np.zeros(40) for name in q.CORE+q.STATE})
    for name in q.FULLCAT:f[name]='unknown'
    f['changed']=[0]*20+[1]*20;f['past_cell_support']=True;f['smooth_stuff']=f.changed
    result=q.diagnostics(f,np.full(40,.5),'overlap')
    row=next(x for x in result['balance'] if x['field']=='smooth_stuff:value')
    assert row['arm_constant_separation'] and result['max_abs_smd_after']>.1 and not result['diagnostic_gate']
    assert q.diagnostics(f,np.full(40,.5),'ipw')['retained']==40
    assert f.past_cell_support.all()
