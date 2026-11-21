import numpy as np
import pandas as pd
from scripts import build_decision_pe_features as f
from scripts import build_decision_pe_models as m


def test_pe_proxy_uses_preterminal_count_and_preserves_missing_contact():
    p=pd.DataFrame({'event_type':['strikeout','single','field_out','field_out','intent_walk'],
        'outs_before':[0]*5,'outs_after':[1,0,1,1,0],'final_strikes':[2]*5,'final_balls':[0]*5,
        'pa_ev_n':[0,1,1,0,0],'ev_mean':[np.nan,100,70,np.nan,np.nan],'pa_fair_sum':[0,1,1,1,0],
        'physical_actors':[1]*5,'actor_pitcher_id':[10]*5,'pitcher_id':[10]*5,'bad_timing':[0]*5})
    score=f.pe_score(p)
    assert np.allclose(score.iloc[:3],[1.,-.88,1.5]) and score.iloc[3:].isna().all()


def test_canonical_pa_categories_keep_nulls_and_raw_events():
    events=pd.Series(['strikeout','single','field_out','walk',None],dtype='string')
    before=pd.Series([0,0,0,0,None],dtype='Int64');after=pd.Series([1,1,1,0,None],dtype='Int64')
    result=f.outcome_group(events,before,after)
    assert result.iloc[:4].tolist()==['k','single','other_out','bb'] and pd.isna(result.iloc[4])


def test_all_comparators_use_same_declared_full_predictors_without_outcomes():
    assert m.columns('hgb_full')==m.columns('rf_full')==m.columns('linear_full')
    prohibited={'changed','target_observed','y_pa','y_run','target_runs','actual_target_batter_id','observed_pa_result','old_decision_at'}
    assert not prohibited&set(f.GROUPS['full']+f.FULLCAT)
    assert not any('forecast1_id'==x for x in f.GROUPS['full'])


def test_temperature_is_finite_normalized_and_identity_at_one():
    p=np.array([[.2,.3,.5],[1e-12,.9,.1]])
    assert np.allclose(m.temperature(p,1),p/p.sum(axis=1,keepdims=True))
    result=m.temperature(p,.5)
    assert np.isfinite(result).all() and np.allclose(result.sum(axis=1),1)


def test_warning_replay_ignores_future_outcome_and_actual_change():
    p=pd.DataFrame({'decision_id':list('abcde'),'game_pk':[1]*5,'team_id':[1]*5,'appearance_id':['x']*5,
        'role':['SP']*5,'inning':[4]*5,'half':['top']*5,'anchor_at':[1,2,3,4,5],'seen_pa_count':[10,11,12,13,14]})
    a=m.warning_replay(p,np.ones(5),.5)
    p['changed']=[0,1,0,0,1];p['target_observed']=[1,0,1,1,0];p['y_run']=[0,np.nan,1,1,np.nan]
    b=m.warning_replay(p,np.ones(5),.5)
    pd.testing.assert_frame_equal(a,b)
    assert a.emitted.tolist()==[False,True,False,False,False]


def test_warning_gap_and_new_half_reset_persistence():
    p=pd.DataFrame({'decision_id':list('abcd'),'game_pk':[1]*4,'team_id':[1]*4,'appearance_id':['x']*4,
        'role':['RP']*4,'inning':[5,5,6,6],'half':['top']*4,'anchor_at':[1,2,3,4],'seen_pa_count':[10,12,13,14]})
    result=m.warning_replay(p,np.ones(4),.5)
    assert result.emitted.tolist()==[False,False,False,True]


def test_cluster_loss_is_paired_and_reproducible():
    p=pd.DataFrame({'game_pk':[1,1,2,2],'outgoing_pitcher_id':[10,11,10,11]})
    a=m.cluster_delta(p,[-.1]*4,reps=50,seed=4)
    assert a==m.cluster_delta(p,[-.1]*4,reps=50,seed=4)
    assert np.isclose(a['delta'],-.1) and np.allclose(a['interval'],[-.1,-.1])


def test_hgb_pe_is_a_feature_addition_not_a_different_learner():
    base=m.make_model('hgb_base')[-1].get_params();pe=m.make_model('hgb_pe')[-1].get_params()
    assert base==pe
    assert set(m.columns('hgb_base')[0])<set(m.columns('hgb_pe')[0])<set(m.columns('hgb_full')[0])
