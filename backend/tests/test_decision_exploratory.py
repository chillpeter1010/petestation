import numpy as np
import pandas as pd
from scripts import build_decision_exploratory as x


def points():
    return pd.DataFrame({'decision_id':list('abcdef'),'game_pk':[1]*6,'team_id':[2]*6,
        'appearance_id':['sp','sp','rp','rp','rp','rp'],'role':['SP','SP','RP','RP','RP','RP'],
        'inning':[4]*6,'half':['top']*6,'anchor_at':np.arange(6.),'seen_pa_count':[10,11,12,13,14,15],
        'risk':[.8]*6,'threshold':[.5]*6})


def test_cooldown_is_shared_when_sp_is_replaced_by_rp():
    result=x.replay_frame(points())
    assert result.emitted.tolist()==[False,True,False,False,True,False]
    assert result.replay_reason.tolist()[3]=='team_cooldown'


def test_replay_ignores_outcome_and_actual_substitution():
    p=points();a=x.replay_frame(p)
    p['changed']=[1]*6;p['target_observed']=False;p['y_run']=np.nan
    b=x.replay_frame(p)
    pd.testing.assert_frame_equal(a[a.columns],b[a.columns])


def test_missing_risk_and_pa_gap_break_persistence():
    p=points().iloc[:3].copy();p['appearance_id']='same';p.loc[1,'risk']=np.nan
    assert not x.replay_frame(p).emitted.any()
    p['risk']=.8;p['seen_pa_count']=[1,3,5]
    assert not x.replay_frame(p).emitted.any()


def test_new_half_does_not_complete_previous_half_persistence():
    p=points().iloc[:2].copy();p['inning']=[4,5]
    assert not x.replay_frame(p).emitted.any()


def test_cooldown_is_not_shared_between_teams():
    p=points();p['team_id']=[2,2,3,3,3,3]
    assert x.replay_frame(p).emitted.tolist()==[False,True,False,True,False,False]


def test_features_exclude_observed_future_actor_actions_and_labels():
    prohibited={'changed','target','observed','actor_pitcher_id','final_pitcher_id','pitcher_id','target_runs','actual_target_batter_id','target_start'}
    assert not prohibited&set(x.NUM+x.LIVE+x.CAT)
    assert not any(k.startswith('forecast') and k.endswith('_id') for k in x.NUM)


def test_unknown_predictor_is_not_converted_to_normal():
    p=points()
    for col in x.NUM+x.LIVE:p[col]=np.nan
    for col in x.CAT:
        if col not in p:p[col]=None
    result=x.design(p)
    assert result[x.NUM+x.LIVE].isna().all().all()


def test_range_gate_rejects_known_extrapolation_but_keeps_missingness():
    p=pd.DataFrame({'current_pitches':[20,120,np.nan]})
    assert x.in_range(p,{'numeric_ranges':{'current_pitches':[0,100]}}).tolist()==[True,False,True]


def test_walkoff_event_has_absorbing_value_and_zero_remaining_re(monkeypatch):
    monkeypatch.setattr(x.b,'we_predict',lambda bundle,frame:np.full(len(frame),.5))
    initial=pd.DataFrame({'inning':[9],'bottom':[1],'scheduled_innings':[9],'score_diff':[0],'outs':[1],
        'base_state':[1],'balls':[0],'strikes':[0],'extra':[0],'research_home_we':[.5],'research_re':[.8]})
    wpa,re=x.event_values(initial,np.array([1]),np.array([1]),np.array([2]),{'re':{(1,2,0):{'mean':.7}}})
    assert np.allclose(wpa,[-.5]) and np.allclose(re,[-.2])


def test_protocol_separates_exploration_from_formal_efficacy():
    p=x.protocol()
    assert p['recommendation_allowed'] is False and p['formal_efficacy_passed'] is False
    assert p['test2025_outcomes_examined'] is False and p['stop']=='16.3'
    assert 'SNIPS/DR withheld' in p['formal_offpolicy']


def test_rollout_resets_preentry_rest_and_stops_at_third_out(monkeypatch):
    p=pd.DataFrame({key:[np.nan,np.nan] for key in x.NUM+x.LIVE})
    for key in x.CAT:p[key]='unknown'
    p=p.assign(inning=5,half='top',scheduled_innings=9,defense_lead=0,outs=2,base_state=0,
        option_role='RP',is_current=False,current_pitches=0,current_bf=0,rest_hours=48.)
    seen=[]
    def predict(bundle,work):
        seen.append(work.rest_hours.to_numpy().copy())
        return np.full((len(work),9),1/9)
    counter=[0]
    def draw(work,probability,tables,u):
        event=[4,0,2,1] if counter[0]==0 else [0,0,3,0]
        counter[0]+=1
        return np.tile(event,(len(work),1)),np.zeros(len(work))
    monkeypatch.setattr(x.pe,'predict',predict);monkeypatch.setattr(x.action,'draw_transition',draw)
    monkeypatch.setattr(x.b,'we_predict',lambda bundle,frame:np.full(len(frame),.5))
    we={'re':{(2,0,0):{'mean':.1},(2,1,0):{'mean':.2}}}
    reference={'max_pitch':{'RP':100},'inter_pa_rest_hours':.01,'tables':{},
        'pitch_counts':{(r,k):np.array([4]) for r in ['SP','RP'] for k in range(9)}}
    result=x.simulate_arm(p,np.zeros((32,2,2)),[{'numeric_ranges':{}}]*2,reference,we,{k:np.full(2,.2) for k in ['nonout','extra_base','k','bb']})
    assert np.allclose(seen[0],48) and np.allclose(seen[1],.01) and len(seen)==2
    assert not result['half']['censored'].any() and np.allclose(result['half']['re24'],.1)
