import numpy as np
import pandas as pd
from scripts import build_decision_batter_matchups as h


def test_type_uses_supported_past_repertoire_and_fixed_boundaries():
    f=pd.DataFrame({'hand':['R','L','R'],'pitches':[50,100,49],
        'fastball_share':[.6,.4,.8],'breaking_share':[.3,.35,.1],'offspeed_share':[.1,.25,.1],
        'fast_velocity':[95.,90.,98.]})
    assert h.classify_arsenal(f).tolist()==['R:fastball:95plus','L:mixed:90to95','unknown']


def test_attack_scopes_strict_completed_pa_denominators_and_hierarchical_backoff(tmp_path,monkeypatch):
    monkeypatch.setattr(h,'OUT',tmp_path)
    kind='R:fastball:95plus'
    pd.DataFrame({'pitcher_id':[11],'role':['SP'],'appearance_id':['past'],'available_at':[5.],
        'pitches':[100],'fastball_share':[1.],'breaking_share':[0.],'offspeed_share':[0.],
        'fast_velocity':[96.],'arsenal_type':[kind]}).to_parquet(tmp_path/'arsenal_history.parquet')
    for scope in ['pair','type']:
        rows=[]
        for at,n in [(10.,1),(30.,100)]:
            rows.append({'batter_id':1,**({'pitcher_id':11} if scope=='pair' else {'arsenal_type':kind}),
                'available_at':at,'pa_n':n,**{key+'_n':n if key=='k' else 0 for key in h.b.OUTCOMES}})
        pd.DataFrame(rows).to_parquet(tmp_path/(scope+'_history.parquet'))
    rows=[]
    for at,batter,pitcher,family in [(10.,1,11,'fastball'),(20.,1,12,'breaking'),(30.,1,11,'fastball'),(15.,2,11,'fastball')]:
        row={'game_pk':100,'outcome_key':str(at),'batter_id':batter,'pitcher_id':pitcher,'half':'top','available_at':at}
        row.update({f+'_'+s:0. for f in h.FAMILIES+['unknown'] for s in h.SUMS})
        row.update({family+'_'+s:v for s,v in {'pitches':2,'known':2,'swings':1 if family=='fastball' else 2,
            'whiffs':0 if family=='fastball' else 1,'contacts':1,'fouls':1 if family=='fastball' else 0,
            'fair':0 if family=='fastball' else 1,'ev_sum':0 if family=='fastball' else 95,'ev_n':0 if family=='fastball' else 1,
            'hard':0 if family=='fastball' else 1}.items()})
        rows.append(row)
    pd.DataFrame(rows).to_parquet(tmp_path/'pa_stats_2024.parquet')
    for scope in ['batter_family','league_family']:
        rows=[]
        for family in h.FAMILIES:
            for at in [10.,30.]:
                rows.append({**({'batter_id':1} if scope=='batter_family' else {}),'pitcher_hand':'R','family':family,'available_at':at,
                    'known':4,'swings':2,'whiffs':1 if at==10 else 100,'contacts':1,'fouls':1,'fair':0,'ev_sum':0,'ev_n':0,'hard':0})
        pd.DataFrame(rows).to_parquet(tmp_path/(scope+'_history.parquet'))
    q=pd.DataFrame({'request_id':['q','cold'],'decision_id':['d','d2'],'game_pk':[100,100],'decision_at':[30.,30.],
        'option_pitcher_id':[11,99],'option_role':['SP','RP'],'batter_id':[1,3],'pitcher_hand':['R','R'],'half':['top','top']})
    for key in h.b.OUTCOMES:q['batter_'+key+'_rate']=.2 if key=='k' else .1
    result=h.attack_features(q,2024).set_index('request_id');a=result.loc['q'];cold=result.loc['cold']
    assert a.game3_pa_n==2 and a.pair_game3_pa_n==1 and a.other_game3_pa_n==1
    assert a.team3_pa_n==2 and a.game3_observed_at==20
    assert a.game3_fastball_received_share==.5
    assert a.game3_fastball_swing==.5
    assert np.isclose(a.game3_fastball_swing_share,1/3)
    assert a.pair_n==1 and np.isclose(a.type_k_rate,11/51)
    assert a.affinity_whiff==.5
    assert cold.game3_pa_n==0 and np.isnan(cold.game3_contact)
    assert cold.pair_n==0 and cold.type_n==0 and cold.pair_k_rate==.2
    assert cold.arsenal_type=='unknown'
