"""15.1 common pre-action anchor and missingness audit. Prior studies are read-only."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_overlap as old

n,b=old.n,old.b
ROOT=old.ROOT;OUT=ROOT/'data/research/decision_common_clock_v1'


def read(path):return old.read(path)
def save(name,value):b.save_json(OUT/name,value)
def write(frame,name):frame.to_parquet(OUT/name,index=False,compression='zstd')


def anchor_reason(frame):
    return np.select([frame.anchor_at.isna()|~frame.previous_complete.fillna(False),
        frame.anchor_at.ge(frame.old_decision_at),frame.entry_at.ge(frame.anchor_at)|frame.entry_at.isna(),
        ~frame.outs.between(0,2)|~frame.base_state.between(0,7)],
        ['previous_complete_clock_unknown','anchor_not_strictly_before_action','outgoing_not_yet_observed_at_anchor','anchor_state_unknown'],default='included')


def cache():
    OUT.mkdir(parents=True,exist_ok=True)
    print('15.1: building cumulative official-pitch clocks2021-24 only',flush=True)
    with n.r.connect() as c:
        paths=[str(n.r.OUT/f'pitch_observations_{y}.parquet') for y in range(2021,2025)]
        c.read_parquet(paths).create_view('o')
        c.execute('''CREATE TABLE physical AS SELECT game_pk,pitcher_id,appearance_id,session_id,available_at,
            appearance_pitch_position,session_pitch_position,p_throws,event_id,at_bat_number FROM o WHERE time_reliable AND available_at IS NOT NULL''')
        c.execute('''CREATE TABLE pitcher_clock AS SELECT pitcher_id,available_at,
            sum(n) OVER(PARTITION BY pitcher_id ORDER BY available_at ROWS UNBOUNDED PRECEDING) cumulative_pitches
            FROM(SELECT pitcher_id,available_at,count(*) n FROM physical GROUP BY ALL)''')
        c.table('pitcher_clock').write_parquet(str(OUT/'pitcher_clock.parquet'),compression='zstd')
        print('15.1: total-pitch clocks ready; saving game clocks',flush=True)
        c.execute('''CREATE TABLE game_clock AS SELECT game_pk,pitcher_id,available_at,
            sum(n) OVER(PARTITION BY game_pk,pitcher_id ORDER BY available_at ROWS UNBOUNDED PRECEDING) game_pitches,
            appearance_id,session_id,appearance_position,session_position,pitcher_hand FROM(
                SELECT game_pk,pitcher_id,available_at,count(*) n,any_value(appearance_id) appearance_id,any_value(session_id) session_id,
                    max(appearance_pitch_position) appearance_position,max(session_pitch_position) session_position,any_value(p_throws) pitcher_hand
                FROM physical GROUP BY game_pk,pitcher_id,available_at)''')
        c.table('game_clock').write_parquet(str(OUT/'game_clock.parquet'),compression='zstd')
        earliest=c.execute('SELECT min(available_at) FROM physical').fetchone()[0]
    save('cache.json',{'earliest':earliest,'years':[2021,2022,2023,2024],'time':'completed physical pitch available_at, strictly before anchor; anchor is previous play end plus1ms'})
    print('15.1 cumulative clock cache ready',flush=True)


def prepare(year):
    print(f'15.1 {year}: previous completed-play anchors and state reconstruction',flush=True)
    with n.r.connect() as c:
        c.read_parquet(str(old.OUT/f'boundaries_{year}.parquet')).create_view('original')
        for folder,name in [(n.old.FOUNDATION,'decisions'),(n.old.FOUNDATION,'plays'),(n.old.FOUNDATION,'bullpen_candidates'),(n.old.FOUNDATION,'appearances')]:
            c.read_parquet(str(folder/f'{name}_{year}.parquet')).create_view(name)
        c.read_parquet(str(n.r.OUT/'appearance_history.parquet')).create_view('appearance_history')
        c.read_parquet(str(OUT/'game_clock.parquet')).create_view('gc')
        c.read_parquet(str(OUT/'pitcher_clock.parquet')).create_view('pc')
        c.read_parquet(str(n.OUT/f'block_scores_{year}.parquet')).filter(f'alpha={n.ALPHA}').create_view('signals')
        c.read_parquet(str(b.PREP/'ability_history.parquet')).filter("actor='pitcher' AND split='All'").create_view('ability')
        c.execute('''CREATE TEMP TABLE previous AS SELECT game_pk,at_bat_number,lag(epoch(try_cast(end_time AS TIMESTAMPTZ))) OVER win previous_end,
            lag(is_complete) OVER win previous_complete,lag(inning) OVER win previous_inning,lag(half) OVER win previous_half,
            lag(outs_after) OVER win previous_outs,lag(base_state_after) OVER win previous_bases,
            lag(home_score_after) OVER win previous_home,lag(away_score_after) OVER win previous_away
            FROM plays WINDOW win AS(PARTITION BY game_pk ORDER BY at_bat_number)''')
        base=c.execute('''SELECT o.year,o.game_pk,o.team_id,o.decision_id,o.role,o.appearance_id,o.outgoing_pitcher_id,
            o.changed,o.cohort_reason,o.game_closed_at,o.decision_at old_decision_at,
            d.at_bat_number,d.event_index,p.previous_end+.001 anchor_at,p.previous_complete,
            o.inning,o.half,o.scheduled_innings,a.entry_at,
            CASE WHEN p.previous_inning=o.inning AND p.previous_half=o.half THEN 'within_inning' ELSE 'between_innings' END phase,
            CASE WHEN p.previous_inning=o.inning AND p.previous_half=o.half THEN p.previous_outs ELSE0 END outs,
            CASE WHEN p.previous_inning=o.inning AND p.previous_half=o.half THEN p.previous_bases WHEN o.inning>o.scheduled_innings THEN2 ELSE0 END base_state,
            CASE WHEN o.half='top' THEN p.previous_home-p.previous_away ELSE p.previous_away-p.previous_home END defense_lead
            FROM original o JOIN decisions d USING(decision_id) JOIN previous p ON p.game_pk=o.game_pk AND p.at_bat_number=d.at_bat_number
            LEFT JOIN appearance_history a ON o.appearance_id=a.appearance_id ORDER BY o.game_pk,d.at_bat_number'''.replace('ELSE0','ELSE 0').replace('THEN2','THEN 2')).fetchdf()
        base['anchor_reason']=anchor_reason(base);base['clock_gap_seconds']=base.old_decision_at-base.anchor_at
        write(base,'anchor_audit_'+str(year)+'.parquet')
        valid=base[base.anchor_reason.eq('included')].copy();valid['decision_at']=valid.anchor_at
        valid['cut72']=valid.anchor_at-72*3600;valid['cut120']=valid.anchor_at-120*3600
        c.register('q',valid)
        c.execute('''CREATE TEMP TABLE bf AS SELECT game_pk,terminal_pitcher_id pitcher_id,epoch(try_cast(end_time AS TIMESTAMPTZ)) available_at,
            count(*) OVER(PARTITION BY game_pk,terminal_pitcher_id ORDER BY at_bat_number ROWS UNBOUNDED PRECEDING) bf
            FROM plays WHERE is_complete AND is_batter_faced AND end_time IS NOT NULL''')
        c.execute('''CREATE TEMP TABLE refs AS SELECT pitcher_id,role,available_at,median(actual_pitches) OVER win median_pitches,
            count(*) OVER win history_n FROM appearance_history WHERE available_at IS NOT NULL AND NOT bad_timing AND actual_pitches>0
            WINDOW win AS(PARTITION BY pitcher_id,role ORDER BY available_at,appearance_id ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)''')
        fields=['block_id','session_id','block_number','available_at','personal_reference_at','n_stuff','n_velocity','n_location','n_contact']
        fields += [g+suffix for g in 'ABC' for suffix in ['_state','_severity']]+['smooth_stuff','smooth_velocity','smooth_location','smooth_contact']
        result=c.execute('''SELECT q.*,g.available_at pitch_available_at,g.game_pitches current_pitches,g.pitcher_hand,g.session_position,
            coalesce(z.bf,0) current_bf,g.appearance_position,
            (p.cumulative_pitches-coalesce(p3.cumulative_pitches,0))-(g.game_pitches-coalesce(g3.game_pitches,0)) prior_games_pitches_3d,
            (p.cumulative_pitches-coalesce(p5.cumulative_pitches,0))-(g.game_pitches-coalesce(g5.game_pitches,0)) prior_games_pitches_5d,
            r.available_at load_reference_at,r.median_pitches,r.history_n,ent.available_at entry_last_pitch_at,
            a.available_at ability_available_at,a.pa_n ability_n,a.k_n/nullif(a.pa_n,0) pitcher_k_rate,a.bb_n/nullif(a.pa_n,0) pitcher_bb_rate,
            a.hr_n/nullif(a.pa_n,0) pitcher_hr_rate,'''+','.join('s.'+v for v in fields)+'''
            FROM q ASOF LEFT JOIN gc g ON q.game_pk=g.game_pk AND q.outgoing_pitcher_id=g.pitcher_id AND q.anchor_at>g.available_at
            ASOF LEFT JOIN pc p ON q.outgoing_pitcher_id=p.pitcher_id AND q.anchor_at>p.available_at
            ASOF LEFT JOIN pc p3 ON q.outgoing_pitcher_id=p3.pitcher_id AND q.cut72>p3.available_at
            ASOF LEFT JOIN pc p5 ON q.outgoing_pitcher_id=p5.pitcher_id AND q.cut120>p5.available_at
            ASOF LEFT JOIN gc g3 ON q.game_pk=g3.game_pk AND q.outgoing_pitcher_id=g3.pitcher_id AND q.cut72>g3.available_at
            ASOF LEFT JOIN gc g5 ON q.game_pk=g5.game_pk AND q.outgoing_pitcher_id=g5.pitcher_id AND q.cut120>g5.available_at
            ASOF LEFT JOIN bf z ON q.game_pk=z.game_pk AND q.outgoing_pitcher_id=z.pitcher_id AND q.anchor_at>z.available_at
            ASOF LEFT JOIN refs r ON q.outgoing_pitcher_id=r.pitcher_id AND q.role=r.role AND q.entry_at>r.available_at
            ASOF LEFT JOIN pc ent ON q.outgoing_pitcher_id=ent.pitcher_id AND q.entry_at>ent.available_at
            ASOF LEFT JOIN ability a ON q.outgoing_pitcher_id=a.player_id AND q.role=a.role AND q.anchor_at>a.available_at
            ASOF LEFT JOIN signals s ON q.appearance_id=s.appearance_id AND q.anchor_at>s.available_at''').fetchdf()
        print(f'15.1 {year}: {len(result):,} anchor-safe state/load/ability rows; linking strictly earlier pool snapshots',flush=True)
        c.execute('''CREATE TEMP TABLE snapshots AS SELECT game_pk,team_id,decision_id snapshot_id,max(cutoff_epoch) snapshot_at
            FROM bullpen_candidates GROUP BY game_pk,team_id,decision_id''')
        c.register('q',result)
        links=c.execute('''SELECT q.decision_id,s.snapshot_id,s.snapshot_at FROM q ASOF LEFT JOIN snapshots s
            ON q.game_pk=s.game_pk AND q.team_id=s.team_id AND q.anchor_at>s.snapshot_at''').fetchdf()
        c.register('links',links)
        c.execute('''CREATE TEMP TABLE eligible_pool AS SELECT q.decision_id,p.pitcher_id,p.pitches_3d_before,p.hours_since_last_pitch
            FROM q JOIN links l USING(decision_id) JOIN bullpen_candidates p ON p.decision_id=l.snapshot_id
            WHERE p.nominal_eligible AND p.previous_role='RP' AND p.prior_observed_relief>0 AND p.pitcher_id<>q.outgoing_pitcher_id
                AND NOT EXISTS(SELECT 1 FROM appearance_history a WHERE a.game_pk=q.game_pk AND a.team_id=q.team_id AND a.pitcher_id=p.pitcher_id AND a.entry_at<q.anchor_at)''')
        pools=c.execute('''SELECT q.decision_id,count(p.pitcher_id) pool_rp_count,median(p.pitches_3d_before) pool_pitches3,
            median(p.hours_since_last_pitch) pool_rest FROM q LEFT JOIN eligible_pool p USING(decision_id)
            GROUP BY q.decision_id''').fetchdf()
        result=result.merge(links,on='decision_id',validate='one_to_one').merge(pools,on='decision_id',validate='one_to_one')
    result.loc[result.snapshot_at.isna(),['pool_rp_count','pool_pitches3','pool_rest']]=np.nan
    result['pitch_rest_hours']=(result.anchor_at-result.pitch_available_at)/3600
    result['entry_rest_hours']=(result.entry_at-result.entry_last_pitch_at)/3600
    result['pool_snapshot_age_minutes']=(result.anchor_at-result.snapshot_at)/60
    result['block_age_minutes']=(result.anchor_at-result.available_at)/60
    result['load_relative']=result.current_pitches/result.median_pitches
    result['lookback_complete']=result.anchor_at.ge(read(OUT/'cache.json')['earliest']+14*86400)
    for key in ['prior_games_pitches_3d','prior_games_pitches_5d']:result.loc[~result.lookback_complete,key]=np.nan
    for group in 'ABC':result[group+'_state']=result[group+'_state'].fillna(-1).astype(int)
    result['state_support']=np.where(result[[g+'_state' for g in 'ABC']].ge(0).all(axis=1),'three_known','partial_or_unknown')
    result['pitch_band']=pd.cut(result.current_pitches,[-np.inf,29,59,89,np.inf],labels=['0-29','30-59','60-89','90+']).astype(str)
    result['cell']=result.role+':'+result.phase+':'+result.pitch_band+':'+pd.cut(result.defense_lead,[-np.inf,-2,1,np.inf],labels=['behind','close','ahead']).astype(str)
    assert (result.pitch_available_at.dropna()<result.loc[result.pitch_available_at.notna(),'anchor_at']).all()
    write(result,f'features_{year}.parquet')
    rows=[]
    for (role,action,phase),g in base.groupby(['role','changed','phase']):
        included=g[g.anchor_reason.eq('included')]
        rows.append({'role':role,'changed':int(action),'phase':phase,'n':len(g),'included':len(included),
            'gap_seconds_median':float(included.clock_gap_seconds.median()) if len(included) else None,
            'gap_seconds_q90':float(included.clock_gap_seconds.quantile(.9)) if len(included) else None})
    save(f'preparation_{year}.json',{'year':year,'original':len(base),'included':len(result),'reasons':base.anchor_reason.value_counts().to_dict(),'clock_by_role_action_phase':rows})
    print(f'15.1 {year}: complete; {len(base)-len(result):,} excluded with explicit anchor reason',flush=True)


def missing_audit(year):
    print(f'15.1 {year}: classify old future-measurement censoring, labels only',flush=True)
    with n.r.connect() as c:
        c.read_parquet(str(old.OUT/f'monitoring_{year}.parquet')).create_view('q')
        c.read_parquet(str(OUT/'game_clock.parquet')).create_view('g')
        c.read_parquet(str(n.r.OUT/'appearance_history.parquet')).create_view('a')
        c.read_parquet(str(n.OUT/f'block_scores_{year}.parquet')).filter(f'alpha={n.ALPHA}').create_view('s')
        f=c.execute('''SELECT q.*,g.session_position last_session_position,g.appearance_position last_appearance_position,a.actual_pitches,
            s.game_pitches target_game_pitches,s.session_pitches target_session_pitches,s.measurement_models target_measurement_models
            FROM q ASOF LEFT JOIN g ON q.game_pk=g.game_pk AND q.outgoing_pitcher_id=g.pitcher_id AND q.decision_at>g.available_at
            LEFT JOIN a ON q.appearance_id=a.appearance_id
            LEFT JOIN s ON q.session_id=s.session_id AND q.target_block=s.block_number''').fetchdf()
    required=np.ceil(f.last_session_position/10)*10+10-f.last_session_position
    remaining=f.actual_pitches-f.last_appearance_position
    outside=f.target_game_pitches.gt(np.where(f.role.eq('SP'),100,60))|f.target_session_pitches.lt(np.where(f.role.eq('SP'),35,10))|f.target_measurement_models.ne(1)
    conditions=[f.future_observed.eq(1),f.changed.eq(1),remaining.lt(required),f.target_block.gt(f.block_number+2),f.target_block.notna()&outside,f.target_block.notna()]
    f['missing_reason']=np.select([v.fillna(False).to_numpy(bool) for v in conditions],['observed','immediate_change','insufficient_future_pitch_opportunity','incomplete_block_or_session_gap','outside_predeclared_support','measurement_or_reference_insufficient'],default='incomplete_block_or_session_gap')
    f['future_pitches_needed']=required;f['future_pitches_remaining']=remaining
    write(f[['decision_id','role','future_observed','future_bad','missing_reason','future_pitches_needed','future_pitches_remaining']],f'missing_audit_{year}.parquet')
    save(f'missing_audit_{year}.json',{'year':year,'rows':[{'role':role,'reason':reason,'n':len(g)} for (role,reason),g in f.groupby(['role','missing_reason'])],
        'scope':'old15 measurement target, diagnostic postdecision labels only; no new observation model or15.3 horizon change; physical-opportunity deficit can include later removal, not proof of fatigue'})


def protocol():
    paths=[Path(__file__),old.OUT/'manifest.json',n.OUT/'manifest.json',OUT/'pitcher_clock.parquet',OUT/'game_clock.parquet']
    for y in range(2021,2025):
        paths += [OUT/f'{name}_{y}.parquet' for name in ['features','anchor_audit','missing_audit']]
        paths += [n.old.FOUNDATION/f'{name}_{y}.parquet' for name in ['plays','decisions','bullpen_candidates']]
    return {'version':'decision_common_clock_v1','input_sha256':{p.relative_to(ROOT).as_posix():b.digest(p) for p in paths},
        'anchor':'end of immediately previous global play +1ms; previous play complete, anchor strictly before old decision, outgoing already entered; otherwise exclude with reason. This is observational risk-set anchor, not proof before unrecorded managerial intent',
        'context':'previous play known scores; within-inning previous outs/bases; new half0 outs with deterministic regular-season extra-inning runner rule only, no runner/player identity inferred; current scheduled length known. No next-batter identity/ability borrowed from future PA',
        'features':'pitch counts,72/120h other-game load, current BF, pitcher-role ability and normal residuals ASOF strictly before anchor; personal load median frozen strictly before appearance entry to avoid current-appearance history; total/game cumulative differences, current blocks may be gray; no old feature row reused after timestamp shift',
        'pool':'strictly earlier same-game/team nominal RP snapshot, remove actors already entered by anchor and outgoing; retain snapshot age/unknown, not complete current active/warmup/health availability',
        'missingness':'classify existing15 whole-future target by observed/immediate change/fewer physical pitches than required for whole fixed block/support range/measurement or reference/incomplete block or session gap; never predictors, no new RP horizon fit',
        'cohort':'inherits old15 retrospective legal/identity/completed-play selection, plus anchor exclusions; not deployment population or fully causal decision set',
        'test2025_outcomes_examined':False,'recommendation_allowed':False,'stop':'15.2'}


def freeze():
    value=protocol();path=OUT/'protocol.json'
    if path.exists():assert read(path)==value
    save('protocol.json',value);print('15.1 source/anchor/recomputed-feature/missingness protocol frozen',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['cache','prepare','missing_audit','freeze']);parser.add_argument('--year',type=int,choices=range(2021,2025));args=parser.parse_args()
    if args.stage in ['prepare','missing_audit']:globals()[args.stage](args.year)
    else:globals()[args.stage]()
