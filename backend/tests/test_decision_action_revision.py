import numpy as np
import pandas as pd
from scripts import build_decision_action_revision as d


def test_hybrid_uses_new_state_only_at_first_pa_then_baseline(monkeypatch):
    monkeypatch.setattr(d,'PATHS',2);calls=[]
    monkeypatch.setattr(d,'first_probability',lambda frame,*args:(calls.append('first') or np.tile([1.,0,0,0,0,0,0,0,0],(len(frame),1))))
    monkeypatch.setattr(d.b,'design',lambda frame,*args:frame[['outs','option_game_pitches','is_current']])
    def probability(model,x):
        calls.append('baseline');assert x.is_current.all() and (x.option_game_pitches==3).all()
        return np.tile([1.,0,0,0,0,0,0,0,0],(len(x),1))
    monkeypatch.setattr(d.b,'probabilities',probability)
    def transition(frame,p,tables,uniform):
        return np.array([[0,0,min(o+1,3),0] for o in frame.outs]),np.zeros(len(frame))
    monkeypatch.setattr(d.a,'draw_transition',transition)
    monkeypatch.setattr(d.b,'we_predict',lambda bundle,post:np.full(len(post),.6))
    f=pd.DataFrame({'inning':[5]*2,'half':['top']*2,'scheduled_innings':[9]*2,'defense_lead':[0]*2,
        'outs':[1]*2,'base_state':[0]*2,'extra':[0]*2,'research_home_we':[.5]*2,'research_re':[.4]*2,
        'option_role':['RP']*2,'pitcher_hand':['R']*2,'option_game_pitches':[0]*2,'option_current_bf':[0]*2,
        'is_current':[False]*2,'first_feature_extrapolated':[False]*2})
    for name in ['pitches_1d_before','pitches_3d_before','pitches_5d_before','pitches_7d_before','pitches_14d_before']:f[name]=0.
    bank=pd.DataFrame({name:[0.] for name in d.a.BATTER_COLUMNS});bank['expected_stand']='L'
    reference={'max_training_pitches':{'RP':100},'cdf':np.array([1.]),'profiles':{'R':bank},
        'pitch_counts':{(r,k):np.array([3]) for r in ['SP','RP'] for k in range(9)}}
    result=d.simulate_arm(f,np.zeros(2,dtype=int),np.full((32,1,2,4),.5),{'model':None,'prior':None},{},reference,{}, {})
    assert calls==['first','baseline'] and not result['censored'].any()
    np.testing.assert_allclose(result['pitches'],[[6,6]])
    np.testing.assert_allclose(result['bf'],[[2,2]])
