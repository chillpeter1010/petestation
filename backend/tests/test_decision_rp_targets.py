import numpy as np
import pandas as pd
from scripts import build_decision_rp_targets as q


def test_usage_profile_uses_only_entry_history_and_keeps_unknown():
    result=q.usage_profile([4,5,10,10],[3,4,5,4],[15,20,15,21])
    assert result.tolist()==['history_unknown','short_profile','extended_profile','extended_profile']


def test_monitoring_uses_first_forward_evidence_and_never_future_outcome():
    f=pd.DataFrame({'decision_id':['a','b','c','d','e'],'anchor_at':[1,2,3,4,5],
        'appearance_id':['x']*5,'block_id':[None,None,'block0','block0','block1']})
    assert q.monitoring_mask(f).tolist()==[True,False,True,False,True]
    f['future_bad']=[1,0,1,1,0]
    assert q.monitoring_mask(f).tolist()==[True,False,True,False,True]


def test_short_load_is_predecision_relative_load_not_future_duration():
    f=pd.DataFrame({'usage_profile':['short_profile']*3,'relative_pitches':[1.,1.6,1.],
        'relative_bf':[1.,1.,1.6],'final_game_pitches':[100,5,15]})
    assert q.subset_mask(f,'short_load').tolist()==[True,False,False]
    assert not {'changed','future_bad','future_observed','next_pa_y','future_ten_y','actual_pitches','incoming_pitcher_id'}&set(q.NUM+q.CAT)


def test_sparse_outcome_task_is_a_declared_constant_not_unstable_classifier():
    f=pd.DataFrame({'label':[0,1,0,0]})
    bundle=q.model_fit(f,f,'label')
    assert bundle['kind']=='constant' and np.allclose(q.predict(bundle,f),2/6)


def test_missingness_sensitivity_does_not_fill_the_labels():
    f=pd.DataFrame({'next_pa_observed':[1,0,0],'next_pa_y':[1.,np.nan,np.nan],
        'next_pa_observation_probability':[.5,.5,.5],'next_pa_outcome_probability':[.4,.4,.4]})
    before=f.next_pa_y.copy();result=q.scenario_summary(f,'next_pa')
    assert result['worst_case_bounds']==[1/3,1.]
    rates=[x['scenario_rate'] for x in result['missing_scenarios']]
    assert rates[0]<rates[1]<rates[2]
    pd.testing.assert_series_equal(before,f.next_pa_y)


def test_raw_pa_events_match_canonical_outcome_groups_not_group_name_strings():
    events=pd.Series(['strikeout','field_out','grounded_into_double_play','force_out','field_error','walk',
        'single','strikeout_double_play','fielders_choice',None])
    before=pd.Series([0]*10);after=pd.Series([1,1,2,1,0,0,1,2,0,0])
    y=q.pa_nonout(events,before,after)
    assert y.iloc[:9].tolist()==[0,0,0,0,1,1,1,0,1] and np.isnan(y.iloc[9])
