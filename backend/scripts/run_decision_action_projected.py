"""Memory-only column projection for the frozen baseline-only14.1 simulation.

No model/input file or scientific setting is changed. The central model must
match the completed full-column run exactly before bootstrap simulations proceed.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import build_decision_action_revision as a


def main():
    assert json.loads((a.OUT/'protocol.json').read_text('utf-8'))==a.protocol()
    selections=json.loads((a.u.OUT/'validation.json').read_text('utf-8'))['roles']
    assert all(row['selected']=='baseline' for row in selections.values()),'Projection is limited to baseline-only simulations'
    runtime=a.OUT/'runtime_projection';runtime.mkdir(exist_ok=True)
    reference=runtime/'central_full_columns.parquet'
    if not reference.exists():shutil.copyfile(a.OUT/'scenario_model_0.parquet',reference)
    needed=set(a.b.LEVELS['matchup'][0]+a.b.LEVELS['matchup'][1])-{'pitcher_log_n','batter_log_n'}
    needed.update(['decision_id','option_pitcher_id','forecast_role','research_home_we','research_re','first_feature_extrapolated',
        'pitcher_own_split_n','pitcher_own_all_n','batter_own_split_n','batter_own_all_n','pitches_5d_before'])
    original_read=pd.read_parquet;original_write=pd.DataFrame.to_parquet
    checked=False
    def projected_read(path,*args,**kwargs):
        if isinstance(path,(str,Path)) and Path(path).resolve()==(a.OUT/'options.parquet').resolve():
            kwargs['columns']=sorted(needed)
        return original_read(path,*args,**kwargs)
    def verified_write(frame,path,*args,**kwargs):
        nonlocal checked
        result=original_write(frame,path,*args,**kwargs)
        if isinstance(path,(str,Path)) and Path(path).resolve()==(a.OUT/'scenario_model_0.parquet').resolve():
            pd.testing.assert_frame_equal(original_read(path),original_read(reference),check_exact=True)
            checked=True
            a.save('runtime_projection.json',{'version':'baseline_input_projection_v1','protocol_sha256':a.b.digest(a.OUT/'protocol.json'),
                'runner_sha256':a.b.digest(Path(__file__)),'projected_columns':sorted(needed),
                'central_full_vs_projected':'exact_dataframe_equality','reference_sha256':a.b.digest(reference),
                'models_inputs_settings_random_paths_changed':False})
            print('14.1 full central model EXACTLY matches projected-column run; all frozen inputs/settings unchanged',flush=True)
        return result
    pd.read_parquet=projected_read;pd.DataFrame.to_parquet=verified_write
    try:a.simulate()
    finally:pd.read_parquet=original_read;pd.DataFrame.to_parquet=original_write
    assert checked
    a.finalize()


if __name__=='__main__':main()
