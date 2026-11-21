import numpy as np
import pandas as pd
from scripts import build_decision_ablation as a


def fixture():
    columns = a.b.LEVELS['matchup'][0]+a.SUPPORT_NUM+a.PLUS+a.SIGNALS
    fields = {name:[1.,2.] for name in columns if not name.endswith('_log_n')}
    fields.update({name:['known','known'] for name in a.b.LEVELS['matchup'][1]+a.SUPPORT_CAT})
    for actor in ('pitcher','batter'):
        fields[f'{actor}_own_split_n']=[10,10];fields[f'{actor}_own_all_n']=[20,20]
        fields[f'{actor}_ability_status']=['own_split','own_split']
    return pd.DataFrame(fields)


def test_support_controls_are_identical_across_signal_ablations():
    f=fixture(); prior=np.full(9,1/9)
    base=a.design(f,'baseline',prior);all_features=a.design(f,'all',prior)
    assert set(all_features)-set(base)==set(a.PLUS+a.SIGNALS)
    pd.testing.assert_frame_equal(base,all_features[base.columns])
    assert not set(a.SIGNALS+a.PLUS).intersection(base)


def test_missing_signal_scores_remain_missing_before_train_only_imputer():
    f=fixture(); f.loc[0,'quality']=np.nan
    x=a.design(f,'all',np.full(9,1/9))
    assert pd.isna(x.loc[0,'quality'])
    model=a.make_model('all'); model.fit(x,[0,3])
    assert np.isclose(a.b.probabilities(model,x).sum(axis=1),1).all()


def test_large_role_harm_blocks_global_average_increment():
    n=1000
    f=pd.DataFrame({'game_pk':np.arange(n)//10,'target':np.zeros(n,dtype=int),
        'outgoing_role':['SP']*500+['RP']*500,'is_current':[True]*n})
    base=np.full((n,9),.5/8);base[:,0]=.5
    p=base.copy();p[:500,0]=.9;p[:500,1:]=.1/8;p[500:,0]=.49;p[500:,1:]=.51/8
    result=a.compare(f,p,base)
    assert result['metrics']['log_loss']<a.b.metrics(f.target.to_numpy(),base)['log_loss']
    assert not result['increment_gate']
