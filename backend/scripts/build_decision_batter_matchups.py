"""Slice13.5: past completed-PA attack profiles and lagged repertoire matchups.

No same-season full-season tags, future lineup or current-PA responses in features.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import warnings

import numpy as np
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, SplineTransformer
from threadpoolctl import threadpool_limits

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_role_models as m

r, b = m.r, m.b
OUT = b.ROOT/'data/research/decision_batter_matchup_v1'
FAMILIES = ['fastball', 'breaking', 'offspeed']
FAMILY_SQL = "CASE WHEN pitch_type IN ('FF','FA','SI','FC') THEN 'fastball' WHEN pitch_type IN ('SL','ST','CU','KC','SV','CS') THEN 'breaking' WHEN pitch_type IN ('CH','FS','FO','SC','KN','EP') THEN 'offspeed' ELSE 'unknown' END"
SUMS = ['pitches','known','swings','whiffs','contacts','fouls','fair','ev_sum','ev_n','hard','balls_sum','strikes_sum','count_n','zone_sum','zone_n','stuff_sum','stuff_n','location_sum','location_n']
RATIOS = {'swing':('swings','known'), 'whiff':('whiffs','swings'), 'contact':('contacts','swings'),
          'foul':('fouls','swings'), 'fair':('fair','swings'), 'ev':('ev_sum','ev_n'), 'hard':('hard','ev_n')}


def save(name, value):
    b.save_json(OUT/name, value)


def publish(c, name, filename):
    c.table(name).write_parquet(str(OUT/filename), compression='zstd')


def sources():
    OUT.mkdir(parents=True, exist_ok=True)
    for year in r.YEARS:
        print(f'{year}: completed PA / pitch-family source statistics', flush=True)
        with r.connect() as c:
            c.read_parquet(str(r.OUT/f'pitch_observations_{year}.parquet')).create_view('o')
            c.read_parquet(str(r.OUT/f'pa_observations_{year}.parquet')).create_view('p')
            c.execute('CREATE TEMP TABLE identity AS SELECT game_pk,at_bat_number,count(DISTINCT batter_id) batters FROM o GROUP BY ALL')
            c.execute('''CREATE TABLE identity_exclusions AS SELECT p.outcome_key,p.game_pk,p.at_bat_number,p.batter_id,p.actual_batter_id,
                i.batters>1 multiple_physical_batters,p.actual_batter_id IS DISTINCT FROM p.batter_id batter_identity_mismatch,
                p.actor_pitcher_id IS DISTINCT FROM p.terminal_pitcher_id pitcher_identity_mismatch
                FROM p JOIN identity i USING(game_pk,at_bat_number)
                WHERE p.is_complete AND p.is_batter_faced AND NOT p.mid_pa_change AND p.physical_actors=1 AND p.bad_timing=0
                    AND (i.batters>1 OR p.actual_batter_id IS DISTINCT FROM p.batter_id OR p.actor_pitcher_id IS DISTINCT FROM p.terminal_pitcher_id)''')
            publish(c,'identity_exclusions',f'identity_exclusions_{year}.parquet')
            with m.r.connect() as raw:
                raw.execute(f"ATTACH '{(b.ROOT/f'data/MLB{year}/mlb_{year}.duckdb').as_posix()}' AS db (READ_ONLY)")
                frame = raw.execute("SELECT cast(game_pk AS VARCHAR)||'_'||cast(at_bat_number AS VARCHAR)||'_'||cast(pitch_number AS VARCHAR) pitch_uid,balls,strikes,plate_x,plate_z,sz_bot,sz_top FROM db.pitches WHERE game_type='R'").fetchdf()
            assert frame.pitch_uid.is_unique
            c.register('tracking', frame)
            c.execute(f"""CREATE TEMP TABLE z AS SELECT o.*,{FAMILY_SQL} AS family,t.balls,t.strikes,
                CASE WHEN isfinite(t.plate_x) AND isfinite(t.plate_z) AND isfinite(t.sz_bot) AND isfinite(t.sz_top) AND t.sz_top>t.sz_bot
                     THEN abs(t.plate_x)<=0.83 AND t.plate_z BETWEEN t.sz_bot AND t.sz_top END in_zone
                FROM o LEFT JOIN tracking t USING(pitch_uid) WHERE time_reliable AND alignment_status='validated_order'""")
            sums = """count(*) pitches,count(swing) known,sum(swing) swings,sum(whiff) whiffs,sum(contact) contacts,
                sum(foul) fouls,sum(fair) fair,sum(ev) ev_sum,count(ev) ev_n,count(*) FILTER(WHERE ev>=95) hard,
                sum(balls) balls_sum,sum(strikes) strikes_sum,count(balls+strikes) count_n,
                sum(cast(in_zone AS INTEGER)) zone_sum,count(in_zone) zone_n,
                sum(research_stuff_plus) stuff_sum,count(research_stuff_plus) stuff_n,
                sum(research_location_plus) location_sum,count(research_location_plus) location_n"""
            c.execute(f'CREATE TABLE family_stats AS SELECT year,game_pk,at_bat_number,family,{sums} FROM z GROUP BY ALL')
            publish(c,'family_stats',f'family_stats_{year}.parquet')
            columns=','.join(f"sum(s.{name}) FILTER(WHERE family='{family}') AS {family}_{name}" for family in FAMILIES+['unknown'] for name in SUMS)
            c.execute(f"""CREATE TABLE pa_stats AS SELECT p.year,p.game_pk,p.outcome_key,p.at_bat_number,p.batter_id,
                p.final_pitcher_id pitcher_id,p.final_role AS role,p.half,p.anchor_at,p.available_at,
                p.intentional_walk,p.event_type,p.outs_before,p.outs_after,
                {columns} FROM p LEFT JOIN family_stats s USING(year,game_pk,at_bat_number)
                LEFT JOIN identity i USING(game_pk,at_bat_number)
                WHERE p.is_complete AND p.is_batter_faced AND p.available_at IS NOT NULL AND p.final_pitcher_id IS NOT NULL
                    AND coalesce(p.bad_timing,0)=0 AND coalesce(p.physical_actors,1)=1 AND NOT p.mid_pa_change
                    AND ((p.zero_pitch AND coalesce(p.physical_pitches,0)=0) OR
                        (i.batters=1 AND p.actual_batter_id=p.batter_id AND p.actor_pitcher_id=p.terminal_pitcher_id))
                GROUP BY ALL""")
            assert c.execute('SELECT count(*)-count(DISTINCT outcome_key) FROM pa_stats').fetchone()[0]==0
            publish(c,'pa_stats',f'pa_stats_{year}.parquet')
    with r.connect() as c:
        c.execute(f"CREATE VIEW o AS SELECT *,{FAMILY_SQL} AS family FROM read_parquet('{(r.OUT/'pitch_observations_*.parquet').as_posix()}') WHERE time_reliable AND alignment_status='validated_order'")
        c.read_parquet(str(r.OUT/'appearance_history.parquet')).create_view('a')
        c.execute("""CREATE TABLE app AS SELECT a.pitcher_id,a.role,a.appearance_id,a.available_at,
            count(o.event_id) pitches,count(o.event_id) FILTER(WHERE family='fastball') fastball,
            count(o.event_id) FILTER(WHERE family='breaking') breaking,count(o.event_id) FILTER(WHERE family='offspeed') offspeed,
            sum(release_speed) FILTER(WHERE family='fastball') fast_velocity_sum,
            count(release_speed) FILTER(WHERE family='fastball') fast_velocity_n,
            arg_max(p_throws,o.available_at) hand
            FROM a LEFT JOIN o USING(appearance_id) WHERE a.available_at IS NOT NULL AND coalesce(a.bad_timing,0)=0 GROUP BY ALL""")
        fields=['pitches',*FAMILIES,'fast_velocity_sum','fast_velocity_n']
        c.execute('CREATE TABLE arsenal AS SELECT pitcher_id,role,appearance_id,available_at,hand,'+
            ','.join(f'sum({v}) OVER win {v}' for v in fields)+
            ' FROM app WINDOW win AS(PARTITION BY pitcher_id,role ORDER BY available_at,appearance_id ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)')
        arsenal=c.table('arsenal').fetchdf()
        for family in FAMILIES:arsenal[family+'_share']=arsenal[family]/arsenal.pitches.replace(0,np.nan)
        arsenal['fast_velocity']=arsenal.fast_velocity_sum/arsenal.fast_velocity_n.replace(0,np.nan)
        arsenal['arsenal_type']=classify_arsenal(arsenal)
        arsenal.to_parquet(OUT/'arsenal_history.parquet',index=False,compression='zstd')
    print('Past last-three closed-appearance repertoire histories published',flush=True)


def classify_arsenal(frame):
    shares=frame[[f+'_share' for f in FAMILIES]].fillna(-1)
    dominant=shares.idxmax(axis=1).str.removesuffix('_share').where(shares.max(axis=1)>=.5,'mixed')
    velocity=np.where(frame.fast_velocity.ge(95),'95plus',np.where(frame.fast_velocity.ge(90),'90to95',np.where(frame.fast_velocity.notna(),'under90','unknown')))
    value=frame.hand.fillna('unknown')+':'+dominant+':'+velocity
    return value.where(frame.pitches.ge(50)&frame.hand.isin(['L','R']),'unknown')


def histories():
    with r.connect() as c:
        c.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{(OUT/'pa_stats_*.parquet').as_posix()}')")
        c.read_parquet(str(OUT/'arsenal_history.parquet')).create_view('a')
        c.execute('''CREATE TABLE tagged AS SELECT p.*,coalesce(a.arsenal_type,'unknown') arsenal_type,a.available_at type_observed_at,
            a.hand pitcher_hand FROM p ASOF LEFT JOIN a ON p.pitcher_id=a.pitcher_id AND p.role=a.role AND p.anchor_at>a.available_at''')
        frame=c.table('tagged').fetchdf()
        frame['target']=b.label_code(frame.rename(columns={'event_type':'observed_pa_result','outs_before':'outs'}))
        c.register('tagged_frame',frame)
        # All learned outcome histories are terminally observed, non-IBB PAs; type tags were known before that PA.
        c.execute('CREATE TABLE eligible AS SELECT * FROM tagged_frame WHERE NOT intentional_walk AND anchor_at<available_at')
        for kind,keys,condition in [('pair',['batter_id','pitcher_id'],'true'),('type',['batter_id','arsenal_type'],"arsenal_type<>'unknown'")]:
            partition=','.join(keys)
            c.execute(f"CREATE TABLE {kind}_history AS SELECT {partition},outcome_key,available_at,count(*) OVER win pa_n,"+
                ','.join(f'sum(cast(target={i} AS INTEGER)) OVER win {key}_n' for i,key in enumerate(b.OUTCOMES))+
                f' FROM eligible WHERE {condition} WINDOW win AS(PARTITION BY {partition} ORDER BY available_at,outcome_key ROWS UNBOUNDED PRECEDING)')
            publish(c,kind+'_history',kind+'_history.parquet')
        c.execute(f"CREATE VIEW fam AS SELECT * FROM read_parquet('{(OUT/'family_stats_*.parquet').as_posix()}')")
        c.execute('''CREATE TABLE fp AS SELECT p.batter_id,p.pitcher_hand,p.available_at,p.outcome_key,s.* EXCLUDE(year,game_pk,at_bat_number)
            FROM tagged p JOIN fam s USING(game_pk,at_bat_number) WHERE p.anchor_at<p.available_at''')
        for kind,keys in [('batter_family',['batter_id','pitcher_hand','family']),('league_family',['pitcher_hand','family'])]:
            partition=','.join(keys)
            c.execute(f'CREATE TABLE {kind}_history AS SELECT {partition},available_at,outcome_key,'+
                ','.join(f'sum({v}) OVER win {v}' for v in SUMS)+
                f' FROM fp WINDOW win AS(PARTITION BY {partition} ORDER BY available_at,outcome_key ROWS UNBOUNDED PRECEDING)')
            publish(c,kind+'_history',kind+'_history.parquet')
    print('Strictly lagged BvP -> type -> batter-ability and pitch-family histories published',flush=True)


def attack_features(requests:pd.DataFrame,year:int) -> pd.DataFrame:
    """Generic actual-actor or nominal-option requests; no labels in return value."""
    q=requests[['request_id','decision_id','game_pk','decision_at','option_pitcher_id','option_role','batter_id','pitcher_hand','half',*[f'batter_{k}_rate' for k in b.OUTCOMES]]].copy()
    assert q.request_id.is_unique
    # Hundreds of explicit audit columns are assembled once, then serialized together.
    warnings.filterwarnings('ignore',category=pd.errors.PerformanceWarning)
    print(f'{year}: attack features {len(q):,} requests; repertoire/BvP/type histories',flush=True)
    with r.connect() as c:
        c.register('q',q)
        c.read_parquet(str(OUT/'arsenal_history.parquet')).create_view('arsenal')
        result=c.execute('''SELECT q.request_id,a.available_at arsenal_observed_at,a.pitches arsenal_n,
            a.fastball_share,a.breaking_share,a.offspeed_share,a.fast_velocity,coalesce(a.arsenal_type,'unknown') arsenal_type
            FROM q ASOF LEFT JOIN arsenal a ON q.option_pitcher_id=a.pitcher_id AND q.option_role=a.role AND q.decision_at>a.available_at''').fetchdf().set_index('request_id').reindex(q.request_id)
        result.index.name='request_id'
        c.register('arsenal_requests',q.merge(result.reset_index(),on='request_id',validate='one_to_one'))
        for kind,keys in [('type',['batter_id','arsenal_type']),('pair',['batter_id','pitcher_id'])]:
            c.read_parquet(str(OUT/(kind+'_history.parquet'))).create_view('h',replace=True)
            conditions=' AND '.join('q.'+('option_pitcher_id' if k=='pitcher_id' else k)+'=h.'+k for k in keys)
            frame=c.execute('SELECT q.request_id,h.available_at AS '+kind+'_observed_at,h.pa_n AS '+kind+'_n,'+
                ','.join(f'h.{key}_n AS {kind}_{key}_count' for key in b.OUTCOMES)+
                f' FROM arsenal_requests q ASOF LEFT JOIN h ON {conditions} AND q.decision_at>h.available_at').fetchdf().set_index('request_id').reindex(q.request_id)
            result=result.join(frame)
        for i,key in enumerate(b.OUTCOMES):
            prior=q[f'batter_{key}_rate'].to_numpy(dtype=float)
            tn=result.type_n.fillna(0).to_numpy();pn=result.pair_n.fillna(0).to_numpy()
            result[f'type_{key}_rate']=(result[f'type_{key}_count'].fillna(0).to_numpy()+50*prior)/(tn+50)
            result[f'pair_{key}_rate']=(result[f'pair_{key}_count'].fillna(0).to_numpy()+20*result[f'type_{key}_rate'])/(pn+20)
        c.read_parquet(str(OUT/f'pa_stats_{year}.parquet')).create_view('h',replace=True)
        scopes={'game': 'h.batter_id=q.batter_id','pair_game':'h.batter_id=q.batter_id AND h.pitcher_id=q.option_pitcher_id',
                'other_game':'h.batter_id=q.batter_id AND h.pitcher_id<>q.option_pitcher_id',
                'team':'h.half=q.half AND h.pitcher_id=q.option_pitcher_id'}
        for scope,condition in scopes.items():
            print(f'{year}: completed-PA attack scope {scope}',flush=True)
            # Ranking occurs on full PAs, including zero-pitch IBBs; rates use only their measured pitches.
            c.execute(f'''CREATE OR REPLACE TEMP TABLE recent AS SELECT q.request_id,h.*,
                row_number() OVER(PARTITION BY q.request_id ORDER BY h.available_at DESC,h.outcome_key DESC) rn
                FROM q JOIN h ON q.game_pk=h.game_pk AND {condition} AND q.decision_at>h.available_at
                QUALIFY rn<=3''')
            windows=[1,2,3] if scope=='game' else [3]
            for window in windows:
                prefix=f'{scope}{window}'
                names=[f'{family}_{s}' for family in FAMILIES+['unknown'] for s in SUMS]
                values=c.execute('SELECT request_id,count(*) '+prefix+'_pa_n,max(available_at) '+prefix+'_observed_at,'+
                    ','.join(f'coalesce(sum({name}),0) {name}' for name in names)+f' FROM recent WHERE rn<={window} GROUP BY request_id').fetchdf().set_index('request_id').reindex(q.request_id)
                result[prefix+'_pa_n']=values[prefix+'_pa_n'].fillna(0)
                result[prefix+'_observed_at']=values[prefix+'_observed_at']
                physical=sum(values[f+'_pitches'].fillna(0) for f in FAMILIES+['unknown'])
                swings=sum(values[f+'_swings'].fillna(0) for f in FAMILIES+['unknown'])
                for family in FAMILIES:
                    stem=f'{prefix}_{family}'
                    for s in ['pitches','known','swings','ev_n']:result[f'{stem}_{s}']=values[f'{family}_{s}'].fillna(0)
                    result[stem+'_received_share']=values[family+'_pitches']/physical.replace(0,np.nan)
                    result[stem+'_swing_share']=values[family+'_swings']/swings.replace(0,np.nan)
                    for metric,(num,den) in RATIOS.items():
                        result[f'{stem}_{metric}']=values[f'{family}_{num}']/values[f'{family}_{den}'].replace(0,np.nan)
                result[prefix+'_pitches']=physical
                for metric,(num,den) in RATIOS.items():
                    numerator=sum(values[f+'_'+num].fillna(0) for f in FAMILIES+['unknown'])
                    denominator=sum(values[f+'_'+den].fillna(0) for f in FAMILIES+['unknown'])
                    result[prefix+'_'+metric]=numerator/denominator.replace(0,np.nan)
        # Historical family behavior is weighted by the option's past repertoire; zero own support is a backoff, not a zero rate.
        family_frames={}
        for family in FAMILIES:
            print(f'{year}: lagged family affinity {family}',flush=True)
            c.execute(f"CREATE OR REPLACE TEMP VIEW fq AS SELECT *, '{family}' AS family FROM arsenal_requests")
            for kind in ['batter_family','league_family']:
                c.read_parquet(str(OUT/(kind+'_history.parquet'))).create_view('h',replace=True)
                own='q.batter_id=h.batter_id AND ' if kind=='batter_family' else ''
                cols=[s for s in SUMS if s in set(sum(([a,z] for a,z in RATIOS.values()),[]))]
                frame=c.execute('SELECT q.request_id,h.available_at,'+','.join('h.'+s for s in cols)+
                    f' FROM fq q ASOF LEFT JOIN h ON {own}q.pitcher_hand=h.pitcher_hand AND q.family=h.family AND q.decision_at>h.available_at').fetchdf().set_index('request_id').reindex(q.request_id)
                family_frames[(family,kind)]=frame
            own=family_frames[(family,'batter_family')];league=family_frames[(family,'league_family')]
            result[family+'_history_at']=own.available_at
            result[family+'_reference_at']=league.available_at
            result[family+'_history_swings']=own.swings.fillna(0)
            for metric,(num,den) in RATIOS.items():
                prior=league[num]/league[den].replace(0,np.nan)
                strength=10 if metric=='ev' else 20
                result[f'affinity_{family}_{metric}']=(own[num].fillna(0)+strength*prior)/(own[den].fillna(0)+strength)
        for metric in RATIOS:
            weights=result[[f+'_share' for f in FAMILIES]].to_numpy(dtype=float)
            rates=result[[f'affinity_{f}_{metric}' for f in FAMILIES]].to_numpy(dtype=float)
            usable=np.isfinite(rates)&np.isfinite(weights);support=np.where(usable,weights,0).sum(axis=1)
            numerator=np.where(usable,weights*rates,0).sum(axis=1)
            result['affinity_'+metric]=np.divide(numerator,support,out=np.full(len(q),np.nan),where=support>=.8)
            result['affinity_'+metric+'_mix_support']=support
        for scope in scopes:
            for metric in ['whiff','contact','ev']:
                weights=result[[f+'_share' for f in FAMILIES]].to_numpy(dtype=float)
                rates=result[[f'{scope}3_{f}_{metric}' for f in FAMILIES]].to_numpy(dtype=float)
                ok=np.isfinite(weights)&np.isfinite(rates);support=np.where(ok,weights,0).sum(axis=1)
                result[f'{scope}3_mix_{metric}']=np.divide(np.where(ok,weights*rates,0).sum(axis=1),support,out=np.full(len(q),np.nan),where=support>=.8)
        result['game_contact_change']=result.game1_contact-result.game3_contact
        result['game_whiff_change']=result.game1_whiff-result.game3_whiff
        for n in ['type_n','pair_n']:result[n]=result[n].fillna(0)
        times=[n for n in result if n.endswith(('_observed_at','_history_at','_reference_at'))]
        assert not result[times].ge(q.decision_at.to_numpy(),axis=0).any().any()
        return result.reset_index()


def features(year):
    f=pd.read_parquet(r.OUT/f'observed_features_{year}.parquet')
    f['request_id']=f.decision_id
    result=attack_features(f,year)
    result.to_parquet(OUT/f'observed_attack_{year}.parquet',index=False,compression='zstd')
    coverage=[]
    for role,g in f.groupby('option_role'):
        z=result.set_index('request_id').loc[g.request_id]
        coverage.append({'role':role,'n':len(z),'same_game_pa':int(z.game3_pa_n.gt(0).sum()),
            'same_pitcher_pa':int(z.pair_game3_pa_n.gt(0).sum()),'historical_pair':int(z.pair_n.gt(0).sum()),
            'known_type':int(z.arsenal_type.ne('unknown').sum()),'type_own_pa':int(z.type_n.gt(0).sum()),
            'affinity_whiff':int(z.affinity_whiff.notna().sum())})
    save(f'features_{year}.json',{'year':year,'rows':len(result),'coverage':coverage,'time_violations':0,
        'scope':'actual observed actor; prior completed PAs only; same-game, exact pair, other pitchers, team and historical family/type scopes remain distinct'})
    print(f'{year}: {len(result):,} strictly past attack/matchup requests published',flush=True)


def protocol():
    paths=[Path(__file__),Path(m.__file__),OUT/'arsenal_history.parquet',r.OUT/'protocol.json']
    paths += [OUT/(k+'_history.parquet') for k in ['pair','type','batter_family','league_family']]
    paths += [OUT/f'observed_attack_{y}.parquet' for y in r.YEARS]
    paths += [OUT/f'{kind}_{y}.parquet' for y in r.YEARS for kind in ['pa_stats','family_stats']]
    paths += [OUT/f'identity_exclusions_{y}.parquet' for y in r.YEARS]
    paths += [r.OUT/f'curve_cohort_{y}.parquet' for y in range(2021,2025)]
    return {'version':'decision_batter_matchup_v1','protocol_revision':2,
        'superseded_protocol_sha256':b.digest(OUT/'attempt1_pa_identity_unfiltered/protocol.json'),
        'identity_revision':'Exclude multiple physical batters or inconsistent physical/official batter/pitcher; retain zero-pitch IBB as PA with0 pitches.110 conflicted completed PA across6 seasons logged; prior experiment/source preserved before outcome-based selection.',
        'input_sha256':{str(p.relative_to(b.ROOT)):b.digest(p) for p in paths},
        'families':FAMILIES,'pitch_family_sql':FAMILY_SQL,'attack_windows':[1,2,3],
        'clocks':'Prior fully completed PAs available strictly before decision; no current PA partial swings or future lineup. Raw outcomes and counts retain valid denominators.',
        'scopes':['same-game batter last1/2/3 PA','same-game exact pair last3','same-game other pitchers last3','same-game team vs option last3','historical exact BvP','historical lagged repertoire type','historical pitch family x hand'],
        'type':'last3 closed appearances same role, >=50 pitches; dominant family >=.5 else mixed; hand x family x fastball velocity (<90/90-95/95+); fixed descriptive bins, not learned optimal tags',
        'shrinkage':'BvP strength20 -> own type strength50 -> strictly past batter-hand ability; family rates strength20 valid denominators (EV10 BBE) -> strictly past hand/family league; n/backoff remain explicit',
        'association':'2021-23 nuisance fits,2024 descriptive conditional validation; repeated batter encounters and actual prior pitch exposure separated; current-response count/location/quality controls only in descriptive analysis',
        'limits':'Swing composition is not psychological targeting. Conditional familiarity association is not causal. Pitch family categories are broad, not validated optimal matchups.',
        'test_outcome_metrics_examined':False,'recommendation_allowed':False}


def freeze():
    value=protocol();path=OUT/'protocol.json'
    if path.exists() and json.loads(path.read_text('utf-8'))!=value:raise ValueError('Frozen matchup experiment differs; preserve it before explicit revision')
    save('protocol.json',value);print('13.5 protocol frozen',flush=True)


def association_curve(frame,residual,axis):
    bins=np.minimum(frame.same_batter_encounter.to_numpy(),4) if axis=='encounter' else np.digitize(frame.pitches_seen_by_batter_before,[1,6,11,21])
    f=frame[['game_pk','pitcher_id','appearance_id']].copy();f['bin']=bins;f['residual']=residual
    f['w']=1/f.groupby(['appearance_id','bin']).appearance_id.transform('count')
    levels=np.sort(f.bin.unique());codes=np.searchsorted(levels,f.bin);w=f.w.to_numpy();v=f.residual.to_numpy()
    point=np.bincount(codes,weights=w*v)/np.bincount(codes,weights=w)
    games,_=pd.factorize(f.game_pk);pitchers,_=pd.factorize(f.pitcher_id);rng=np.random.default_rng(m.SEED)
    boot=[]
    for _ in range(200):
        weights=w*rng.poisson(1,games.max()+1)[games]*rng.poisson(1,pitchers.max()+1)[pitchers]
        den=np.bincount(codes,weights=weights,minlength=len(levels));num=np.bincount(codes,weights=weights*v,minlength=len(levels))
        boot.append(np.divide(num,den,out=np.full(len(levels),np.nan),where=den>0))
    delta=point-point[0];boot=np.array(boot);boot-=boot[:,[0]];se=np.nanstd(boot,axis=0,ddof=1)
    support=f.groupby('bin').agg(n=('bin','size'),appearances=('appearance_id','nunique'),pitchers=('pitcher_id','nunique'))
    valid=support.n.ge(200).to_numpy()&support.appearances.ge(50).to_numpy()&support.pitchers.ge(30).to_numpy()&(se>1e-12)
    critical=float(np.nanquantile(np.nanmax(np.abs((boot[:,valid]-delta[valid])/se[valid]),axis=1),.95)) if valid.any() else 1.96
    return [{'bin':int(level),'n':int(support.loc[level,'n']),'appearances':int(support.loc[level,'appearances']),
        'pitchers':int(support.loc[level,'pitchers']),'delta':float(delta[i]),'low95':float(delta[i]-critical*se[i]),
        'high95':float(delta[i]+critical*se[i]),'supported':bool(support.loc[level,'n']>=200 and support.loc[level,'appearances']>=50 and support.loc[level,'pitchers']>=30)} for i,level in enumerate(levels)]


def associations():
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    frames=[]
    for year in range(2021,2025):
        f=pd.read_parquet(r.OUT/f'curve_cohort_{year}.parquet')
        stats=pd.read_parquet(OUT/f'pa_stats_{year}.parquet').set_index('outcome_key').reindex(f.outcome_key)
        for name,num,den in [('response_balls','balls_sum','count_n'),('response_strikes','strikes_sum','count_n'),('response_zone','zone_sum','zone_n')]:
            numerator=sum(stats[family+'_'+num].fillna(0).to_numpy() for family in FAMILIES+['unknown'])
            denominator=sum(stats[family+'_'+den].fillna(0).to_numpy() for family in FAMILIES+['unknown'])
            f[name]=np.divide(numerator,denominator,out=np.full(len(f),np.nan),where=denominator>0)
        f['contact_rate']=1-f.whiff_rate
        frames.append(f)
    all_frame=pd.concat(frames,ignore_index=True);panels=[]
    numeric=m.CURVE_CONTROL_NUM+['pitches_before','response_balls','response_strikes','response_zone','stuff','location_value']
    categorical=m.CURVE_CONTROL_CAT
    with threadpool_limits(limits=2):
        for role in ['SP','RP']:
            for metric in ['contact_rate','whiff_rate','ev']:
                t=all_frame[all_frame.year.lt(2024)&all_frame.role.eq(role)&all_frame[metric].notna()]
                v=all_frame[all_frame.year.eq(2024)&all_frame.role.eq(role)&all_frame[metric].notna()]
                print(f'13.5 conditional association {role}/{metric}: {len(t):,}/{len(v):,}',flush=True)
                transform=ColumnTransformer([('numeric',make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler()),numeric),
                    ('count_spline',make_pipeline(SimpleImputer(strategy='median'),SplineTransformer(n_knots=4,degree=2,include_bias=False)),['pitches_before']),
                    ('categorical',OneHotEncoder(handle_unknown='ignore',sparse_output=True),categorical)],sparse_threshold=1.)
                fit=make_pipeline(transform,Ridge(alpha=100.,solver='lsqr',max_iter=200,tol=1e-4))
                weights=1/t.groupby('appearance_id').outcome_key.transform('count').to_numpy();weights/=weights.mean()
                fit.fit(m.clean_design(t,numeric,categorical),t[metric],ridge__sample_weight=weights)
                rt=t[metric].to_numpy()-fit.predict(m.clean_design(t,numeric,categorical));rv=v[metric].to_numpy()-fit.predict(m.clean_design(v,numeric,categorical))
                joblib.dump(fit,OUT/f'association_{role}_{metric}.joblib')
                for axis in ['encounter','prior_physical_pitches']:
                    panels.append({'role':role,'metric':metric,'axis':axis,'training':association_curve(t,rt,axis),
                        'validation_2024':association_curve(v,rv,axis)})
    save('familiarity_associations.json',{'version':'decision_batter_matchup_v1','panels':panels,
        'controls':'pitch count, prior batter ability, identities/hand/date/context, response pitch-family mix, balls/strikes/zone and research Plus; response controls are diagnostic only, never prediction inputs',
        'pitch_bins':['0','1-5','6-10','11-20','21+'],'interval':'200 game x pitcher bootstrap, simultaneous95 within panel, nuisance fit fixed; cross-panel comparisons exploratory',
        'scope':'observed retained pitchers; no causal familiarity or psychological-targeting claim; no test outcome metrics'})


def finalize():
    assert json.loads((OUT/'protocol.json').read_text('utf-8'))==protocol()
    report={'version':'decision_batter_matchup_v1','protocol_sha256':b.digest(OUT/'protocol.json'),
        'years':[json.loads((OUT/f'features_{y}.json').read_text('utf-8')) for y in r.YEARS],
        'associations':json.loads((OUT/'familiarity_associations.json').read_text('utf-8')),
        'recommendation_allowed':False,'test_outcome_metrics_examined':False}
    save('summary.json',report);b.save_json(b.ROOT/'data/sample/petehub_pitcher_decision_slice13_5_v1.json',report)
    files=[p for p in OUT.rglob('*') if p.is_file() and p.name!='manifest.json']
    save('manifest.json',{'version':'decision_batter_matchup_v1','files':[{'path':p.relative_to(OUT).as_posix(),'bytes':p.stat().st_size,'sha256':b.digest(p)} for p in sorted(files)]})
    print('13.5 evidence published',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['sources','histories','features','freeze','associations','finalize']);parser.add_argument('--year',type=int,choices=r.YEARS)
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if args.stage=='features':
        for year in [args.year] if args.year else r.YEARS:features(year)
    else:globals()[args.stage]()
