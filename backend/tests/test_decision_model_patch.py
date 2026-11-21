import numpy as np
import pandas as pd

from scripts import build_decision_model_patch as p


def test_calibration_is_bounded_normalized_and_reduces_overconfidence():
    y=np.tile(np.arange(9),100)
    probabilities=np.full((len(y),9),.005)
    probabilities[np.arange(len(y)),np.roll(y,1)]=.96
    t=p.fit_temperature(y,probabilities)
    calibrated=p.temperature_probability(probabilities,t)
    assert .5<=t<=3 and np.allclose(calibrated.sum(axis=1),1)
    assert -np.log(calibrated[np.arange(len(y)),y]).mean() < -np.log(probabilities[np.arange(len(y)),y]).mean()


def test_calibration_split_excludes_spanning_games_and_keeps_time_order():
    f=pd.DataFrame({'game_pk':np.repeat(np.arange(20),2),'decision_id':[str(i) for i in range(40)],
        'decision_at':np.repeat(np.arange(20)*86400.,2)+np.tile([1.,2.],20),
        'pa_end_at':np.repeat(np.arange(20)*86400.,2)+np.tile([10.,20.],20)})
    f.loc[f.game_pk.eq(15),'pa_end_at']=17*86400.
    fit,cal,flow=p.temporal_partition(f)
    assert flow['spanning_games_excluded']>=1
    assert 15 not in set(fit.game_pk)|set(cal.game_pk)
    assert fit.pa_end_at.max()<cal.decision_at.min()
    assert set(fit.game_pk).isdisjoint(cal.game_pk)


def test_independent_groups_and_one_bounded_nonlinear_family():
    assert len(p.CONFIGS)==16
    for group in ['current','recent','batter']:
        used=set(p.columns(p.CONFIG_BY_ID[f'linear_{group}_0.001'])[0])
        base=set(p.columns(p.CONFIG_BY_ID['linear_base_0.001'])[0])
        assert used-base==set(p.GROUPS[group])-base
    assert not any('_'+family+'_' in name for name in p.BATTER for family in p.u.h.FAMILIES)
    tree=p.make_model(p.CONFIG_BY_ID['tree_rich_7'])[-1]
    assert tree.max_leaf_nodes==7 and not tree.early_stopping and tree.max_iter==60


def test_whole_game_cap_is_stable_and_never_splits_games():
    f=pd.DataFrame({'game_pk':np.repeat(np.arange(20),3)})
    sampled=p.game_sample(f,10)
    assert sampled.groupby('game_pk').size().eq(3).all()
    assert set(sampled.game_pk)==set(p.game_sample(f.iloc[::-1],10).game_pk)
