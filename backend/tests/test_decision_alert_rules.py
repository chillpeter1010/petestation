import numpy as np
import pandas as pd

from scripts import decision_alert_rules as a


def points():
    n=9
    return pd.DataFrame({'decision_id':[f'd{i}' for i in range(n)],'game_pk':1,'team_id':10,
        'defensive_ordinal':np.arange(n),'appearance_id':['a']*6+['b']*3,'inning':1,'half':'top',
        'decision_at':np.arange(n)*30.,'point_reason':'qualifies'})


def test_persistence_gap_resets_and_same_appearance_never_reemits():
    f=points();f.loc[1,'point_reason']='cohort:no_legal_choice';result=a.issue_alerts(f)
    assert result[result.alert_emitted].decision_id.tolist()==['d3','d7']
    assert result.loc[2,'run_length']==1 and result.loc[4,'alert_reason']=='cooldown'
    assert result.loc[5,'alert_reason']=='cooldown'
    f.loc[5,'decision_id']='renamed';f['observed_change']=True
    assert a.issue_alerts(f).alert_emitted.tolist()==result.alert_emitted.tolist()


def test_half_inning_and_missing_raw_boundary_break_persistence():
    f=points().iloc[:3].copy();f.loc[1,'inning']=2;f.loc[2,'defensive_ordinal']=4
    assert not a.issue_alerts(f).alert_emitted.any()


def test_cooldown_can_block_a_new_appearance():
    f=points().iloc[:5].copy();f['appearance_id']=['a','a','b','b','b']
    result=a.issue_alerts(f)
    assert result[result.alert_emitted].decision_id.tolist()==['d1','d4']
    assert result.loc[3,'alert_reason']=='cooldown_other_appearance'


def test_matching_is_identity_and_side_specific_with_strict_two_pa_ten_minute_window():
    alerts=points().iloc[[1,7]].copy()
    events=pd.DataFrame([
        {'event_id':'wrong-side','game_pk':1,'team_id':11,'outgoing_appearance_id':'a','boundary_decision_id':'d1','event_at':30.,'defensive_ordinal':1,'at_bat_number':1,'event_index':0},
        {'event_id':'exact','game_pk':1,'team_id':10,'outgoing_appearance_id':'a','boundary_decision_id':'d1','event_at':30.,'defensive_ordinal':1,'at_bat_number':1,'event_index':0},
        {'event_id':'advance','game_pk':1,'team_id':10,'outgoing_appearance_id':'b','boundary_decision_id':'d9','event_at':270.,'defensive_ordinal':9,'at_bat_number':9,'event_index':0}])
    pairs=a.match_events(alerts,events)
    assert pairs.match_kind.tolist()==['same_boundary','advance_window']
    events.loc[2,'event_at']=alerts.iloc[1].decision_at+601
    assert len(a.match_events(alerts,events))==1
    events.loc[2,['event_at','defensive_ordinal']]=[270.,10]
    assert len(a.match_events(alerts,events))==1


def test_matching_is_one_to_one_and_takes_earliest_eligible_not_nearest():
    alerts=points().iloc[[0,1]].copy()
    events=pd.DataFrame([{'event_id':name,'game_pk':1,'team_id':10,'outgoing_appearance_id':'a','boundary_decision_id':'other',
        'event_at':float(ordinal*30),'defensive_ordinal':ordinal,'at_bat_number':ordinal,'event_index':0} for name,ordinal in [('first',1),('second',2)]])
    pairs=a.match_events(alerts,events)
    assert pairs.event_id.tolist()==['first','second']
    assert pairs.event_id.is_unique and pairs.decision_id.is_unique


def test_gate_rejects_support_and_interval_failure_at_fixed_threshold():
    f=pd.DataFrame({'simulation_supported':[True,True,False,True],'maximum_unsupported_mass':[0.,0.,0.,.02],
        'wpa_delta':[.005,.0049,.02,.02],'wpa_mc95_low':[.001]*4,'wpa_bootstrap80_low':[.001]*4})
    assert a.qualify(f).tolist()==['qualifies','below_minimum_gain','simulation_censor_or_extrapolation','rare_transition_mass']


def test_non_batter_play_does_not_consume_advance_pa_budget():
    alert=points().iloc[0].copy();alert['completed_pa_before']=0
    event=pd.Series({'game_pk':1,'team_id':10,'outgoing_appearance_id':'a','boundary_decision_id':'later',
        'event_at':100.,'defensive_ordinal':3,'completed_pa_before':2})
    assert a.eligible_pair(alert,event)=='advance_window'
    event['completed_pa_before']=0
    assert a.eligible_pair(alert,event) is None
    event['outgoing_appearance_id']=pd.NA
    assert a.eligible_pair(alert,event) is None
