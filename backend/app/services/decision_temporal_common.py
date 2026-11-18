"""Frozen research-only temporal contracts for Pitcher Decision Slices 6–10."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]/'data'
BASE=ROOT/'research/decision_support_pipeline_20261114'
OUT=ROOT/'research/decision_support_temporal_20261114'
VERSION='decision_temporal_research_v1'
FOLDS=[
    {'id':'2021_h2','train_end':'2021-07-01','score_start':'2021-07-01','score_end':'2022-01-01'},
    {'id':'2022','train_end':'2022-01-01','score_start':'2022-01-01','score_end':'2023-01-01'},
    {'id':'2023','train_end':'2023-01-01','score_start':'2023-01-01','score_end':'2024-01-01'},
    {'id':'frozen_2024','train_end':'2024-01-01','score_start':'2024-01-01','score_end':'2027-01-01'},
]
PHYSICAL=['release_speed','release_spin_rate','release_extension','release_pos_x','release_pos_z','pfx_x','pfx_z',
          'spin_cos','spin_sin','arm_angle','prior_velo_delta','prior_hb_delta','prior_ivb_delta','pitch_type_code','throw_left']
LOCATION=['plate_x','plate_z_norm','balls_before','strikes_before','outs_before','base_state_before','pitch_type_code','throw_left','bat_left']
PITCH_CODES=['FF','SI','FC','FA','SL','ST','CU','KC','CS','SV','CH','FS','FO','KN','EP','SC']


def save(path: Path,value: object) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def fold_for(time: str) -> dict | None:
    return next((f for f in FOLDS if f['score_start']<=time[:10]<f['score_end']),None)


def compatible(official: dict, source: dict) -> bool:
    a,b=official.get('speed'),source.get('release_speed')
    if a is not None and b is not None and abs(a-b)>.4:return False
    a,b=official.get('type'),source.get('pitch_type')
    if a and b and a!=b:return False
    for a,b in [(official.get('x'),source.get('plate_x')),(official.get('z'),source.get('plate_z'))]:
        if a is not None and b is not None and abs(a-b)>.15:return False
    return True


def align(official: list[dict], source: list[dict]) -> dict[int,int]:
    """Unique order-preserving maximum matching; ambiguous pairs remain absent."""
    n,m=len(official),len(source)
    if n==m and all(compatible(a,b) for a,b in zip(official,source)):
        return dict(zip(range(n),range(m)))
    ok=[[compatible(a,b) for b in source] for a in official]
    forward=[[0]*(m+1) for _ in range(n+1)]
    back=[[0]*(m+1) for _ in range(n+1)]
    for i in range(n):
        for j in range(m):forward[i+1][j+1]=max(forward[i][j+1],forward[i+1][j],forward[i][j]+int(ok[i][j]))
    for i in range(n-1,-1,-1):
        for j in range(m-1,-1,-1):back[i][j]=max(back[i+1][j],back[i][j+1],back[i+1][j+1]+int(ok[i][j]))
    pairs=[(i,j) for i in range(n) for j in range(m) if ok[i][j] and forward[i][j]+1+back[i+1][j+1]==forward[n][m]]
    return {i:j for i,j in pairs if sum(a==i for a,b in pairs)==1 and sum(b==j for a,b in pairs)==1}


def protocol() -> dict:
    return {'version':VERSION,'date':'2026-11-14','status':'frozen_before_training','folds':FOLDS,
        'outer_split':{'train':'2021–2023','validation':'2024','test':'2025','retrospective_deployment':'2026'},
        'holdout_policy':'2025/2026 score/coverage only; no outcome performance selection in Slices 6–10. Existing years already examined elsewhere; not prospective.',
        'label_availability':'Training games must finish before train_end; source delta_run_exp and home_win_exp are not training targets.',
        'target':'Pitcher-positive count/base-out RE change using training-only reference tables and completed official events.',
        'plus_method':'Research Location: expected run value from location/context. Research Stuff: physical prediction of residual after location/context model. Distinct from frozen formal marginal-context Stuff+.',
        'hgb':{'max_iter':70,'max_leaf_nodes':15,'learning_rate':.08,'min_samples_leaf':80,'l2_regularization':10.,'max_bins':128,'early_stopping':False,'random_state':20261114},
        'maximum_training_rows':300000,'sampling':'fixed hash of canonical event ID, no outcome-based sampling',
        'primary_fastball':'Prior closed appearances only, among FF/SI/FC; at least 20 prior pitches. Missing reference retained, not season-end backfill.',
        'scale':'100 + 10 train-reference SD units; separate model/reference IDs; 110 does not mean 10% better; no median forcing.',
        'prefix':{'SP':{'early':20,'late_minimum':15,'exact_early_minimum':3,'max_pitches':100},
                  'RP':{'early':5,'late_minimum':5,'exact_early_minimum':2,'max_pitches':60},
                  'fixed_mix_minimum':.8,'physical_component_minimum':.75,'ridge_alpha':10.,'early_prior_n':5.,'reliability_prior_n':20.,'interval':'80% sampling interval; model uncertainty not fully included'},
        'state_folds':'2021 Sep–Dec from scored Jul–Aug warmup; 2022 from 2021 H2; 2023 from 2021 H2–2022; freeze through 2023 for 2024–2026.',
        'state_gates':'SP early20 + late15, RP early5 + late5; interval and sample support; never combine Quality/Physical/Command into energy.',
        'context_reference':'Prior completed games only; WE training/calibration split chronologically 80/20 within reference; RE 24-state partial pooling; LI expected absolute WE swing from prior state transitions, not same-year realized absolute WPA.',
        'context_minimum_n':30,'we_max_iter':90,'we_platt_C':1.,
        'feature_availability':{'pitch_physics':'after delivery only','prefix_state':'strictly before decision','candidate':'prior appearances only','roster':'confidence flags, no individual ranking','outcomes':'label table only'},
        'quality_filters':['unknown base state','source clock regression or fallback','ambiguous pitch alignment','position switches','compound substitutions','warmup','early-history censoring'],
        'validation':'2024 diagnostics only; no retuning after diagnostics. Failed/uncertain variants stay research-only; no formal replacement.',
        'prohibited':['2025/2026 outcomes for tuning','same-season full primary-fastball average','full-game state as prefix','missing LI=1','missing Plus=100','individual bullpen recommendation'],
        'method_sources':['https://library.fangraphs.com/misc/li/','https://library.fangraphs.com/misc/re24/']}
