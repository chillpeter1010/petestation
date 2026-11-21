import numpy as np
import pandas as pd

from scripts import build_decision_overlap as q
from scripts import build_decision_overlap_pool as pool


def test_conditional_choice_normalizes_within_each_decision_not_across_pool():
    groups=np.array(['a','a','b','b','b'])
    result=q.softmax_groups(np.array([1000.,1001.,-1000.,-1000.,-1000.]),groups)
    assert np.isclose(result[:2].sum(),1) and np.isclose(result[2:].sum(),1)
    assert result[1]>result[0] and np.allclose(result[2:],1/3)
    assert np.allclose(result,q.softmax_groups(np.array([2000.,2001.,20.,20.,20.]),groups))


def test_rare_assignment_can_destroy_effective_sample_size():
    assert q.ess(np.ones(100))==100
    weights=np.r_[np.ones(99),1000.]
    assert q.ess(weights)<2 and q.ess(q.cap_weights(weights,10))>50
    assert q.weight_summary([])['ess']==0


def test_past_future_partition_drops_spanning_game_and_blocks_clock_leakage():
    f=pd.DataFrame({'game_pk':np.arange(1000),'decision_at':np.arange(1000)*86400.+1,'game_closed_at':np.arange(1000)*86400.+100})
    f.loc[0,'game_closed_at']=800*86400.+100
    fit,cal,_=q.partition(f)
    assert 0 not in fit.game_pk.to_list() and 0 not in cal.game_pk.to_list()
    assert fit.game_closed_at.max()<cal.decision_at.min() and set(fit.game_pk).isdisjoint(cal.game_pk)


def test_action_design_excludes_actor_chosen_and_all_postdecision_labels():
    f=pd.DataFrame({name:[1.,2.] for name in q.NUM})
    for name in q.CAT:f[name]='unknown'
    first=q.design(f)
    f['rp_count']=pd.Series([1,pd.NA],dtype='Int64')
    numeric=q.design(f)
    assert numeric.rp_count.dtype==np.dtype('float64') and np.isnan(numeric.rp_count.iloc[1])
    f['rp_count']=[1.,2.]
    for name in ['changed','future_observed','future_bad','incoming_pitcher_id','game_closed_at','target_anchor','chosen']:
        f[name]=[999.,-999.]
    pd.testing.assert_frame_equal(first,q.design(f))
    assert not set(q.CHOICE)&{'chosen','incoming_pitcher_id','role','decision_id'}


def test_role_cells_keep_unknown_li_separate_from_low_leverage():
    f=pd.DataFrame({'role':['SP']*3,'inning':[1,5,10],'current_pitches':[20,60,100],'research_pa_li':[np.nan,.9,2.1]})
    result=q.cells(f)
    assert result.tolist()==['SP:1-3:0-29:unknown','SP:4-6:60-89:low','SP:10+:90+:high']


def test_tiny_flag_sample_does_not_get_an_interval_or_support_from_all_successes():
    frame=pd.DataFrame({'complete':[True]*10,'future_observed':[1]*10,'propensity':[.5]*10,
        'two_red':[True]+[False]*9,'future_bad':[1.]+[0.]*9,'game_pk':np.arange(10),
        'outgoing_pitcher_id':np.arange(10),'appearance_id':np.arange(10)})
    result=q.weighted_contrast(frame,None)
    assert result['flagged']==1 and result['difference']>.8 and result['interval'] is None
    assert result['supported'] is False and result['valid_draws']<200


def test_actor_assignment_preserves_outside_pool_mass_instead_of_renormalizing_it_away():
    actors=pool.actor_mass(.4,.75,np.array([.25,.75]))
    outside=.4*(1-.75);continuation=1-.4
    assert np.isclose(actors.sum(),.3) and np.isclose(actors.sum()+outside+continuation,1)
    assert np.all(pool.actor_mass(.4,0.,np.array([.25,.75]))==0)
