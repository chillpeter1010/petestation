"""15.5 source/clock/feature/forecast/probability/split/replay accounting only."""
import argparse
from pathlib import Path
import sys
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_pe_models as m
from scripts.audit_decision_overlap_revision import hashes


def feature_audit():
    f,q=m.f,m.q
    all_pa=pd.concat([pd.read_parquet(f.OUT/f'pa_cache_{year}.parquet') for year in range(2021,2025)],ignore_index=True)
    personal={k:g.sort_values(['available_at','game_pk','at_bat_number']) for k,g in all_pa.groupby(['pitcher_id','role'])}
    total=0
    for year in range(2021,2025):
        frame=pd.read_parquet(f.OUT/f'features_{year}.parquet');base=q.base.features(year)
        assert frame.decision_id.is_unique and set(frame.decision_id)==set(base.decision_id)
        assert frame.anchor_at.lt(frame.old_decision_at).all()
        clocks=[('pe_available_at','anchor_at'),('pe_reference_at','entry_at'),('ff_reference_at','entry_at'),('lineup_available_at','anchor_at')]
        clocks += [(f'forecast{slot}_{kind}_at','anchor_at') for slot in [1,2,3] for kind in ['identity','history','league']]
        for field,clock in clocks:
            known=frame[field].notna();assert frame.loc[known,field].lt(frame.loc[known,clock]).all(),(year,field)
        assert frame.loc[frame.changed.eq(1),['y_pa','y_run']].isna().all().all()
        assert frame.loc[~frame.target_observed,['y_pa','y_run']].isna().all().all()
        known=frame.target_observed;assert frame.loc[known,'actor_pitcher_id'].eq(frame.loc[known,'outgoing_pitcher_id']).all()
        assert frame.loc[known,'final_pitcher_id'].eq(frame.loc[known,'outgoing_pitcher_id']).all()
        assert frame.loc[known,'physical_actors'].eq(1).all() and frame.loc[known,'target_start'].ge(frame.loc[known,'anchor_at']).all()
        raw=frame.observed_pa_result;category=np.where(frame.label_outs_after.gt(frame.label_outs).fillna(False),'other_out','other_reach').astype(object)
        for event,group in [('strikeout','k'),('strikeout_double_play','k'),('walk','bb'),('hit_by_pitch','hbp'),('home_run','hr'),('single','single'),('double','double'),('triple','triple')]:category[raw.eq(event).fillna(False).to_numpy(bool)]=group
        coded=pd.Series(category).map({key:i for i,key in enumerate(f.OUTCOMES)}).to_numpy()
        assert np.array_equal(frame.loc[known,'y_pa'],coded[known])
        assert np.array_equal(frame.loc[known,'y_run'],frame.loc[known,'target_runs'].gt(0).astype(int))
        pa=pd.read_parquet(f.OUT/f'pa_cache_{year}.parquet');by_app={k:g.sort_values(['available_at','at_bat_number']) for k,g in pa.groupby('appearance_id')}
        with q.n.r.connect() as c:
            c.read_parquet(str(q.n.r.OUT/f'pa_observations_{year}.parquet')).create_view('p')
            lineup=c.execute('''SELECT game_pk,half,coalesce(actual_batter_id,batter_id) batter_id,
                coalesce(available_at,epoch(try_cast(end_time AS TIMESTAMPTZ))) available_at,
                row_number() OVER(PARTITION BY game_pk,half ORDER BY at_bat_number) ordinal
                FROM p WHERE is_complete AND is_batter_faced''').fetchdf()
        by_game={k:g for k,g in lineup.groupby(['game_pk','half'])}
        sample=frame.sample(min(96,len(frame)),random_state=155)
        for row in sample.itertuples():
            past=by_app.get(row.appearance_id,pa.iloc[:0]);past=past[past.available_at.lt(row.anchor_at)]
            if len(past):
                assert past.available_at.max()==row.pe_available_at
                for window in [1,2,3]:
                    tail=past.pe.tail(window);expected=float(tail.sum()) if len(tail)==window and tail.notna().all() else np.nan
                    assert np.isclose(getattr(row,f'pe_last{window}'),expected,equal_nan=True)
                assert np.isclose(row.pe_cumulative_observed,past.pe.sum())
                assert np.isclose(row.pe_cumulative_coverage,past.pe.notna().mean())
                count=past.ff_n.sum();mean=past.ff_sum.sum()/count if count else np.nan
                assert np.isclose(row.ff_delta_prefix,past.ff_mean.iloc[-1]-mean,equal_nan=True)
            hist=personal.get((row.outgoing_pitcher_id,row.role),all_pa.iloc[:0]);hist=hist[hist.available_at.lt(row.entry_at)]
            pe=hist[hist.pe.notna()].tail(50);ff=hist[hist.ff_n.gt(0)&hist.physical_actors.eq(1)].tail(50)
            assert np.isclose(row.pe_entry_mean,pe.pe.mean() if len(pe)>=10 else np.nan,equal_nan=True)
            assert np.isclose(row.ff_entry_mean,ff.ff_mean.mean() if len(ff)>=10 else np.nan,equal_nan=True)
            game=by_game[(row.game_pk,row.half)];past_lineup=game[game.available_at.lt(row.anchor_at)]
            seen=past_lineup.ordinal.max() if len(past_lineup) else 0
            assert seen==row.seen_pa_count
            for slot in [1,2,3]:
                expected_slot=(seen+slot-1)%9+1
                prev=past_lineup[((past_lineup.ordinal-1)%9+1).eq(expected_slot)].sort_values('ordinal')
                expected=prev.batter_id.iloc[-1] if len(prev) else np.nan
                assert np.isclose(getattr(row,f'forecast{slot}_id'),expected,equal_nan=True)
        coverage=m.read(f.OUT/f'coverage_{year}.json')
        for record in coverage['coverage']:
            part=frame[frame.role.eq(record['role'])]
            assert record['n']==len(part) and record['target_observed']==int(part.target_observed.sum())
            assert record['feature_nonmissing']=={key:int(part[key].notna().sum()) for key in f.PE+f.PERSONAL+f.LINEUP}
            assert record['lineup_status']==part.lineup_status.value_counts().to_dict()
        total+=len(frame);print(f'{year}: full clocks/censoring/categories/coverage and sampled direct prefix/personal/lineup reconstruction checked',flush=True)
    assert total==546880
    return total


def main():
    q=m.q;previous=sum(hashes(folder) for folder in m.entry_folders());assert previous==1556
    new=hashes(m.f.OUT)+hashes(m.OUT)
    assert m.read(m.OUT/'protocol.json')==m.protocol();total=feature_audit()
    guard=m.read(m.OUT/'confirmation_guard.json');assert not guard['2024_outputs_present']
    for name,sha in guard['inputs'].items():assert q.b.digest(m.OUT/name)==sha
    assert (m.OUT/'confirmation_guard.json').stat().st_mtime_ns<min(p.stat().st_mtime_ns for p in m.OUT.glob('model_2024_*.joblib'))
    selection=m.read(m.OUT/'selection.json');assert not selection['selection_uses2024']
    tasks=0
    with threadpool_limits(limits=2):
        for year in [2022,2023,2024]:
            past=pd.concat([m.design(pd.read_parquet(m.f.OUT/f'features_{y}.parquet')) for y in range(2021,year)],ignore_index=True)
            for role in ['SP','RP']:
                source=past[past.role.eq(role)&past.game_closed_at.lt(pd.Timestamp(f'{year}-01-01',tz='UTC').timestamp())]
                fit_all,cal_all,flow=q.temporal_partition(source);fit=fit_all[fit_all.target_observed];cal=cal_all[cal_all.target_observed]
                if len(fit)>m.FIT_CAP:fit=fit.sample(m.FIT_CAP,random_state=m.SEED).sort_values(['anchor_at','decision_id'])
                split=pd.read_parquet(m.OUT/f'split_{year}_{role}.parquet')
                assert set(split.loc[split.fit_used,'decision_id'])==set(fit.decision_id)
                assert set(split.loc[split.partition.eq('calibration'),'decision_id'])==set(cal_all.decision_id)
                assert set(fit_all.game_pk).isdisjoint(cal_all.game_pk)
                info=m.read(m.OUT/f'fit_{year}_{role}.json');assert info['flow']==flow
                assert info['fit_last_label']<info['cal_first_anchor']<=info['cal_last_label']<info['validation_first_anchor']
                frame=pd.read_parquet(m.OUT/f'scored_{year}_{role}.parquet');raw=pd.read_parquet(m.f.OUT/f'features_{year}.parquet')
                assert frame.decision_id.is_unique and set(frame.decision_id)==set(raw.loc[raw.role.eq(role),'decision_id'])
                assert cal_all.game_closed_at.max()<frame.anchor_at.min()
                primary=m.primary_mask(frame,role);part=frame[primary&frame.target_observed];y=part.y_pa.to_numpy(int)
                result=m.read(m.OUT/f'results_{year}_{role}.json');assert result['observed_n']==len(part)
                chosen=selection['selected'][role]['config']
                for task,configs in [('pa',m.CONFIGS),('run',m.RUN_CONFIGS)]:
                    for config in configs:
                        bundle=joblib.load(m.OUT/f'model_{year}_{role}_{task}_{config}.joblib')
                        trans=bundle['model'][0];numeric,cat=m.columns(config)
                        assert trans.transformers_[0][2]==numeric and trans.transformers_[1][2]==cat
                        assert not {'changed','target_observed','y_pa','y_run','actual_target_batter_id','old_decision_at'}&set(numeric+cat)
                        classes=9 if task=='pa' else 2;expected=(np.bincount(fit['y_'+task].to_numpy(int),minlength=classes)+1)/(len(fit)+classes)
                        assert np.allclose(expected,bundle['prior'])
                        probability=m.predict(bundle,frame.iloc[:64])
                        if task=='pa':
                            assert np.allclose(probability,frame[[f'{config}_p{k}' for k in range(9)]].iloc[:64],atol=1e-12)
                            p=part[[f'{config}_p{k}' for k in range(9)]].to_numpy();metric=m.metrics_pa(y,p,bundle['prior'])
                            row=next(r for r in result['pa'] if r['config']==config)
                            assert np.isclose(metric['log_loss'],row['metrics']['log_loss']) and np.isclose(metric['nonout']['auc'],row['metrics']['nonout']['auc'])
                            if config==chosen:
                                base=part[[f'hgb_base_p{k}' for k in range(9)]].to_numpy()
                                interval=m.cluster_delta(part,-np.log(p[np.arange(len(y)),y])+np.log(base[np.arange(len(y)),y]),seed=m.SEED+year+m.CONFIGS.index(config))
                                assert interval==row['delta_log_loss']
                        else:
                            assert np.allclose(probability[:,1],frame[config+'_run'].iloc[:64],atol=1e-12)
                            cut=float(np.quantile(m.predict(bundle,cal_all)[:,1],.9));assert np.isclose(cut,bundle['warning_threshold'])
                            warning=pd.read_parquet(m.OUT/f'warning_{year}_{role}_{config}.parquet')
                            assert set(warning.decision_id)==set(frame.decision_id) and warning.loc[warning.emitted,'appearance_id'].is_unique
                            assert warning.loc[warning.emitted,'high'].all()
                            summary=next(r for r in result['warnings'] if r['config']==config)
                            emitted=frame.set_index('decision_id').loc[warning.loc[warning.emitted,'decision_id']]
                            assert len(emitted)==summary['alerts'] and int((~emitted.target_observed).sum())==summary['unknown_alerts']
                            assert int(emitted.y_run.sum())==summary['true_observed']
                        tasks+=1
                print(f'{year}/{role}: seven common-sample models, priors, clocks, direct forecasts, selected interval and past-cal warning thresholds checked',flush=True)
    assert tasks==42==len(list(m.OUT.glob('model_*.joblib')))
    for role in ['SP','RP']:
        ranked=[]
        for config in m.CONFIGS:
            rows=[next(r for r in m.read(m.OUT/f'results_{year}_{role}.json')['pa'] if r['config']==config) for year in [2022,2023]]
            ranked.append({'role':role,'config':config,'failed_folds':sum(not r['predictive_gate'] for r in rows),'mean_log_loss':float(np.mean([r['metrics']['log_loss'] for r in rows]))})
        ranked=sorted(ranked,key=lambda r:(r['failed_folds'],r['mean_log_loss'],m.CONFIGS.index(r['config'])))
        assert ranked==selection['selected'][role]['ranking']
    evidence=m.read(m.ROOT/'data/sample/petehub_pitcher_decision_pe_revision_v1.json');assert evidence==m.read(m.OUT/'evidence.json')
    assert evidence['flow']=={'progress':'48/55','models_pa':30,'models_run':12,'features_boundaries':total}
    assert not evidence['recommendation_allowed'] and not evidence['slice16_entry_allowed'] and not evidence['test2025_outcomes_examined']
    assert evidence['balance_reference']==m.read(m.f.entry.OUT/'evidence.json')['primary_folds']
    project=next(p for p in m.read(m.ROOT/'docs/PROJECT_TRACKER.json')['projects'] if p['id']=='pitcher-decision-support')
    assert len(project['slices'])==55 and sum(p['status']=='done' for p in project['slices'])==48
    items={p['id']:p for p in project['slices']};assert all(items[s]['status']=='done' for s in ['15.5.1','15.5.2','15.5.3','15.5.4'])
    assert all(items[s]['status']=='planned' for s in ['16','17','18','19','20','21']) and '15.5.4' in items['16']['depends_on']
    front=m.read(m.ROOT/'frontend/data/pitcherDecisionPlan.json');assert front['project']==project and front['peRevision']==evidence
    for name,file in [('entryReview','entry_review_v1'),('rpTargetResearch','rp_targets_v1'),('signalLights','signal_lights_v2')]:assert front[name]==m.read(m.ROOT/f'data/sample/petehub_pitcher_decision_{file}.json')
    report={'version':'decision_pe_revision_source_audit_v1','previous_artifacts':previous,'new_artifacts':new,'common_boundaries':total,'models':42,'progress':'48/55',
        'stop':'15.5.4','recommendation_allowed':False,'slice16_entry_allowed':False,'test2025_outcomes_examined':False,'visual_acceptance':'pending user',
        'checks':'source/clock/prefix/forecast hypotheses/actor/labels/splits/probabilities/selection/selected uncertainty/warning-threshold/accounting only; not causal or visual acceptance'}
    m.save('audit.json',report);q.b.save_json(m.ROOT/'data/sample/petehub_pitcher_decision_pe_revision_audit_v1.json',report)
    print('15.5.1-4 source checks passed; outcome research does not promote original models or16',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--features-only',action='store_true');args=parser.parse_args()
    if args.features_only:feature_audit()
    else:main()
