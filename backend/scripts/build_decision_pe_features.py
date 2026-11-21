"""15.5.1/2: common-clock PA-prefix PE, personal references and forecast lineup."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_entry_review as entry

q=entry.q;ROOT=q.ROOT;OUT=ROOT/'data/research/decision_pe_features_v1'
OUTCOMES=list(q.b.OUTCOMES)
PE=['pe_cumulative_observed','pe_cumulative_coverage','pe_last1','pe_last2','pe_last3','pe_slope3',
    'prefix_strike_share','last3_whiff_rate','last3_hard_rate','ff_delta_prefix']
PERSONAL=['pe_entry_mean','pe_entry_n','pe3_personal_delta','ff_entry_mean','ff_entry_n','ff_delta_entry']
LINEUP=[f'forecast{slot}_{key}' for slot in [1,2,3] for key in ['log_n','nonout','extra_base','k','bb']]
BASE=q.base.CORE+q.base.STATE;CATS=q.base.FULLCAT+['phase']
FULLCAT=CATS+['lineup_status']
GROUPS={'base':BASE,'pe':BASE+PE,'full':BASE+PE+PERSONAL+LINEUP}


def read(path):return q.read(path)
def save(name,value):q.b.save_json(OUT/name,value)
def write(frame,name):frame.to_parquet(OUT/name,index=False,compression='zstd')


def outcome_group(event,outs_before,outs_after):
    result=pd.Series(np.where(outs_after.gt(outs_before).fillna(False),'other_out','other_reach'),index=event.index)
    for raw,group in [('strikeout','k'),('strikeout_double_play','k'),('walk','bb'),('hit_by_pitch','hbp'),('home_run','hr'),('single','single'),('double','double'),('triple','triple')]:result.loc[event.eq(raw)]=group
    return result.where(event.notna()&outs_before.notna()&outs_after.notna()&event.ne('intent_walk'))


def pe_score(frame):
    # PA-level proxy, deliberately not a reproduction of pitch-level PE.
    weights={'single':-.88,'double':-1.25,'triple':-1.58,'home_run':-2.03,'walk':-.69,'hit_by_pitch':-.72}
    event=frame.event_type;result=event.map(weights)
    out=frame.outs_after.gt(frame.outs_before)&~event.isin(['sac_fly','sac_fly_double_play'])
    result=result.fillna(pd.Series(np.where(out|event.isin(['strikeout','strikeout_double_play']),.5,0.),index=frame.index))
    count=.5*np.sign(frame.final_strikes-frame.final_balls)
    quality=pd.Series(np.where(frame.pa_ev_n.gt(0),np.where(frame.ev_mean.ge(95),-.5,np.where(frame.ev_mean.le(80),.5,0.)),0.),index=frame.index)
    known=frame.physical_actors.eq(1)&frame.actor_pitcher_id.eq(frame.pitcher_id)&frame.bad_timing.eq(0)&event.ne('intent_walk')&frame.final_strikes.notna()&frame.final_balls.notna()
    # No contact is not missing EV; fair contact lacking EV is unknown.
    known &= ~(frame.pa_fair_sum.gt(0)&~frame.pa_ev_n.gt(0))
    return (result+count+quality).where(known)


def cache(year):
    OUT.mkdir(exist_ok=True);print(f'15.5 {year}: closed PA events and physical FF/count measurements',flush=True)
    with q.n.r.connect() as c:
        c.read_parquet(str(q.n.r.OUT/f'pa_observations_{year}.parquet')).create_view('p')
        c.read_parquet(str(q.n.r.OUT/f'pitch_observations_{year}.parquet')).create_view('i')
        c.read_parquet(str(q.n.old.FOUNDATION/f'events_{year}.parquet')).create_view('events')
        frame=c.execute('''WITH counts AS(
            SELECT game_pk,at_bat_number,arg_max(balls_before,event_index) final_balls,arg_max(strikes_before,event_index) final_strikes
            FROM events WHERE is_pitch GROUP BY ALL), physical AS(
            SELECT game_pk,at_bat_number,appearance_id,
            sum(release_speed) FILTER(WHERE pitch_type='FF' AND release_speed>0) ff_sum,
            count(*) FILTER(WHERE pitch_type='FF' AND release_speed>0) ff_n,
            count(*) FILTER(WHERE description IN('ball','blocked_ball','pitchout')) balls_n,
            count(*) FILTER(WHERE description IN('called_strike','swinging_strike','swinging_strike_blocked','foul','foul_tip','foul_bunt','missed_bunt','bunt_foul_tip')) strikes_n
            FROM i WHERE time_reliable GROUP BY ALL)
            SELECT p.game_pk,p.at_bat_number,p.available_at,p.anchor_at pa_start,p.final_appearance_id appearance_id,p.final_pitcher_id pitcher_id,
            p.final_role AS role,p.actor_pitcher_id,p.physical_actors,p.bad_timing,p.event_type,p.outs_before,p.outs_after,p.actual_batter_id,
            p.home_score_before,p.away_score_before,p.home_score_after,p.away_score_after,p.half,
            p.pa_whiff_sum,p.pa_swing_sum,p.pa_fair_sum,p.pa_ev_sum,p.pa_ev_n,p.pa_ev_sum/nullif(p.pa_ev_n,0) ev_mean,
            counts.final_balls,counts.final_strikes,physical.ff_sum,physical.ff_n,physical.balls_n,physical.strikes_n
            FROM p LEFT JOIN counts USING(game_pk,at_bat_number)
            LEFT JOIN physical ON physical.game_pk=p.game_pk AND physical.at_bat_number=p.at_bat_number AND physical.appearance_id=p.final_appearance_id
            WHERE p.is_complete AND p.is_batter_faced AND p.available_at IS NOT NULL AND p.bad_timing=0
            AND p.final_role IN('SP','RP') AND p.final_appearance_id IS NOT NULL''').fetchdf()
    frame=frame.sort_values(['appearance_id','available_at','at_bat_number']).reset_index(drop=True)
    frame['pe']=pe_score(frame);frame['outcome']=outcome_group(frame.event_type,frame.outs_before,frame.outs_after)
    for col in ['pa_whiff_sum','pa_swing_sum','pa_fair_sum','pa_ev_sum','pa_ev_n','ff_sum','ff_n','balls_n','strikes_n']:frame[col]=pd.to_numeric(frame[col],errors='coerce')
    group=frame.groupby('appearance_id',sort=False)
    frame['pe_cumulative_observed']=frame.pe.fillna(0).groupby(frame.appearance_id).cumsum()
    frame['pe_known_count']=frame.pe.notna().groupby(frame.appearance_id).cumsum()
    frame['pe_cumulative_coverage']=frame.pe_known_count/(group.cumcount()+1)
    for window in [1,2,3]:frame[f'pe_last{window}']=group.pe.transform(lambda v:v.rolling(window,min_periods=window).sum())
    frame['pe_slope3']=((frame.pe-group.pe.shift(2))/2).where(frame.pe_last3.notna())
    for col in ['pa_whiff_sum','pa_swing_sum','pa_fair_sum']:
        frame[col+'_last3']=group[col].transform(lambda v:v.rolling(3,min_periods=3).sum())
    frame['last3_whiff_rate']=frame.pa_whiff_sum_last3/frame.pa_swing_sum_last3.replace(0,np.nan)
    frame['hard']=pd.Series(np.where(frame.pa_ev_n.gt(0),frame.ev_mean.ge(95),np.where(frame.pa_fair_sum.eq(0),0,np.nan)),index=frame.index)
    frame['last3_hard_rate']=frame.groupby('appearance_id').hard.transform(lambda v:v.rolling(3,min_periods=3).mean())
    ball=frame.balls_n.fillna(0).groupby(frame.appearance_id).cumsum();strike=frame.strikes_n.fillna(0).groupby(frame.appearance_id).cumsum()
    frame['prefix_strike_share']=strike/(ball+strike).replace(0,np.nan)
    frame['ff_mean']=frame.ff_sum/frame.ff_n.replace(0,np.nan)
    frame['ff_prefix_mean']=frame.ff_sum.fillna(0).groupby(frame.appearance_id).cumsum()/frame.ff_n.fillna(0).groupby(frame.appearance_id).cumsum().replace(0,np.nan)
    frame['ff_delta_prefix']=frame.ff_mean-frame.ff_prefix_mean
    write(frame,f'pa_cache_{year}.parquet');print(f'15.5 {year}: {len(frame):,} closed PA records; PE known {int(frame.pe.notna().sum()):,}',flush=True)


def references():
    f=pd.concat([pd.read_parquet(OUT/f'pa_cache_{year}.parquet') for year in range(2021,2025)],ignore_index=True)
    personal=f[f.pe.notna()].sort_values(['pitcher_id','role','available_at','game_pk','at_bat_number']).copy()
    g=personal.groupby(['pitcher_id','role'],sort=False)
    personal['pe_entry_mean']=g.pe.transform(lambda v:v.rolling(50,min_periods=10).mean())
    personal['pe_entry_n']=g.pe.transform(lambda v:v.rolling(50,min_periods=1).count())
    write(personal[['pitcher_id','role','available_at','pe_entry_mean','pe_entry_n']],'pe_personal.parquet')
    ff=f[f.ff_n.gt(0)&f.physical_actors.eq(1)].sort_values(['pitcher_id','role','available_at','game_pk','at_bat_number']).copy()
    g=ff.groupby(['pitcher_id','role'],sort=False)
    ff['ff_entry_mean']=g.ff_mean.transform(lambda v:v.rolling(50,min_periods=10).mean())
    ff['ff_entry_n']=g.ff_mean.transform(lambda v:v.rolling(50,min_periods=1).count())
    write(ff[['pitcher_id','role','available_at','ff_entry_mean','ff_entry_n']],'ff_personal.parquet')
    good=f[f.outcome.notna()&f.physical_actors.eq(1)].copy();good['day']=np.floor(good.available_at/86400)*86400
    counts=pd.crosstab(good.day,good.outcome).reindex(columns=OUTCOMES,fill_value=0).sort_index().cumsum()
    league=(counts+1).div(counts.sum(axis=1)+len(OUTCOMES),axis=0);league['available_at']=counts.index+86400
    write(league.reset_index(drop=True),'league_prior.parquet');print('15.5 entry-frozen personal references and previous-UTC-day league priors ready',flush=True)


def prepare(year):
    f=q.base.features(year).reset_index(drop=True)
    rp=pd.read_parquet(q.OUT/f'features_{year}.parquet',columns=['decision_id','usage_profile','monitor_unit'])
    f=f.merge(rp,on='decision_id',how='left',validate='one_to_one');f['usage_profile']=f.usage_profile.fillna('SP');f['monitor_unit']=f.monitor_unit.fillna(False).astype(bool)
    print(f'15.5 {year}: common anchor joins for {len(f):,} decisions',flush=True)
    with q.n.r.connect() as c:
        c.register('q',f);c.read_parquet(str(OUT/f'pa_cache_{year}.parquet')).create_view('p')
        c.read_parquet(str(OUT/'pe_personal.parquet')).create_view('pr');c.read_parquet(str(OUT/'ff_personal.parquet')).create_view('fr')
        c.read_parquet(str(q.n.r.OUT/f'pa_observations_{year}.parquet')).create_view('pa')
        c.read_parquet(str(q.b.PREP/f'clean_labels_{year}.parquet')).create_view('labels')
        c.execute('''CREATE TEMP TABLE lineup AS SELECT game_pk,half,coalesce(actual_batter_id,batter_id) actual_batter_id,
            coalesce(available_at,epoch(try_cast(end_time AS TIMESTAMPTZ))) available_at,
            row_number() OVER(PARTITION BY game_pk,half ORDER BY at_bat_number) seen_pa_count
            FROM pa WHERE is_complete AND is_batter_faced''')
        c.execute('CREATE TEMP TABLE slots AS SELECT *,((seen_pa_count-1)%9)+1 slot FROM lineup')
        joined=c.execute('''SELECT q.decision_id,p.available_at pe_available_at,'''+','.join('p.'+v for v in PE)+''',p.ff_mean last_ff,
            pr.available_at pe_reference_at,pr.pe_entry_mean,pr.pe_entry_n,fr.available_at ff_reference_at,fr.ff_entry_mean,fr.ff_entry_n,
            l.available_at lineup_available_at,coalesce(l.seen_pa_count,0) seen_pa_count
            FROM q ASOF LEFT JOIN p ON q.appearance_id=p.appearance_id AND q.anchor_at>p.available_at
            ASOF LEFT JOIN pr ON q.outgoing_pitcher_id=pr.pitcher_id AND q.role=pr.role AND q.entry_at>pr.available_at
            ASOF LEFT JOIN fr ON q.outgoing_pitcher_id=fr.pitcher_id AND q.role=fr.role AND q.entry_at>fr.available_at
            ASOF LEFT JOIN lineup l ON q.game_pk=l.game_pk AND q.half=l.half AND q.anchor_at>l.available_at''').fetchdf()
        f=f.merge(joined,on='decision_id',validate='one_to_one');f['pe3_personal_delta']=f.pe_last3/3-f.pe_entry_mean;f['ff_delta_entry']=f.last_ff-f.ff_entry_mean
        requests=pd.concat([f[['decision_id','game_pk','half','anchor_at','pitcher_hand','seen_pa_count']].assign(forecast_slot=slot,slot=(f.seen_pa_count+slot-1)%9+1) for slot in [1,2,3]],ignore_index=True)
        c.register('requests',requests)
        forecast=c.execute('''SELECT q.*,s.actual_batter_id forecast_batter_id,s.available_at forecast_identity_at
            FROM requests q ASOF LEFT JOIN slots s ON q.game_pk=s.game_pk AND q.half=s.half AND q.slot=s.slot AND q.anchor_at>s.available_at''').fetchdf()
        c.register('forecast',forecast);c.read_parquet(str(q.b.PREP/'ability_history.parquet')).filter("actor='batter' AND split='All'").create_view('bh')
        c.read_parquet(str(OUT/'league_prior.parquet')).create_view('league')
        columns=','.join('h.'+key+'_n,'+'g.'+key+' league_'+key for key in OUTCOMES)
        abilities=c.execute('''SELECT f.decision_id,f.forecast_slot,f.forecast_batter_id,f.forecast_identity_at,h.available_at batter_history_at,h.pa_n,
            g.available_at league_reference_at,'''+columns+''' FROM forecast f
            ASOF LEFT JOIN bh h ON f.forecast_batter_id=h.player_id AND f.anchor_at>h.available_at
            ASOF LEFT JOIN league g ON f.anchor_at>g.available_at''').fetchdf()
        labels=c.execute('''SELECT q.decision_id,p.anchor_at target_start,p.available_at target_available_at,p.actor_pitcher_id,p.final_pitcher_id,p.physical_actors,p.bad_timing,
            p.actual_batter_id actual_target_batter_id,l.organic_pa_eligible,l.observed_pa_result,l.outs label_outs,l.outs_after label_outs_after,
            p.home_score_after-p.home_score_before+p.away_score_after-p.away_score_before target_runs
            FROM q LEFT JOIN pa p USING(decision_id) LEFT JOIN labels l USING(decision_id)''').fetchdf()
    for slot in [1,2,3]:
        part=abilities[abilities.forecast_slot.eq(slot)].set_index('decision_id').loc[f.decision_id]
        count=part.pa_n.fillna(0).to_numpy(float);rates={}
        for key in OUTCOMES:
            prior=part['league_'+key].fillna(1/9).to_numpy(float)
            rates[key]=(part[key+'_n'].fillna(0).to_numpy(float)+20*prior)/(count+20)
        f[f'forecast{slot}_id']=part.forecast_batter_id.to_numpy();f[f'forecast{slot}_identity_at']=part.forecast_identity_at.to_numpy()
        f[f'forecast{slot}_history_at']=part.batter_history_at.to_numpy();f[f'forecast{slot}_league_at']=part.league_reference_at.to_numpy()
        f[f'forecast{slot}_log_n']=np.log1p(count)
        f[f'forecast{slot}_nonout']=1-rates['k']-rates['other_out'];f[f'forecast{slot}_extra_base']=rates['double']+rates['triple']+rates['hr']
        for key in ['k','bb']:f[f'forecast{slot}_{key}']=rates[key]
    f['lineup_status']=np.select([f.forecast1_id.isna(),f.forecast1_history_at.isna()],['slot_unobserved','forecast_without_own_history'],default='previous_slot_actor_forecast')
    f=f.merge(labels,on='decision_id',validate='one_to_one')
    observed=f.changed.eq(0)&f.organic_pa_eligible.fillna(False)&f.actor_pitcher_id.eq(f.outgoing_pitcher_id)&f.final_pitcher_id.eq(f.outgoing_pitcher_id)&f.physical_actors.eq(1)&f.bad_timing.eq(0)
    observed &= f.target_start.ge(f.anchor_at)&f.target_available_at.gt(f.target_start)&f.target_available_at.le(f.game_closed_at)
    group=outcome_group(f.observed_pa_result,f.label_outs,f.label_outs_after)
    observed=(observed&group.notna()&f.target_runs.between(0,4)).fillna(False).astype(bool)
    f['target_observed']=observed;f['y_pa']=group.map({key:i for i,key in enumerate(OUTCOMES)}).where(observed).astype(float)
    f['y_run']=f.target_runs.gt(0).where(observed).astype(float)
    for key in list(dict.fromkeys(GROUPS['full'])):f[key]=pd.to_numeric(f[key],errors='coerce').replace([np.inf,-np.inf],np.nan).astype(float)
    for key in FULLCAT:f[key]=f[key].astype('string').fillna('unknown').astype(str)
    for col,clock in [('pe_available_at','anchor_at'),('pe_reference_at','entry_at'),('ff_reference_at','entry_at'),('lineup_available_at','anchor_at')]+[(f'forecast{i}_{what}_at','anchor_at') for i in [1,2,3] for what in ['identity','history','league']]:
        known=f[col].notna();assert f.loc[known,col].lt(f.loc[known,clock]).all(),col
    write(f,f'features_{year}.parquet')
    coverage=[]
    for role in ['SP','RP']:
        part=f[f.role.eq(role)]
        coverage.append({'role':role,'n':len(part),'target_observed':int(part.target_observed.sum()),'missing_target':int((~part.target_observed).sum()),
            'feature_nonmissing':{key:int(part[key].notna().sum()) for key in PE+PERSONAL+LINEUP},
            'lineup_status':part.lineup_status.value_counts().to_dict(),
            'forecast_agreement_n':int((part.target_observed&part.forecast1_id.notna()).sum()),
            'forecast_agreement':int((part.target_observed&part.forecast1_id.eq(part.actual_target_batter_id)).sum())})
    save(f'coverage_{year}.json',{'year':year,'boundaries':len(f),'coverage':coverage,'dict_D':'load/recovery, not next batter; forecast identities are hypotheses from past slots, never certified next actors'})
    print(f'15.5 {year}: labels observed {int(observed.sum()):,}; forecast next-slot known {int(f.forecast1_id.notna().sum()):,}',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['cache','references','prepare']);parser.add_argument('--year',type=int,choices=range(2021,2025));args=parser.parse_args()
    if args.stage=='references':references()
    else:globals()[args.stage](args.year)
