import numpy as np
import pandas as pd
from scripts import build_decision_entry_review as e


def test_comparison_gates_require_balance_ess_calibration_and_fit():
    r={'max_abs_smd_after':.1,'change':{'ess':500},'continue':{'ess':500}}
    assert e.gate_failures(r,{'ece':.03})==[]
    r['max_abs_smd_after']=.10001;r['change']['ess']=499
    assert e.gate_failures(r,{'ece':.03001},True)==['balance_smd','effective_sample_size','action_calibration','fit_warning']
    r['max_abs_smd_after']=None
    assert 'balance_smd' in e.gate_failures(r,{'ece':np.nan})


def test_review_eligibility_never_uses_actual_action_or_future_observation():
    f=pd.DataFrame({'decision_id':['a','b','c'],'game_pk':[1]*3,'appearance_id':['x']*3,'outgoing_pitcher_id':[10]*3,
        'role':['RP']*3,'phase':['within_inning']*3,'anchor_at':[1,2,3],'past_cell_support':[True,True,False]})
    first=e.review_ledger(f,[True,False,True],np.array([.1,.2,.3]),False,False)
    f['changed']=[0,1,1];f['future_ten_y']=[0,np.nan,1];f['future_ten_observed']=[1,0,1]
    second=e.review_ledger(f,[True,False,True],np.array([.1,.2,.3]),False,False)
    pd.testing.assert_frame_equal(first,second)
    assert first.review_rejection.tolist()==['development_comparison_failed','outside_fixed_population','past_cell_unsupported']
    assert first.initial_support.tolist()==[True,False,False] and not first.review_eligible.any()


def test_retrospective_gate_does_not_change_past_only_initial_support():
    f=pd.DataFrame({'decision_id':['a'],'game_pk':[1],'appearance_id':['x'],'outgoing_pitcher_id':[10],
        'role':['SP'],'phase':['within_inning'],'anchor_at':[1],'past_cell_support':[True]})
    a=e.review_ledger(f,[True],np.array([.5]),False,False);b=e.review_ledger(f,[True],np.array([.5]),True,True)
    assert a.initial_support.equals(b.initial_support) and not b.review_eligible.any()
    assert b.review_rejection.iloc[0]=='pipeline_not_ready'


def test_two_way_cluster_brier_is_paired_reproducible_and_target_specific():
    f=pd.DataFrame({'game_pk':[1,1,2,2,3,3],'outgoing_pitcher_id':[10,11,10,11,10,11]})
    y=np.array([0,1,0,1,0,1]);p=np.array([.1,.9,.1,.9,.1,.9])
    result=e.clustered_brier(f,y,p,.5,reps=50,seed=5)
    assert result==e.clustered_brier(f,y,p,.5,reps=50,seed=5)
    assert np.isclose(result['delta'],-.24) and np.allclose(result['interval'],[-.24,-.24])
    assert result['games']==3 and result['pitchers']==2


def test_strategy_contract_preserves_horizon_abstention_and_unready_status():
    contract=e.strategy_contract()
    assert not contract['implementation_ready']
    assert 'uniform' in contract['replacement_law'] and 'abstain' in contract['replacement_law']
    assert 'half' in contract['primary_endpoint'] and 'same half' in contract['secondary_endpoint']
    assert 'never substitutes' in contract['exploratory_endpoint']
