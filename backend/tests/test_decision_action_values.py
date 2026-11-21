import numpy as np
import pandas as pd
from scripts import build_decision_action_values as a


def test_joint_draw_applies_walkoff_non_hr_cap():
    train=pd.DataFrame({'outs':[0,0,0],'base_state':[3,3,3],'extra':[0,0,0],
        'target':[4,4,3],'runs_to_pa_end':[1,2,3],'outs_after':[0,0,0],'post_base':[3,1,0]})
    f=train.iloc[[0]].reset_index(drop=True).assign(half='bottom',inning=9,scheduled_innings=9,defense_lead=0)
    p=np.zeros((1,9));p[0,4]=1
    events,mass=a.draw_transition(f,p,a.b.fit_transitions(train),np.array([.99]))
    assert events.tolist()==[[4,1,0,3]] and mass[0]==0


def test_half_end_values_use_total_runs_terminal_rules_and_defense_sign(monkeypatch):
    initial=pd.DataFrame({'inning':[5,9],'half':['top','bottom'],'scheduled_innings':[9,9],
        'defense_lead':[1,0],'outs':[1,0],'base_state':[0,0],'research_home_we':[.6,.6],'research_re':[.4,.4]})
    monkeypatch.setattr(a.b,'we_predict',lambda bundle,post:np.full(len(post),.55))
    wpa,re24=a.half_values(initial,np.array([1,1]),np.array([3,0]),np.array([0,1]),{})
    np.testing.assert_allclose(wpa,[-.05,-.4]);np.testing.assert_allclose(re24,[-.6,-.6])


def test_simulator_stops_on_inning_end_after_one_batter_and_tracks_tail(monkeypatch):
    monkeypatch.setattr(a,'PATHS',2)
    monkeypatch.setattr(a.b,'design',lambda frame,*args:frame)
    monkeypatch.setattr(a.b,'probabilities',lambda model,x:np.tile([1.,0,0,0,0,0,0,0,0],(len(x),1)))
    monkeypatch.setattr(a.b,'we_predict',lambda bundle,post:np.full(len(post),.6))
    fields={'inning':[5]*2,'half':['top']*2,'scheduled_innings':[9]*2,'defense_lead':[0]*2,
        'outs':[2]*2,'base_state':[0]*2,'extra':[0]*2,'research_home_we':[.5]*2,'research_re':[.1]*2,
        'option_role':['RP']*2,'pitcher_hand':['R']*2,'option_game_pitches':[0]*2,'option_current_bf':[0]*2,'is_current':[False]*2}
    for key in ['pitches_1d_before','pitches_3d_before','pitches_7d_before','pitches_14d_before']:fields[key]=[0]*2
    f=pd.DataFrame(fields)
    train=pd.DataFrame({'outs':[2],'base_state':[0],'extra':[0],'target':[0],
        'runs_to_pa_end':[0],'outs_after':[3],'post_base':[0]})
    ref={'max_training_pitches':{'RP':100},'pitch_counts':{(r,k):np.array([3]) for r in ('SP','RP') for k in range(9)}}
    result=a.simulate_arm(f,np.zeros(2,dtype=int),np.full((32,1,2,4),.5),
        {'model':None,'prior':None,'pooling':20},ref,a.b.fit_transitions(train),{})
    assert not result['censored'].any() and not result['extrapolated'].any()
    np.testing.assert_allclose(result['wpa'],[[.1,.1]])
    np.testing.assert_allclose(result['re24'],[[.1,.1]])


def test_role_pool_does_not_admit_unknown_role_or_cold_start():
    cases=pd.DataFrame({'decision_id':['d'],'boundary_balls':[0],'boundary_strikes':[0],
        'research_home_we':[.5],'research_re':[.5]})
    options=pd.DataFrame({'decision_id':['d']*4,'is_current':[True,False,False,False],
        'option_pitcher_id':[1,2,3,4],'option_role':['SP','RP','RP','RP'],'role_known':[True,True,False,True],
        'pitcher_own_all_n':[100,100,100,0],'pitcher_hand':['R']*4,'lookback_14d_complete':[True]*4,'rest_hours':[48.]*4})
    selected,_,excluded=a.supported_options(cases,options)
    assert selected.empty and excluded[0]['reason']=='fewer_than_two_nominal_RP'
