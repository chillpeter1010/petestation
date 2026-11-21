import numpy as np
import pandas as pd

from scripts import build_decision_signal_calibration as q
from scripts import build_decision_signal_models as m
from scripts import decision_signal_episodes as e


def test_smoothing_resets_at_missing_evidence_and_never_reads_future():
    f=pd.DataFrame({'session_id':['a']*5,'value':[1.,2.,np.nan,8.,9.]})
    result=q.smooth(f,'value',.3)
    assert np.isclose(result.iloc[1],1.3) and np.isnan(result.iloc[2]) and result.iloc[3]==8
    f.loc[4,'value']=-1000
    assert q.smooth(f,'value',.3).iloc[:4].equals(result.iloc[:4])


def test_future_target_needs_a_new_complete_block_and_both_a_measurements():
    f=pd.DataFrame({'session_id':['a']*4,'block_number':[0,1,3,4],'available_at':[10.,20.,40.,50.],
        'residual_stuff':[0.,-6.,0.,-6.],'residual_velocity':[0.,-.6,0.,np.nan],
        'residual_location':[0.,-6.,0.,0.],'residual_contact':[0.,.2,0.,0.]})
    out=q.future_labels(f)
    assert out.future_A.iloc[0]==1 and out.future_C.iloc[0]==1
    assert np.isnan(out.future_A.iloc[1]) and np.isnan(out.future_A.iloc[2]) and np.isnan(out.future_A.iloc[3])


def test_support_is_role_specific_and_does_not_call_high_count_normal():
    f=pd.DataFrame({'role':['SP','SP','RP','RP'],'session_pitches':[34,40,10,70],
        'game_pitches':[34,40,10,70],'measurement_models':1,'n_stuff':10,'y_stuff':0.})
    assert q.supported(f,'stuff').tolist()==[False,True,True,False]


def test_fit_calibration_partition_has_strict_clock_and_no_shared_games():
    f=pd.DataFrame({'game_pk':np.arange(30),'anchor_at':np.arange(30)*86400.+1,'available_at':np.arange(30)*86400.+10})
    fit,cal,_=q.split(f)
    assert fit.available_at.max()<cal.anchor_at.min() and set(fit.game_pk).isdisjoint(cal.game_pk)


def test_color_requires_practical_effect_and_missing_stays_unknown():
    f=pd.DataFrame({'A_severity':[5.,5.,5.,np.nan],'A_effect':[.1,.6,1.,np.nan]})
    cal={'yellow':1.,'red':2.,'bins':[]}
    out=q.color_and_risk(f,'A',cal)
    assert out.A_state.tolist()==[0,1,2,-1] and out.A_risk.isna().all()


def test_load_cdf_does_not_treat_repeated_zero_workload_as_maximum():
    reference=np.array([0.,0.,0.,0.])
    assert m.midrank(reference,np.array([0.]))[0]==.5
    assert m.midrank(reference,np.array([1.]))[0]==1.


def test_outcome_controls_share_masks_but_do_not_include_group_values():
    control,_=m.model_columns('SP','control');all_values,_=m.model_columns('SP','all')
    assert set(m.COMMON)<=set(control)
    assert not set(sum(m.EXTRA.values(),[]))&set(control)
    assert set(sum(m.EXTRA.values(),[]))<=set(all_values)


def episode_points(states,blocks=None):
    n=len(states)
    f=pd.DataFrame({'decision_id':[f'd{i}' for i in range(n)],'game_pk':1,'team_id':1,'appearance_id':'a',
        'role':'SP','session_id':'s','block_number':np.arange(n) if blocks is None else blocks,
        'defensive_ordinal':np.arange(n),'completed_pa_before':np.arange(n)*3,'point_reason':'qualifies'})
    f['block_id']=f.block_number.astype(str)
    for i,g in enumerate('ABCD'):f[g+'_state']=[row[i] for row in states]
    return f


def test_repeated_reads_do_not_establish_cause_persistence():
    f=episode_points([[2,2,0,0]]*3,[0,0,0])
    out,events=e.replay(f,{'SP':2},{'SP':True})
    assert events.empty and not out.nominal_research_alert.any()


def test_recovery_allows_new_event_without_erasing_high_load():
    f=episode_points([[2,2,0,2],[2,2,0,2],[0,0,0,2],[0,0,0,2],[2,2,0,2],[2,2,0,2]])
    out,events=e.replay(f,{'SP':2},{'SP':True})
    assert len(events)==2 and events.end_reason.iloc[0]=='observed_recovery'
    assert out.loc[out.nominal_research_alert,'decision_id'].tolist()==['d1','d5']


def test_gray_is_not_recovery_and_predictive_support_blocks_alerts():
    f=episode_points([[2,2,0,0],[2,2,0,0],[-1,-1,-1,-1],[2,2,0,0],[2,2,0,0]])
    out,events=e.replay(f,{'SP':2},{'SP':False})
    assert len(events)==1 and events.end_reason.iloc[0]=='last_observed_boundary_censored'
    assert not out.nominal_research_alert.any()
