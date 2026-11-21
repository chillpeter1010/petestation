import numpy as np
import pandas as pd
from scripts import build_decision_role_ablation as u


def test_leave_outs_remove_derived_descendants_and_core_workload_columns():
    for variant in ['without_live','without_plus','without_72h','without_120h','without_exposure']:
        assert not set(u.RISK)&set(u.model_columns(variant)[0])
    assert 'pitches_3d_before' not in u.model_columns('load_without_72h')[0]
    assert 'consecutive_days' not in u.model_columns('load_without_streak')[0]
    assert 'option_current_bf' not in u.model_columns('without_exposure')[0]
    assert 'arsenal_type' not in u.model_columns('without_type')[1]
    assert not any(x.startswith(('future','response_','pa_')) for x in u.model_columns('all')[0])


def test_paired_two_way_family_intervals_keep_contrast_direction():
    f=pd.DataFrame({'game_pk':np.repeat(np.arange(10),5),'option_pitcher_id':np.tile(np.arange(5),10)})
    values=np.tile([.1,-.2],(len(f),1));out=u.family_intervals(f,values)
    assert np.isclose(out[0]['mean'],.1) and out[0]['role_family97_5'][0]>0
    assert np.isclose(out[1]['mean'],-.2) and out[1]['role_family97_5'][1]<0


def test_missing_type_ablation_reverts_pair_prior_to_batter_not_type():
    prior=np.full(9,1/9)
    f=pd.DataFrame({n:[0.] for n in set(u.b.LEVELS['matchup'][0]+u.b.LEVELS['matchup'][1]+u.SUPPORT+u.SUPPORT_CAT+u.VARIANTS['all'])-{'pitcher_log_n','batter_log_n'}})
    for actor in ['batter','pitcher']:
        f[actor+'_ability_status']='own_all';f[actor+'_own_all_n']=100.;f[actor+'_own_split_n']=100.
        for key in u.b.OUTCOMES:f[actor+'_'+key+'_rate']=1/9
    f['is_current']=True;f['arsenal_type']='R:fastball:95plus';f['pair_n']=0.
    for key in u.b.OUTCOMES:f['pair_'+key+'_count']=np.nan;f['type_'+key+'_rate']=.9
    x=u.design(f,'without_type',prior)
    assert np.isclose(x.pair_k_rate.iloc[0],1/9)
