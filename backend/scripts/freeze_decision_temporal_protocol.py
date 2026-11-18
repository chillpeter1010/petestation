from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.decision_temporal_common import OUT,ROOT,VERSION,protocol,fingerprint,save


if __name__=='__main__':
    spec=protocol();target=OUT/'protocol.json'
    if target.exists() and json.loads(target.read_text(encoding='utf-8'))!=spec:
        raise ValueError('Existing protocol differs; use a new version rather than retuning the frozen experiment')
    save(target,spec)
    frozen=[]
    for directory in ['stuff_plus','location_plus']:
        for path in (ROOT/'models'/directory).glob('*metadata.json'):
            frozen.append({'path':str(path),'sha256':__import__('hashlib').sha256(path.read_bytes()).hexdigest()})
    guard_path=OUT/'formal_model_guards.json'
    if guard_path.exists():
        assert json.loads(guard_path.read_text(encoding='utf-8'))==frozen,'Formal metadata changed; do not silently rebaseline guards'
    else:save(guard_path,frozen)
    save(ROOT/'sample/petehub_pitcher_decision_slice6_v1.json',{'slice':6,'version':VERSION,'status':'protocol_frozen',
        'protocol_sha256':fingerprint(spec),'folds':spec['folds'],'warmup':'2021 H1; state baseline warmup additionally Jul–Aug',
        'formal_models_preserved':True,'feature_registry':spec['feature_availability'],'holdout_policy':spec['holdout_policy'],
        'research_plus_method':spec['plus_method'],'individual_ranking_allowed':False})
    print('Frozen temporal protocol:',fingerprint(spec),flush=True)
