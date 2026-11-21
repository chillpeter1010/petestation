"""Slices 13.1-13.3: versioned, strictly-past workload and role observations.

Old research artifacts are inputs only. No browser or formal model writes.
"""
from __future__ import annotations

import argparse
from datetime import timedelta
import gzip
import json
from pathlib import Path
import sys

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_baselines as b

OUT=b.ROOT/'data/research/decision_role_observation_v2'
BASE=b.ROOT/'data/research/decision_support_pipeline_20261114'
YEARS=range(2021,2027)
WINDOWS=(1,3,5,7,14)
MEASURES=['research_stuff_plus','research_location_plus','release_speed','release_spin_rate',
          'pfx_x','pfx_z','release_pos_x','release_pos_z','release_extension','arm_angle']
FLAGS=['swing','whiff','contact','called_strike','csw','foul','fair','ev','angle']
SWINGS={'swinging_strike','swinging_strike_blocked','foul','foul_tip','hit_into_play','foul_bunt','missed_bunt','bunt_foul_tip'}
WHIFFS={'swinging_strike','swinging_strike_blocked','missed_bunt'}
FOULS={'foul','foul_tip','foul_bunt','bunt_foul_tip'}


def connect():
    return duckdb.connect(config={'threads':1,'memory_limit':'2GB','preserve_insertion_order':False})


def save(name: str,value) -> None:
    b.save_json(OUT/name,value)


def publish(c,name: str,path: Path) -> None:
    temporary=path.with_suffix('.tmp.parquet')
    c.table(name).write_parquet(str(temporary),compression='zstd');temporary.replace(path)


def fold_at(values: np.ndarray) -> np.ndarray:
    result=np.full(len(values),'warmup',dtype=object)
    for fold in b.FOLDS:
        start=pd.Timestamp(fold['score_start'],tz='UTC').timestamp();end=pd.Timestamp(fold['score_end'],tz='UTC').timestamp()
        result[(values>=start)&(values<end)]=fold['id']
    return result


def pitch_flags(description: pd.Series,ev: pd.Series,angle: pd.Series) -> pd.DataFrame:
    known=description.notna()
    swing=description.isin(SWINGS);whiff=description.isin(WHIFFS);fair=description.eq('hit_into_play')
    result=pd.DataFrame({'swing':swing,'whiff':whiff,'contact':swing&~whiff,
        'called_strike':description.eq('called_strike'),'csw':whiff|description.eq('called_strike'),
        'foul':description.isin(FOULS),'fair':fair,
        'ev':pd.to_numeric(ev,errors='coerce').where(fair),
        'angle':pd.to_numeric(angle,errors='coerce').where(fair)})
    for name in FLAGS[:7]:result[name]=result[name].astype(float).where(known)
    result['ev']=result.ev.where(np.isfinite(result.ev)&result.ev.gt(0))
    result['angle']=result.angle.where(np.isfinite(result.angle))
    return result


def sources() -> None:
    with connect() as c:
        c.execute(f"CREATE VIEW e AS SELECT * FROM read_parquet('{(BASE/'events_*.parquet').as_posix()}')")
        c.execute(f"CREATE VIEW a AS SELECT * FROM read_parquet('{(BASE/'appearances_*.parquet').as_posix()}')")
        c.execute("""CREATE TABLE physical AS WITH timed AS (
            SELECT e.year,e.game_pk,e.appearance_id,e.pitcher_id,e.batter_id,e.at_bat_number,e.event_id,e.event_index,
                a.role,epoch(try_cast(e.event_time AS TIMESTAMPTZ)) started_at,
                epoch(try_cast(e.end_time AS TIMESTAMPTZ)) ended_at,
                epoch(try_cast(e.end_time AS TIMESTAMPTZ))>=epoch(try_cast(e.event_time AS TIMESTAMPTZ)) time_reliable
            FROM e JOIN a USING(appearance_id) WHERE e.is_pitch AND e.pitcher_id IS NOT NULL),
            lagged AS(SELECT *,greatest(started_at,ended_at) available_at,
                lag(greatest(started_at,ended_at)) OVER(PARTITION BY appearance_id ORDER BY started_at,event_index) prior_at FROM timed),
            blocks AS(SELECT *,sum(CASE WHEN prior_at IS NULL OR available_at-prior_at>28800 THEN 1 ELSE 0 END)
                OVER(PARTITION BY appearance_id ORDER BY started_at,event_index) session_no FROM lagged)
            SELECT *,appearance_id||':'||session_no session_id,
                row_number() OVER(PARTITION BY appearance_id ORDER BY started_at,event_index) appearance_pitch_position,
                row_number() OVER(PARTITION BY appearance_id,session_no ORDER BY started_at,event_index) session_pitch_position,
                cast(to_timestamp(available_at) AT TIME ZONE 'America/New_York' AS DATE) pitch_day
            FROM blocks""")
        assert c.execute('SELECT count(*)-count(DISTINCT event_id) FROM physical').fetchone()[0]==0
        publish(c,'physical',OUT/'physical_history.parquet')
        c.execute("""CREATE TABLE appearances AS SELECT a.*,epoch(try_cast(entry_time AS TIMESTAMPTZ)) entry_at,
            epoch(try_cast(exit_time AS TIMESTAMPTZ)) exit_at,
            greatest(epoch(try_cast(exit_time AS TIMESTAMPTZ)),p.last_observed_at) available_at,
            p.last_observed_at,p.actual_pitches,p.bad_timing,
            cast(try_cast(entry_time AS TIMESTAMPTZ) AT TIME ZONE 'America/New_York' AS DATE) entry_day
            FROM a LEFT JOIN(SELECT appearance_id,max(available_at) last_observed_at,count(*) actual_pitches,
                count(*) FILTER(WHERE NOT time_reliable) bad_timing FROM physical GROUP BY appearance_id) p USING(appearance_id)""")
        publish(c,'appearances',OUT/'appearance_history.parquet')
        report={'physical_rows':c.execute('SELECT count(*) FROM physical').fetchone()[0],
            'unreliable_end_clock':c.execute('SELECT count(*) FROM physical WHERE NOT time_reliable').fetchone()[0],
            'appearance_rows':c.execute('SELECT count(*) FROM appearances').fetchone()[0],
            'clock':'completed pitch end, strict < cutoff; unreliable timing flagged, not silently treated as complete'}
        save('source_audit.json',report)
        for year in YEARS:
            print(f'{year}: source observations and raw outcome support',flush=True)
            c.read_parquet(str(b.TEMPORAL/f'alignment_{year}.parquet')).create_view('aligned',replace=True)
            c.execute(f"CREATE OR REPLACE VIEW scored AS SELECT * FROM read_parquet('{(b.TEMPORAL/f'scored_{year}_*.parquet').as_posix()}')")
            with duckdb.connect(str(b.ROOT/f'data/MLB{year}/mlb_{year}.duckdb'),read_only=True) as raw:
                frame=raw.execute("SELECT cast(game_pk AS VARCHAR)||'_'||cast(at_bat_number AS VARCHAR)||'_'||cast(pitch_number AS VARCHAR) pitch_uid,description,launch_speed,launch_angle FROM pitches WHERE game_type='R'").fetchdf()
            assert frame.pitch_uid.is_unique
            flags=pitch_flags(frame.description,frame.launch_speed,frame.launch_angle)
            frame=pd.concat([frame[['pitch_uid','description']],flags],axis=1)
            c.register('raw_flags',frame)
            columns=','.join(f'z.{m}' for m in MEASURES[2:])
            flag_columns=','.join(f'r.{name}' for name in FLAGS)
            c.execute(f"""CREATE OR REPLACE TABLE observations AS SELECT p.*,z.pitch_uid,z.pitch_type,z.stand,z.p_throws,
                z.alignment_status,{columns},s.research_stuff_plus,s.research_location_plus,s.plus_model_id,s.plus_train_cutoff,
                r.description,{flag_columns}
                FROM physical p LEFT JOIN aligned z ON z.event_id=p.event_id AND z.alignment_status='validated_order'
                    AND z.pitcher=p.pitcher_id AND z.batter=p.batter_id
                LEFT JOIN scored s ON s.event_id=p.event_id AND s.source_valid AND s.roster_pitcher AND s.alignment_status='validated_order'
                LEFT JOIN raw_flags r ON r.pitch_uid=z.pitch_uid WHERE p.year={year}""")
            assert c.execute('SELECT count(*) FROM observations WHERE plus_train_cutoff>available_at').fetchone()[0]==0
            publish(c,'observations',OUT/f'pitch_observations_{year}.parquet')
            c.unregister('raw_flags')
            del frame,flags
        print('Physical, appearance and aligned observations published',flush=True)


def lineups() -> None:
    records=[];audit=[]
    with connect() as c:
        for year in YEARS:
            rows=c.read_parquet(str(b.ROOT/f'data/research/decision_support_slice1_20261112/feed_inventory_{year}.parquet')).fetchdf()
            missing=0
            for i,row in enumerate(rows.itertuples()):
                payload=json.loads(gzip.decompress(Path(row.path).read_bytes()))
                for side in ('away','home'):
                    team=payload['liveData']['boxscore']['teams'][side]
                    for player in team.get('players',{}).values():
                        order=player.get('battingOrder')
                        if not order:continue
                        slot=int(order)//100
                        if 1<=slot<=9:records.append({'year':year,'game_pk':row.game_pk,'batter_id':int(player['person']['id']),
                            'batting_slot':slot,'source':'archived_boxscore_slot_for_observed_batter_only'})
                if (i+1)%500==0:print(f'{year}: lineup attributes {i+1}/{len(rows)}',flush=True)
            audit.append({'year':year,'games':len(rows),'missing_files':missing})
    frame=pd.DataFrame(records).drop_duplicates()
    conflict=frame.duplicated(['game_pk','batter_id'],keep=False)
    conflicts=frame.loc[conflict]
    frame=frame.loc[~conflict]
    frame.to_parquet(OUT/'lineup_slots.parquet',index=False,compression='zstd')
    conflicts.to_parquet(OUT/'lineup_slot_conflicts.parquet',index=False,compression='zstd')
    save('lineup_audit.json',{'years':audit,'conflicted_rows':len(conflicts),
        'boundary':'Archived slot may be revised; use only the currently observed batter, never future lineup names/substitutions'})


def prior_streak(day_ordinal: int,observed_days: set[int]) -> int:
    count=0;previous=day_ordinal-1
    while previous in observed_days:count+=1;previous-=1
    return count


def window_counts(times: np.ndarray,cutoffs: np.ndarray,days: int) -> np.ndarray:
    return np.searchsorted(times,cutoffs,side='left')-np.searchsorted(times,cutoffs-days*86400,side='left')


def workload(year: int) -> None:
    with connect() as c:
        c.read_parquet(str(OUT/'physical_history.parquet')).create_view('p')
        history=c.execute('SELECT year,game_pk,pitcher_id,available_at,time_reliable,pitch_day FROM p WHERE year<=? ORDER BY pitcher_id,available_at,event_id',[year]).fetchdf()
        c.read_parquet(str(OUT/'appearance_history.parquet')).create_view('a')
        appearances=c.execute('SELECT * FROM a WHERE year<=? ORDER BY pitcher_id,entry_at,appearance_id',[year]).fetchdf()
        c.read_parquet(str(b.OUT/f'option_features_{year}.parquet')).create_view('o')
        requests=c.execute('SELECT decision_id,game_pk,decision_at,option_pitcher_id,is_current,option_role,role_known,consecutive_days legacy_streak FROM o').fetchdf()
        c.read_parquet(str(b.PREP/f'prepared_features_{year}.parquet')).create_view('f')
        requests=requests.merge(c.execute('SELECT decision_id,appearance_id,history_status FROM f').fetchdf(),on='decision_id',validate='many_to_one')
    earliest=float(history.available_at.min())
    by_pitch={pid:g for pid,g in history.groupby('pitcher_id',sort=False)}
    by_app={pid:g for pid,g in appearances.groupby('pitcher_id',sort=False)}
    out=[];changed=0
    for pid,q in requests.groupby('option_pitcher_id',sort=False):
        q=q.reset_index(drop=True);t=q.decision_at.to_numpy(dtype=float);n=len(q)
        h=by_pitch.get(pid,history.iloc[:0]);apps=by_app.get(pid,appearances.iloc[:0])
        times=h.available_at.to_numpy(dtype=float);ends=np.searchsorted(times,t,side='left')
        days=pd.to_datetime(q.decision_at,unit='s',utc=True).dt.tz_convert('America/New_York').dt.date
        ordinals=np.array([d.toordinal() for d in days]);known_days={d.toordinal() for d in h.pitch_day.dt.date}
        streak_map={d:prior_streak(int(d),known_days) for d in np.unique(ordinals)}
        observed_streak=np.array([streak_map[d] for d in ordinals],dtype=float)
        bad=np.r_[0,np.cumsum(~h.time_reliable.to_numpy(dtype=bool))]
        before14=np.searchsorted(times,t-14*86400,side='left')
        streak_complete=(t>=earliest+14*86400)&((bad[ends]-bad[before14])==0)&q.history_status.eq('strictly_prior_event_time').to_numpy()
        corrected=np.where(streak_complete,observed_streak,np.nan)
        result={'decision_id':q.decision_id,'option_pitcher_id':q.option_pitcher_id,
            'consecutive_days':corrected,'decision_day_pitch_streak':corrected,'observed_pitch_day_streak':observed_streak,
            'streak_history_complete':streak_complete,'legacy_prior_session_streak':q.legacy_streak,
            'lookback_14d_complete':streak_complete,'last_pitch_available_at':np.where(ends>0,times[np.maximum(ends-1,0)] if len(times) else np.nan,np.nan)}
        game_counts=np.zeros(n);game_last=np.full(n,np.nan)
        samegame={}
        for game,group in h.groupby('game_pk',sort=False):samegame[game]=group.available_at.to_numpy(dtype=float)
        for window in WINDOWS:
            starts=np.searchsorted(times,t-window*86400,side='left');observed=window_counts(times,t,window)
            complete=(t>=earliest+window*86400)&((bad[ends]-bad[starts])==0)&q.history_status.eq('strictly_prior_event_time').to_numpy()
            within=np.zeros(n)
            for game,idx in q.groupby('game_pk').groups.items():
                gt=samegame.get(game,np.empty(0));indices=np.asarray(idx)
                within[indices]=np.searchsorted(gt,t[indices],side='left')-np.searchsorted(gt,t[indices]-window*86400,side='left')
                if window==1:
                    last=np.searchsorted(gt,t[indices],side='left');game_counts[indices]=last
                    if len(gt):game_last[indices]=np.where(last>0,gt[np.maximum(last-1,0)],np.nan)
            result[f'observed_pitches_{window}d']=observed
            result[f'pitches_{window}d_before']=np.where(complete,observed,np.nan)
            result[f'prior_games_pitches_{window}d']=np.where(complete,observed-within,np.nan)
            result[f'window_{window}d_complete']=complete
        result['option_game_pitches']=game_counts
        # Same calendar-day exposure is separate from another appearance earlier today.
        hdays=np.array([day.toordinal() for day in h.pitch_day.dt.date])
        result['has_pitched_today']=(ends>0)&(hdays[np.maximum(ends-1,0)]==ordinals) if len(hdays) else np.zeros(n,dtype=bool)
        entries=apps.entry_at.to_numpy(dtype=float);entry_end=np.searchsorted(entries,t,side='left')
        is_current=q.is_current.to_numpy(dtype=bool);current_ids=q.appearance_id.to_numpy()
        aid_map={v:i for i,v in enumerate(apps.appearance_id)}
        self_index=np.array([aid_map.get(v,-1) if cur else -1 for v,cur in zip(current_ids,is_current)])
        self_known=(self_index>=0)&(np.where(self_index>=0,entries[np.maximum(self_index,0)] if len(entries) else np.inf,np.inf)<t)
        entry_cutoffs=np.where(is_current&self_known,entries[np.maximum(self_index,0)] if len(entries) else t,t)
        entry_days=pd.to_datetime(entry_cutoffs,unit='s',utc=True).tz_convert('America/New_York').date
        appearance_days={d.toordinal() for d in apps.entry_day.dropna().dt.date}
        entry_ordinals=np.array([d.toordinal() for d in entry_days])
        entry_streaks={d:prior_streak(int(d),appearance_days) for d in np.unique(entry_ordinals)}
        entry_complete=(entry_cutoffs>=earliest+14*86400)&q.history_status.eq('strictly_prior_event_time').to_numpy()
        core_streak=np.where(entry_complete,[entry_streaks[d] for d in entry_ordinals],np.nan)
        result['consecutive_days']=core_streak
        result['entry_streak_history_complete']=entry_complete
        result['decision_day_appearance_streak']=np.where(streak_complete,[prior_streak(int(d),appearance_days) for d in ordinals],np.nan)
        changed+=int((q.legacy_streak.fillna(-999).to_numpy()!=np.nan_to_num(core_streak,nan=-999)).sum())
        same_year=(apps.year.to_numpy()==year)
        season_cum=np.r_[0,np.cumsum(same_year)];rp_cum=np.r_[0,np.cumsum(same_year&apps.role.eq('RP').to_numpy())]
        season_prior=season_cum[entry_end]-self_known.astype(int)
        result['season_appearances_before']=season_prior
        result['season_appearance_number']=season_prior+1
        own_rp=self_known&q.option_role.eq('RP').to_numpy()
        result['season_rp_appearances_before']=rp_cum[entry_end]-own_rp.astype(int)
        result['season_rp_appearance_number']=np.where(q.option_role.eq('RP')&q.role_known,result['season_rp_appearances_before']+1,np.nan)
        other_today=np.zeros(n,dtype=bool)
        for day,idx in pd.Series(days).groupby(days).groups.items():
            indices=np.asarray(idx);ad=apps[apps.entry_day.dt.date.eq(day)]
            counts=np.searchsorted(ad.entry_at.to_numpy(dtype=float),t[indices],side='left')-self_known[indices].astype(int)
            other_today[indices]=counts>0
        result['appeared_earlier_today']=other_today
        closed=apps[apps.available_at.notna()].sort_values(['available_at','appearance_id']).copy()
        closed['actual_pitches']=closed.actual_pitches.fillna(closed.pitches.where(closed.pitches.eq(0)))
        closed_times=closed.available_at.to_numpy(dtype=float);closed_end=np.searchsorted(closed_times,t,side='left')
        for name,source in [('previous_pitches','actual_pitches'),('role_history_available_at','available_at')]:
            values=closed[source].to_numpy(dtype=float)
            result[name]=np.where(closed_end>0,values[np.maximum(closed_end-1,0)] if len(values) else np.nan,np.nan)
        last_other=np.full(n,np.nan);entry_rest=np.full(n,np.nan)
        for game,idx in q.groupby('game_pk').groups.items():
            indices=np.asarray(idx);other=h[h.game_pk.ne(game)].available_at.to_numpy(dtype=float)
            at=np.searchsorted(other,t[indices],side='left')
            if len(other):last_other[indices]=np.where(at>0,other[np.maximum(at-1,0)],np.nan)
            entry=np.where(is_current[indices]&self_known[indices],entries[np.maximum(self_index[indices],0)] if len(entries) else t[indices],t[indices])
            previous=np.searchsorted(other,entry,side='left')
            if len(other):entry_rest[indices]=np.where(previous>0,(entry-other[np.maximum(previous-1,0)])/3600,np.nan)
        result['rest_hours']=(t-last_other)/3600;result['entry_rest_hours']=entry_rest
        result['live_idle_hours']=(t-result['last_pitch_available_at'])/3600
        year_times=h.loc[h.year.eq(year),'available_at'].to_numpy(dtype=float)
        result['season_pitches_before']=np.searchsorted(year_times,t,side='left')
        result['decision_at']=t;result['is_current']=is_current;result['option_role']=q.option_role
        out.append(pd.DataFrame(result))
    frame=pd.concat(out,ignore_index=True)
    assert not frame.duplicated(['decision_id','option_pitcher_id']).any()
    assert not (frame.last_pitch_available_at>=frame.decision_at).any()
    assert not (frame.role_history_available_at>=frame.decision_at).any()
    assert frame.rest_hours.dropna().ge(0).all()
    frame.to_parquet(OUT/f'workload_features_{year}.parquet',index=False,compression='zstd')
    counts=frame.groupby(['is_current','option_role']).agg(n=('decision_id','size'),streak=('consecutive_days','count'),three_day=('pitches_3d_before','count'),five_day=('pitches_5d_before','count')).reset_index()
    save(f'workload_{year}.json',{'year':year,'rows':len(frame),'legacy_streak_differences':changed,'coverage':json.loads(counts.to_json(orient='records')),'time_violations':0})
    print(f'{year}: {len(frame):,} repaired option workload rows; legacy streak differences={changed:,}',flush=True)


def references() -> None:
    with connect() as c:
        c.execute(f"CREATE VIEW o AS SELECT * FROM read_parquet('{(OUT/'pitch_observations_*.parquet').as_posix()}')")
        c.read_parquet(str(OUT/'appearance_history.parquet')).create_view('a')
        measures=','.join(f'sum(o.{m}) {m}_sum,count(o.{m}) {m}_n' for m in MEASURES)
        c.execute(f"""CREATE TABLE type_closed AS SELECT o.pitcher_id,o.role,o.pitch_type,
            coalesce(o.plus_model_id,'no_model') model_id,a.available_at,{measures}
            FROM o JOIN a USING(appearance_id) WHERE o.time_reliable AND o.pitch_type IS NOT NULL
            AND a.available_at IS NOT NULL AND coalesce(a.bad_timing,0)=0 GROUP BY ALL""")
        cumulative=','.join(f'sum({m}_sum) OVER w {m}_sum,sum({m}_n) OVER w {m}_n' for m in MEASURES)
        c.execute(f"""CREATE TABLE type_prior AS SELECT pitcher_id,role,pitch_type,model_id,available_at,{cumulative}
            FROM type_closed WINDOW w AS(PARTITION BY pitcher_id,role,pitch_type,model_id ORDER BY available_at ROWS UNBOUNDED PRECEDING)""")
        publish(c,'type_prior',OUT/'type_prior.parquet')
    print('Closed same-type, same-version personal references published',flush=True)


def pa_history(year: int) -> None:
    with connect() as c:
        c.read_parquet(str(OUT/f'pitch_observations_{year}.parquet')).create_view('o')
        c.read_parquet(str(BASE/f'plays_{year}.parquet')).create_view('p')
        c.read_parquet(str(BASE/f'decisions_{year}.parquet')).create_view('d')
        c.read_parquet(str(OUT/'lineup_slots.parquet')).create_view('slots')
        means=','.join(f'avg({m}) pa_{m},count({m}) pa_{m}_n' for m in MEASURES)
        sums=','.join(f'sum({m}) pa_{m}_sum,count({m}) pa_{m}_n' for m in FLAGS)
        c.execute(f"""CREATE TABLE pitches AS SELECT year,game_pk,at_bat_number,
            arg_max(appearance_id,available_at) appearance_id,arg_max(pitcher_id,available_at) actor_pitcher_id,arg_max(batter_id,available_at) actual_batter_id,
            any_value(role) actor_role,min(started_at) anchor_at,max(available_at) last_pitch_at,
            count(DISTINCT pitcher_id) physical_actors,count(DISTINCT appearance_id) physical_appearances,
            count(*) physical_pitches,min(appearance_pitch_position)-1 pitches_before,
            min(session_pitch_position)-1 session_pitches_before,
            max(plus_model_id) plus_model_id,{means},{sums},
            count(*) FILTER(WHERE NOT time_reliable) bad_timing FROM o GROUP BY ALL""")
        c.execute("""CREATE TABLE joined AS SELECT p.*,s.* EXCLUDE(year,game_pk,at_bat_number),
            d.decision_id,d.decision_time,d.batter_id decision_batter_id,d.outgoing_pitcher_id,
            d.outs decision_outs,d.base_state decision_bases,d.home_score decision_home,d.away_score decision_away,
            d.balls decision_balls,d.strikes decision_strikes,slots.batting_slot,
            greatest(epoch(try_cast(p.end_time AS TIMESTAMPTZ)),s.last_pitch_at) available_at,
            p.event_type='intent_walk' intentional_walk,
            CASE WHEN p.event_type IN('strikeout','strikeout_double_play') THEN 1 ELSE 0 END k,
            CASE WHEN p.event_type='walk' THEN 1 ELSE 0 END bb,
            CASE WHEN p.event_type IN('home_run','single','double','triple') THEN 1 ELSE 0 END hit
            FROM p LEFT JOIN pitches s USING(year,game_pk,at_bat_number)
            LEFT JOIN d ON d.outcome_key=p.outcome_key
            LEFT JOIN slots ON slots.game_pk=p.game_pk AND slots.batter_id=p.batter_id""")
        # Include zero-pitch IBB in exposure counts by using official terminal appearance.
        c.read_parquet(str(OUT/'appearance_history.parquet')).create_view('a')
        c.execute("""CREATE TABLE exposure AS SELECT j.*,
            coalesce(j.appearance_id,a.appearance_id) final_appearance_id,
            coalesce(j.actor_pitcher_id,j.terminal_pitcher_id) final_pitcher_id,
            coalesce(j.actor_role,a.role) final_role
            FROM joined j LEFT JOIN a ON j.physical_pitches IS NULL AND a.game_pk=j.game_pk
                AND a.pitcher_id=j.terminal_pitcher_id AND a.entry_ab<=j.at_bat_number
                AND (a.exit_ab IS NULL OR a.exit_ab>=j.at_bat_number)
            QUALIFY count(*) OVER(PARTITION BY j.outcome_key)=1""")
        c.execute("""CREATE TABLE pa_observations AS SELECT *,
            coalesce(sum(cast(is_complete AND is_batter_faced AS INTEGER)) OVER(
                PARTITION BY final_appearance_id ORDER BY at_bat_number ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0) bf_before,
            coalesce(sum(cast(is_complete AND is_batter_faced AS INTEGER)) OVER(
                PARTITION BY game_pk,final_pitcher_id,batter_id ORDER BY at_bat_number ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0) same_batter_encounters_before,
            coalesce(sum(coalesce(physical_pitches,0)) OVER(
                PARTITION BY game_pk,final_pitcher_id,batter_id ORDER BY at_bat_number ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0) pitches_seen_by_batter_before,
            CASE WHEN batting_slot IS NOT NULL THEN 1+coalesce(sum(cast(is_complete AND is_batter_faced AS INTEGER)) OVER(
                PARTITION BY game_pk,final_pitcher_id,batting_slot ORDER BY at_bat_number ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0) END slot_encounter,
            is_complete AND is_batter_faced AND physical_actors=1 AND physical_appearances=1 AND bad_timing=0
                AND NOT intentional_walk AND anchor_at<available_at AND actual_batter_id=decision_batter_id
                AND actor_pitcher_id=terminal_pitcher_id AS process_eligible
            FROM exposure""")
        assert c.execute('SELECT count(*)-count(DISTINCT outcome_key) FROM pa_observations').fetchone()[0]==0
        publish(c,'pa_observations',OUT/f'pa_observations_{year}.parquet')
        save(f'pa_{year}.json',{'year':year,'rows':c.execute('SELECT count(*) FROM pa_observations').fetchone()[0],
            'process_eligible':c.execute('SELECT count(*) FROM pa_observations WHERE process_eligible').fetchone()[0],
            'slots':c.execute('SELECT count(batting_slot) FROM pa_observations').fetchone()[0],
            'scope':'Observed PA responses; never use current PA response as predecision feature. Zero-pitch IBB counts encounters but no pitch exposure.'})
    print(f'{year}: official PA exposures, slots and actual-actor responses published',flush=True)


def attach_prefix(c,request_name: str,output_name: str) -> None:
    cumulative=','.join(f'avg({m}) OVER w live_{m},count({m}) OVER w live_{m}_n,avg({m}) OVER w10 last10_{m}' for m in MEASURES)
    flags=','.join(f'sum({m}) OVER w live_{m}_sum,count({m}) OVER w live_{m}_n,sum({m}) OVER w10 last10_{m}_sum,count({m}) OVER w10 last10_{m}_n' for m in FLAGS)
    c.execute(f"""CREATE OR REPLACE TEMP TABLE ph AS SELECT *,{cumulative},{flags},
        regr_slope(research_stuff_plus,session_pitch_position) OVER w10 last10_stuff_slope,
        regr_slope(release_speed,session_pitch_position) OVER w10 last10_velocity_slope
        FROM o WHERE time_reliable
        WINDOW w AS(PARTITION BY session_id ORDER BY available_at,event_index ROWS UNBOUNDED PRECEDING),
        w10 AS(PARTITION BY session_id ORDER BY available_at,event_index ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)""")
    selected=','.join('p.'+name for name in [r[0] for r in c.execute('DESCRIBE ph').fetchall()] if name.startswith(('live_','last10_')))
    c.execute(f"""CREATE OR REPLACE TABLE live AS SELECT q.*,p.session_id,p.available_at observation_at,
        p.session_pitch_position prefix_pitches,p.plus_model_id observation_model_id,{selected},
        CASE WHEN p.available_at IS NULL THEN 'no_completed_current_pitch'
             WHEN q.cutoff-p.available_at>28800 THEN 'resumed_needs_new_baseline'
             ELSE 'observed_current_prefix' END live_status
        FROM {request_name} q ASOF LEFT JOIN ph p ON q.appearance_id=p.appearance_id AND q.cutoff>p.available_at""")
    assert c.execute('SELECT count(*) FROM live WHERE observation_at>=cutoff').fetchone()[0]==0
    early_means=','.join(f'avg({m}) early_{m},count({m}) early_{m}_n' for m in MEASURES[:3])
    c.execute(f"""CREATE OR REPLACE TEMP TABLE early AS SELECT session_id,pitch_type,max(available_at) early_available_at,
        count(*) early_type_pitches,{early_means} FROM o WHERE time_reliable AND pitch_type IS NOT NULL
        AND session_pitch_position<=CASE WHEN role='SP' THEN 20 ELSE 5 END GROUP BY ALL""")
    late_means=','.join(f'avg({m}) OVER w recent_{m},count({m}) OVER w recent_{m}_n,regr_slope({m},session_pitch_position) OVER w slope_{m}' for m in MEASURES[:3])
    c.execute(f"""CREATE OR REPLACE TEMP TABLE late AS SELECT session_id,pitch_type,available_at,{late_means}
        FROM o WHERE time_reliable AND pitch_type IS NOT NULL AND session_pitch_position>CASE WHEN role='SP' THEN 20 ELSE 5 END
        WINDOW w AS(PARTITION BY session_id,pitch_type ORDER BY available_at,event_index ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)""")
    c.execute("""CREATE OR REPLACE TEMP TABLE type_requests AS SELECT l.request_id,l.appearance_id,l.pitcher_id,l.role,l.cutoff,l.entry_at,l.fold_id,
        e.*,e.early_type_pitches*1.0/CASE WHEN l.role='SP' THEN 20 ELSE 5 END mix_weight
        FROM live l JOIN early e USING(session_id) WHERE l.live_status='observed_current_prefix'
        AND l.prefix_pitches>=CASE WHEN l.role='SP' THEN 35 ELSE 10 END AND e.early_available_at<l.cutoff""")
    c.execute("""CREATE OR REPLACE TABLE types AS SELECT q.*,s.* EXCLUDE(session_id,pitch_type),
        r.available_at personal_reference_at,r.research_stuff_plus_sum/nullif(r.research_stuff_plus_n,0) personal_stuff,
        r.research_stuff_plus_n personal_stuff_n,r.research_location_plus_sum/nullif(r.research_location_plus_n,0) personal_location,
        r.research_location_plus_n personal_location_n
        FROM type_requests q ASOF LEFT JOIN late s ON q.session_id=s.session_id AND q.pitch_type=s.pitch_type AND q.cutoff>s.available_at
        ASOF LEFT JOIN type_prior r ON q.pitcher_id=r.pitcher_id AND q.role=r.role AND q.pitch_type=r.pitch_type
            AND ('decision_temporal_research_v1:plus:'||q.fold_id)=r.model_id AND q.entry_at>r.available_at""")
    aggregates=[]
    for metric in MEASURES[:3]:
        gate=f"early_{metric}_n>=CASE WHEN role='SP' THEN 3 ELSE 2 END AND recent_{metric}_n>=2"
        coverage=f'sum(CASE WHEN {gate} THEN mix_weight ELSE 0 END)'
        aggregates += [f'{coverage} mix_coverage_{metric}',
            f'CASE WHEN {coverage}>=0.8 THEN sum(CASE WHEN {gate} THEN mix_weight*(recent_{metric}-early_{metric}) END)/nullif({coverage},0) END mix_delta_{metric}',
            f'CASE WHEN {coverage}>=0.8 THEN sum(CASE WHEN {gate} THEN mix_weight*slope_{metric} END)/nullif({coverage},0) END mix_slope_{metric}']
    for metric,name in [('research_stuff_plus','stuff'),('research_location_plus','location')]:
        gate=f'personal_{name}_n>=20 AND recent_{metric}_n>=2';coverage=f'sum(CASE WHEN {gate} THEN mix_weight ELSE 0 END)'
        aggregates += [f'{coverage} personal_coverage_{name}',
            f'CASE WHEN {coverage}>=0.8 THEN sum(CASE WHEN {gate} THEN mix_weight*(recent_{metric}-personal_{name}) END)/nullif({coverage},0) END personal_delta_{name}']
    c.execute(f"CREATE OR REPLACE TEMP TABLE deltas AS SELECT request_id,{','.join(aggregates)} FROM types GROUP BY request_id")
    c.execute(f"""CREATE OR REPLACE TABLE {output_name} AS SELECT l.*,d.* EXCLUDE(request_id),
        s.quality_plus,s.physical_plus,s.command_plus,s.quality_low,s.quality_high,s.physical_low,s.physical_high,
        s.command_low,s.command_high,s.reliability state_reliability,s.state_observed_at,s.state_train_cutoff,
        s.status state_status FROM live l LEFT JOIN deltas d USING(request_id)
        ASOF LEFT JOIN old_state_history s ON l.appearance_id=s.appearance_id AND l.cutoff>s.state_observed_at""")
    # Resume/old-state gates are applied to observations and state separately.
    names=[r[0] for r in c.execute(f'DESCRIBE {output_name}').fetchall()]
    to_null=[n for n in names if n.startswith(('live_','last10_','mix_','personal_')) and n!='live_status']
    c.execute(f"UPDATE {output_name} SET "+','.join(n+'=NULL' for n in to_null)+" WHERE live_status='resumed_needs_new_baseline'")
    c.execute(f"""UPDATE {output_name} SET quality_plus=NULL,physical_plus=NULL,command_plus=NULL,
        quality_low=NULL,quality_high=NULL,physical_low=NULL,physical_high=NULL,command_low=NULL,command_high=NULL
        WHERE prefix_pitches>CASE WHEN role='SP' THEN 100 ELSE 60 END OR live_status='resumed_needs_new_baseline'
          OR state_observed_at IS NULL OR (observation_at-state_observed_at)>28800""")
    c.execute(f"UPDATE {output_name} SET state_status='outside_modeled_pitch_count' WHERE prefix_pitches>CASE WHEN role='SP' THEN 100 ELSE 60 END")
    c.execute(f"UPDATE {output_name} SET state_status='resumed_needs_new_baseline' WHERE live_status='resumed_needs_new_baseline'")
    assert c.execute(f'SELECT count(*) FROM {output_name} WHERE state_observed_at>=cutoff OR state_train_cutoff>state_observed_at').fetchone()[0]==0


def attach_prior_pa(c,table: str) -> None:
    c.execute("""CREATE OR REPLACE TEMP TABLE pa_prefix AS SELECT final_appearance_id,available_at,
        count(*) FILTER(WHERE is_complete AND is_batter_faced) OVER w completed_bf,
        count(*) FILTER(WHERE process_eligible) OVER w organic_pa,
        sum(CASE WHEN process_eligible THEN k END) OVER w k_sum,
        sum(CASE WHEN process_eligible THEN bb END) OVER w bb_sum,
        sum(CASE WHEN process_eligible THEN hit END) OVER w hit_sum,
        count(*) FILTER(WHERE process_eligible) OVER w5 last5_pa_n,
        sum(CASE WHEN process_eligible THEN k END) OVER w5 last5_k,
        sum(CASE WHEN process_eligible THEN bb END) OVER w5 last5_bb
        FROM pa WHERE final_appearance_id IS NOT NULL AND available_at IS NOT NULL
        WINDOW w AS(PARTITION BY final_appearance_id ORDER BY available_at,at_bat_number ROWS UNBOUNDED PRECEDING),
        w5 AS(PARTITION BY final_appearance_id ORDER BY available_at,at_bat_number ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)""")
    c.execute("""CREATE OR REPLACE TEMP TABLE pairs AS SELECT game_pk,final_pitcher_id,batter_id,available_at,
        count(*) OVER(PARTITION BY game_pk,final_pitcher_id,batter_id ORDER BY available_at,at_bat_number ROWS UNBOUNDED PRECEDING) encounters
        FROM pa WHERE is_complete AND is_batter_faced AND available_at IS NOT NULL""")
    c.execute("""CREATE OR REPLACE TEMP TABLE pair_pitches AS SELECT game_pk,pitcher_id,batter_id,available_at,
        count(*) OVER(PARTITION BY game_pk,pitcher_id,batter_id ORDER BY available_at,event_index ROWS UNBOUNDED PRECEDING) seen
        FROM o WHERE time_reliable""")
    c.execute(f"""CREATE OR REPLACE TABLE extended AS SELECT f.*,h.available_at prior_pa_available_at,
        coalesce(h.completed_bf,0) completed_bf_before,coalesce(h.organic_pa,0) observed_organic_pa_before,
        h.k_sum prior_k,h.bb_sum prior_bb,h.hit_sum prior_hits,h.last5_pa_n,h.last5_k,h.last5_bb,
        coalesce(v.encounters,0) observed_pair_encounters_before,coalesce(z.seen,0) observed_pair_pitches_before
        FROM {table} f ASOF LEFT JOIN pa_prefix h ON f.appearance_id=h.final_appearance_id AND f.cutoff>h.available_at
        ASOF LEFT JOIN pairs v ON f.game_pk=v.game_pk AND f.pitcher_id=v.final_pitcher_id AND f.batter_id=v.batter_id AND f.cutoff>v.available_at
        ASOF LEFT JOIN pair_pitches z ON f.game_pk=z.game_pk AND f.pitcher_id=z.pitcher_id AND f.batter_id=z.batter_id AND f.cutoff>z.available_at""")
    assert c.execute('SELECT count(*) FROM extended WHERE prior_pa_available_at>=cutoff').fetchone()[0]==0
    c.execute(f'CREATE OR REPLACE TABLE {table} AS SELECT * FROM extended')


def prefix(year: int) -> None:
    with connect() as c:
        c.read_parquet(str(OUT/f'pitch_observations_{year}.parquet')).create_view('o')
        c.read_parquet(str(OUT/'type_prior.parquet')).create_view('type_prior')
        c.read_parquet(str(OUT/'appearance_history.parquet')).create_view('a')
        c.read_parquet(str(BASE/f'decisions_{year}.parquet')).create_view('d')
        c.read_parquet(str(OUT/f'pa_observations_{year}.parquet')).create_view('pa')
        c.execute(f"CREATE VIEW old_state_history AS SELECT appearance_id,observed_at state_observed_at,state_train_cutoff,quality_plus,physical_plus,command_plus,quality_low,quality_high,physical_low,physical_high,command_low,command_high,reliability,status FROM read_parquet('{(b.TEMPORAL/f'states_{year}_*.parquet').as_posix()}')")
        c.execute("""CREATE TABLE requests AS SELECT d.decision_id request_id,d.decision_id,d.game_pk,d.appearance_id,d.outgoing_pitcher_id pitcher_id,
            a.role,epoch(try_cast(d.decision_time AS TIMESTAMPTZ)) cutoff,a.entry_at,d.batter_id,
            'pending' fold_id FROM d JOIN a USING(appearance_id)""")
        request_frame=c.table('requests').fetchdf();request_frame['fold_id']=fold_at(request_frame.cutoff.to_numpy())
        c.register('request_frame',request_frame);c.execute('CREATE OR REPLACE TABLE requests AS SELECT * FROM request_frame')
        attach_prefix(c,'requests','current_features')
        attach_prior_pa(c,'current_features')
        publish(c,'current_features',OUT/f'current_features_{year}.parquet')
        c.execute("""CREATE OR REPLACE TABLE requests AS SELECT pa.outcome_key||':pa_anchor' request_id,pa.decision_id,pa.game_pk,
            pa.final_appearance_id appearance_id,pa.final_pitcher_id pitcher_id,pa.final_role AS role,
            pa.anchor_at cutoff,a.entry_at,pa.actual_batter_id batter_id,'pending' fold_id
            FROM pa JOIN a ON a.appearance_id=pa.final_appearance_id WHERE pa.process_eligible""")
        request_frame=c.table('requests').fetchdf();request_frame['fold_id']=fold_at(request_frame.cutoff.to_numpy())
        c.unregister('request_frame');c.register('request_frame',request_frame);c.execute('CREATE OR REPLACE TABLE requests AS SELECT * FROM request_frame')
        attach_prefix(c,'requests','pa_features')
        attach_prior_pa(c,'pa_features')
        publish(c,'pa_features',OUT/f'pa_features_{year}.parquet')
        coverage=c.execute('SELECT role,count(*) n,count(live_research_stuff_plus) stuff,count(quality_plus) quality,count(mix_delta_research_stuff_plus) mix_delta FROM current_features GROUP BY role').fetchdf()
        save(f'prefix_{year}.json',{'year':year,'coverage':json.loads(coverage.to_json(orient='records')),'time_violations':0,
            'scope':'Current features refer to original outgoing actor; PA-anchor features refer to actual sole physical actor before first pitch. No batter swing-by-type feature (Slice13.5) is built.'})
    print(f'{year}: predecision current/actual-PA observations and same-type deltas published',flush=True)


RECENT_METRICS=['stuff','location','velocity','spin','pfx_x','pfx_z','release_x','release_z','extension',
    'quality','physical','command','k_rate','bb_rate','whiff_rate','contact_rate','csw_rate','ev',
    'relative_stuff','relative_location','relative_velocity']


def recent_history() -> None:
    assert all((OUT/f'pa_observations_{year}.parquet').exists() for year in YEARS),'Build all six PA histories first'
    with connect() as c:
        c.execute(f"CREATE VIEW o AS SELECT * FROM read_parquet('{(OUT/'pitch_observations_*.parquet').as_posix()}')")
        c.execute(f"CREATE VIEW pa AS SELECT * FROM read_parquet('{(OUT/'pa_observations_*.parquet').as_posix()}')")
        c.read_parquet(str(OUT/'appearance_history.parquet')).create_view('a')
        c.read_parquet(str(OUT/'type_prior.parquet')).create_view('r')
        c.execute(f"CREATE VIEW st AS SELECT appearance_id,observed_at,plus_model_id,state_train_cutoff,quality_plus,physical_plus,command_plus,quality_low,quality_high,physical_low,physical_high,command_low,command_high,reliability FROM read_parquet('{(b.TEMPORAL/'states_20*.parquet').as_posix()}')")
        c.execute("""CREATE TEMP TABLE latest AS SELECT appearance_id,arg_max(plus_model_id,available_at) model_id,
            max(available_at) observed_at,arg_max(session_id,available_at) session_id
            FROM o GROUP BY appearance_id""")
        c.execute("""CREATE TEMP TABLE last_session AS SELECT o.appearance_id,min(o.available_at) started_at,max(o.session_pitch_position) pitches
            FROM o JOIN latest l ON o.appearance_id=l.appearance_id AND o.session_id=l.session_id GROUP BY o.appearance_id""")
        raw_means=','.join(f'avg({m}) AS "{alias}"' for m,alias in zip(MEASURES[2:],['velocity','spin','pfx_x','pfx_z','release_x','release_z','extension','arm_angle']))
        c.execute(f"""CREATE TEMP TABLE raw AS SELECT appearance_id,{raw_means},
            sum(whiff)/nullif(sum(swing),0) whiff_rate,sum(contact)/nullif(sum(swing),0) contact_rate,
            sum(csw)/nullif(count(csw),0) csw_rate,avg(ev) ev,count(*) physical_pitches,
            count(swing) pitch_outcome_n,sum(swing) swings,count(ev) ev_n
            FROM o WHERE time_reliable GROUP BY appearance_id""")
        c.execute("""CREATE TEMP TABLE plus AS SELECT o.appearance_id,avg(research_stuff_plus) stuff,
            avg(research_location_plus) AS location,count(research_stuff_plus) stuff_n,count(research_location_plus) location_n
            FROM o JOIN latest l ON o.appearance_id=l.appearance_id AND o.plus_model_id=l.model_id
            WHERE o.time_reliable GROUP BY o.appearance_id""")
        type_stats=','.join(f'avg({m}) value_{m},count({m}) n_{m}' for m in MEASURES[:3])
        c.execute(f"""CREATE TEMP TABLE ap_type AS SELECT o.appearance_id,o.pitcher_id,o.role,o.pitch_type,
            l.model_id,a.entry_at,{type_stats} FROM o JOIN latest l USING(appearance_id)
            JOIN a ON a.appearance_id=o.appearance_id
            WHERE o.time_reliable AND o.pitch_type IS NOT NULL AND o.plus_model_id=l.model_id GROUP BY ALL""")
        personal=[]
        for m,name in zip(MEASURES[:3],['stuff','location','velocity']):
            gate=f'r.{m}_n>=20 AND t.n_{m}>0'
            coverage=f'sum(CASE WHEN {gate} THEN t.n_{m} ELSE 0 END)/nullif(sum(t.n_{m}),0)'
            personal.append(f'CASE WHEN {coverage}>=0.8 THEN sum(CASE WHEN {gate} THEN t.n_{m}*(t.value_{m}-r.{m}_sum/r.{m}_n) END)/nullif(sum(CASE WHEN {gate} THEN t.n_{m} ELSE 0 END),0) END relative_{name}')
        c.execute(f"""CREATE TEMP TABLE relative AS SELECT t.appearance_id,{','.join(personal)}
            FROM ap_type t ASOF LEFT JOIN r ON t.pitcher_id=r.pitcher_id AND t.role=r.role AND t.pitch_type=r.pitch_type
                AND t.model_id=r.model_id AND t.entry_at>r.available_at GROUP BY t.appearance_id""")
        c.execute("""CREATE TABLE recent_history AS SELECT a.appearance_id,a.year,a.game_pk,a.pitcher_id,a.role,
            a.entry_at,a.available_at,l.observed_at,l.model_id,p.stuff,p.location,p.stuff_n,p.location_n,
            raw.* EXCLUDE(appearance_id),rel.* EXCLUDE(appearance_id),
            y.k_n/nullif(y.pa_n,0) k_rate,y.bb_n/nullif(y.pa_n,0) bb_rate,y.pa_n,
            CASE WHEN z.pitches<=CASE WHEN a.role='SP' THEN 100 ELSE 60 END AND s.observed_at>=z.started_at
                 THEN s.quality_plus END quality,
            CASE WHEN z.pitches<=CASE WHEN a.role='SP' THEN 100 ELSE 60 END AND s.observed_at>=z.started_at
                 THEN s.physical_plus END physical,
            CASE WHEN z.pitches<=CASE WHEN a.role='SP' THEN 100 ELSE 60 END AND s.observed_at>=z.started_at
                 THEN s.command_plus END command,
            s.observed_at state_observed_at,s.state_train_cutoff,
            s.quality_low,s.quality_high,s.physical_low,s.physical_high,s.command_low,s.command_high
            FROM a LEFT JOIN latest l USING(appearance_id) LEFT JOIN raw USING(appearance_id)
            LEFT JOIN plus p USING(appearance_id) LEFT JOIN relative rel USING(appearance_id)
            LEFT JOIN last_session z USING(appearance_id)
            LEFT JOIN(SELECT final_appearance_id appearance_id,count(*) pa_n,sum(k) k_n,sum(bb) bb_n
                FROM pa WHERE process_eligible GROUP BY final_appearance_id) y USING(appearance_id)
            LEFT JOIN(SELECT * FROM st QUALIFY row_number() OVER(PARTITION BY appearance_id ORDER BY observed_at DESC)=1) s
                ON a.appearance_id=s.appearance_id AND s.plus_model_id=l.model_id
            WHERE a.available_at IS NOT NULL AND coalesce(a.bad_timing,0)=0""")
        assert c.execute('SELECT count(*)-count(DISTINCT appearance_id) FROM recent_history').fetchone()[0]==0
        publish(c,'recent_history',OUT/'recent_history.parquet')
    print('Closed appearance role/measurement/state observation history published',flush=True)


def interval_stats(values: np.ndarray,starts: np.ndarray,ends: np.ndarray) -> tuple[np.ndarray,np.ndarray,np.ndarray,np.ndarray]:
    finite=np.isfinite(values);clean=np.where(finite,values,0.)
    count=np.r_[0,np.cumsum(finite)];total=np.r_[0,np.cumsum(clean)];square=np.r_[0,np.cumsum(clean*clean)]
    n=count[ends]-count[starts];s=total[ends]-total[starts];ss=square[ends]-square[starts]
    mean=np.divide(s,n,out=np.full(len(n),np.nan),where=n>0)
    variance=np.divide(ss-n*mean*mean,n-1,out=np.full(len(n),np.nan),where=n>1)
    se=np.sqrt(np.maximum(variance,0)/np.maximum(n,1))
    return mean,n,mean-1.281552*se,mean+1.281552*se


def recent(year: int) -> None:
    with connect() as c:
        c.read_parquet(str(OUT/'recent_history.parquet')).create_view('h')
        history=c.execute('SELECT * FROM h WHERE year<=? ORDER BY pitcher_id,role,available_at,appearance_id',[year]).fetchdf()
        c.read_parquet(str(b.OUT/f'option_features_{year}.parquet')).create_view('o')
        requests=c.execute('SELECT decision_id,option_pitcher_id,option_role,is_current,decision_at FROM o').fetchdf()
    requests['fold_id']=fold_at(requests.decision_at.to_numpy())
    groups={(pid,role):g.reset_index(drop=True) for (pid,role),g in history.groupby(['pitcher_id','role'],sort=False)}
    profiles=[];links=[];profile_counter=0
    for (pid,role,fold),q in requests.groupby(['option_pitcher_id','option_role','fold_id'],sort=False):
        q=q.reset_index(drop=True);t=q.decision_at.to_numpy();h=groups.get((pid,role),history.iloc[:0])
        times=h.available_at.to_numpy(dtype=float)
        end=np.searchsorted(times,t,side='left');start3=np.searchsorted(times,t-3*86400,side='left');start5=np.searchsorted(times,t-5*86400,side='left')
        unique,inverse=np.unique(np.column_stack([end,start3,start5]),axis=0,return_inverse=True)
        e,s3,s5=unique.T
        profile_ids=np.arange(profile_counter,profile_counter+len(unique));profile_counter+=len(unique)
        profile={'profile_id':profile_ids,'pitcher_id':pid,'role':role,'fold_id':fold,'history_end':e,
            'latest_available_at':np.where(e>0,times[np.maximum(e-1,0)] if len(times) else np.nan,np.nan)}
        compatible=h.model_id.eq('decision_temporal_research_v1:plus:'+fold).to_numpy()
        windows={'last1':np.maximum(e-1,0),'last3':np.maximum(e-3,0),'last5':np.maximum(e-5,0),'day3':s3,'day5':s5}
        for name,starts in windows.items():
            profile[f'{name}_appearances']=e-starts
            plus_valid=compatible&h.stuff.notna().to_numpy()
            state_valid=compatible&h[['quality','physical','command']].notna().any(axis=1).to_numpy()
            for kind,valid in [('raw',np.ones(len(h),dtype=bool)),('plus',plus_valid),('state',state_valid)]:
                observed=h.state_observed_at.to_numpy(dtype=float) if kind=='state' else h.observed_at.to_numpy(dtype=float)
                profile[f'{name}_{kind}_observation_at']=[float(np.nanmax(observed[begin:finish][valid[begin:finish]])) if valid[begin:finish].any() and np.isfinite(observed[begin:finish][valid[begin:finish]]).any() else np.nan for begin,finish in zip(starts,e)]
            for metric in RECENT_METRICS:
                values=pd.to_numeric(h[metric],errors='coerce').to_numpy(dtype=float)
                if metric in ['stuff','location','quality','physical','command','relative_stuff','relative_location','relative_velocity']:
                    values=np.where(compatible,values,np.nan)
                mean,n,low,high=interval_stats(values,starts,e)
                for suffix,val in [('mean',mean),('n',n),('low80',low),('high80',high)]:profile[f'{name}_{metric}_{suffix}']=val
        for metric in ['stuff','location','velocity']:
            slopes=[]
            v=pd.to_numeric(h[metric],errors='coerce').to_numpy(dtype=float)
            if metric!='velocity':v=np.where(compatible,v,np.nan)
            for begin,finish in zip(np.maximum(e-5,0),e):
                values=v[begin:finish];valid=np.isfinite(values);x=np.arange(len(values))[valid]
                slopes.append(float(np.polyfit(x,values[valid],1)[0]) if valid.sum()>=3 else np.nan)
            profile[f'last5_{metric}_slope_per_appearance']=slopes
        profiles.append(pd.DataFrame(profile))
        latest=profile['latest_available_at'][inverse]
        assert np.all(np.isnan(latest)|(latest<t))
        links.append(pd.DataFrame({'decision_id':q.decision_id,'option_pitcher_id':pid,'is_current':q.is_current,
            'option_role':role,'profile_id':profile_ids[inverse],'decision_at':t,'latest_history_available_at':latest,
            'history_age_hours':(t-latest)/3600}))
    profile_frame=pd.concat(profiles,ignore_index=True);link_frame=pd.concat(links,ignore_index=True)
    assert not link_frame.duplicated(['decision_id','option_pitcher_id']).any()
    profile_frame.to_parquet(OUT/f'recent_profiles_{year}.parquet',index=False,compression='zstd')
    link_frame.to_parquet(OUT/f'recent_links_{year}.parquet',index=False,compression='zstd')
    joined=link_frame.merge(profile_frame[['profile_id','last1_stuff_n','last3_stuff_n','day3_stuff_n','day5_stuff_n','last1_quality_n']],on='profile_id',validate='many_to_one')
    coverage=joined.groupby(['is_current','option_role']).agg(n=('decision_id','size'),last_stuff=('last1_stuff_n',lambda s:int((s>0).sum())),three_appearance_stuff=('last3_stuff_n',lambda s:int((s>0).sum())),three_day_stuff=('day3_stuff_n',lambda s:int((s>0).sum())),five_day_stuff=('day5_stuff_n',lambda s:int((s>0).sum())),last_quality=('last1_quality_n',lambda s:int((s>0).sum()))).reset_index()
    save(f'recent_{year}.json',{'year':year,'option_rows':len(link_frame),'unique_profiles':len(profile_frame),
        'coverage':json.loads(coverage.to_json(orient='records')),'time_violations':0,
        'scope':'same observed role; raw measures may cross versions, Plus/state comparisons require requested model version; latest history is closed strictly before decision',
        'intervals':'Descriptive normal central80 interval of appearance means, only n>=2; serial/model uncertainty not included. No recent appearance is not a normal-state observation.'})
    print(f'{year}: {len(link_frame):,} recent-state links / {len(profile_frame):,} unique profiles',flush=True)


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['sources','lineups','workload','references','pa','prefix','recent_history','recent']);parser.add_argument('--year',type=int,choices=YEARS)
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if args.stage in ('workload','pa','prefix','recent'):
        function=pa_history if args.stage=='pa' else globals()[args.stage]
        for year in [args.year] if args.year else YEARS:function(year)
    else:globals()[args.stage]()


if __name__=='__main__':main()
