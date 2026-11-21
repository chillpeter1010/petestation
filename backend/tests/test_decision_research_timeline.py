import numpy as np
import pandas as pd
from scripts import export_decision_action_research as e


def test_trace_has_distinct_predecision_anchor_and_postplay_wpa(monkeypatch):
    frame=pd.DataFrame({'inning':[9],'half':['bottom'],'scheduled_innings':[9],'home_score':[1],'away_score':[1],
        'outs':[1],'base_state':[0],'balls':[0],'strikes':[0],'home_score_after':[2],'away_score_after':[1],
        'is_complete':[True],'outs_after':[1],'base_state_after':[1],'event_index':[2],'last_event_index':[7],
        'decision_id':['g:1:boundary'],'at_bat_number':[1],'batter_id':[1],'event_type':['single'],'description':['walkoff'],
        'outgoing_pitcher_id':[10],'terminal_pitcher_id':[11]})
    monkeypatch.setattr(e.b,'we_predict',lambda bundle,state:np.full(len(state),.6))
    before,after=e.trace_points(frame,{})
    assert before['x']<after['x']
    assert before['pitcherId']==10 and after['pitcherId']==11
    assert before['homeWe']==.6 and after['homeWe']==1
    assert np.isclose(after['homeWpa'],.4)
    assert before['decisionId']==after['decisionId']
    frame['outs']=np.nan
    missing=e.trace_points(frame,{})
    assert all(point['homeWe'] is None and point['homeWpa'] is None for point in missing)
