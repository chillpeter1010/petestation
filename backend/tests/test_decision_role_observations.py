import numpy as np
import pandas as pd
from scripts import build_decision_role_observations as r


def test_streak_counts_only_consecutive_prior_calendar_days():
    assert r.prior_streak(100,{97,98,99,100,101})==3
    assert r.prior_streak(100,{96,98,100})==0
    assert r.prior_streak(100,{98,99})==2


def test_workload_window_is_completed_history_lower_inclusive_upper_strict():
    day=86400
    history=np.array([0.,2*day,4*day,5*day,6*day])
    assert r.window_counts(history,np.array([5*day]),3).tolist()==[2]
    assert r.window_counts(history,np.array([5*day]),5).tolist()==[3]
    assert r.window_counts(history,np.array([0.]),5).tolist()==[0]


def test_pitch_flags_keep_foul_contact_and_unknown_denominators():
    d=pd.Series(['foul_tip','swinging_strike','hit_into_play','called_strike',None])
    flags=r.pitch_flags(d,pd.Series([110,100,95,np.nan,np.nan]),pd.Series([20,20,10,np.nan,np.nan]))
    assert flags.contact.tolist()[:4]==[1.,0.,1.,0.]
    assert flags.whiff.tolist()[:4]==[0.,1.,0.,0.]
    assert flags.csw.tolist()[:4]==[0.,1.,0.,1.]
    assert np.isnan(flags.ev.iloc[0]) and flags.ev.iloc[2]==95
    assert np.isnan(flags.swing.iloc[4])


def test_prefix_excludes_equal_time_and_future_pitch_and_state():
    with r.connect() as c:
        fields={'session_id':['a:1']*3,'appearance_id':['a']*3,'pitcher_id':[1]*3,'role':['SP']*3,
            'pitch_type':['FF']*3,'available_at':[10.,20.,30.],'event_index':[1,2,3],
            'session_pitch_position':[1,2,3],'time_reliable':[True]*3,'plus_model_id':['model']*3}
        for name in r.MEASURES:fields[name]=[10.,20.,999.]
        for name in r.FLAGS:fields[name]=[1.,0.,1.]
        c.register('o_frame',pd.DataFrame(fields));c.execute('CREATE VIEW o AS SELECT * FROM o_frame')
        c.register('q_frame',pd.DataFrame({'request_id':['q'],'appearance_id':['a'],'pitcher_id':[1],
            'role':['SP'],'cutoff':[30.],'entry_at':[5.],'fold_id':['frozen_2024']}))
        c.execute('CREATE VIEW requests AS SELECT * FROM q_frame')
        c.execute('CREATE TABLE type_prior(pitcher_id BIGINT,role VARCHAR,pitch_type VARCHAR,model_id VARCHAR,available_at DOUBLE,research_stuff_plus_sum DOUBLE,research_stuff_plus_n BIGINT,research_location_plus_sum DOUBLE,research_location_plus_n BIGINT)')
        c.execute('CREATE TABLE old_state_history(appearance_id VARCHAR,state_observed_at DOUBLE,state_train_cutoff DOUBLE,quality_plus DOUBLE,physical_plus DOUBLE,command_plus DOUBLE,quality_low DOUBLE,quality_high DOUBLE,physical_low DOUBLE,physical_high DOUBLE,command_low DOUBLE,command_high DOUBLE,reliability DOUBLE,status VARCHAR)')
        c.execute("INSERT INTO old_state_history VALUES('a',30,1,999,999,999,998,1000,998,1000,998,1000,1,'test')")
        r.attach_prefix(c,'requests','result')
        result=c.table('result').fetchdf().iloc[0]
        assert result.observation_at==20
        assert result.live_research_stuff_plus==15
        assert result.live_research_stuff_plus_n==2
        assert pd.isna(result.quality_plus)
        assert pd.isna(result.mix_delta_research_stuff_plus)


def test_recent_interval_preserves_unknown_and_single_appearance_uncertainty():
    mean,n,low,high=r.interval_stats(np.array([10.,np.nan,20.]),np.array([0,0,1]),np.array([1,3,2]))
    np.testing.assert_allclose(mean[:2],[10,15])
    assert n.tolist()==[1,2,0]
    assert np.isnan(low[0]) and np.isnan(high[0])
    assert low[1]<mean[1]<high[1]
    assert np.isnan(mean[2])
