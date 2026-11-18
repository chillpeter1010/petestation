"""Data/source contract checks; never opens a browser or judges motion appearance."""
from pathlib import Path
import ast
import hashlib
import json
import math
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/ballpark/motion-method-demo-v1'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
manifest=read(OUT/'dataset-manifest.json')
for player in manifest['players']:
    ref=[c for c in player['clips'] if c['split']=='reference']
    test=[c for c in player['clips'] if c['split']=='holdout']
    assert len(ref)==20 and len(test)==5
    assert len({c['playId'] for c in ref+test})==25
    assert not {c['gamePk'] for c in ref} & {c['gamePk'] for c in test}
    assert not any((OUT/c['video']).exists() for c in test),'blind-test videos must remain untouched'
    for n in [5,10,20]:assert sum(n in c['groups'] for c in ref)==n
    for c in ref[:5]:
        p=OUT/c['video'];assert p.stat().st_size==c['videoBytes']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==c['videoSha256']
model=read(OUT/'model-provenance.json')
for f in model['files']:
    p=ROOT/f['path'];assert p.stat().st_size==f['bytes']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==f['sha256']
results=[p for p in OUT.glob('*-comparison.json') if read(p).get('methodVersion')=='motionbert-identity-full-timeline-v3']
assert results and {read(p)['clip']['name'] for p in results}=={'yesavage','thompson'}
for p in results:
    c=read(p);raw=read(OUT/'poses-identity-v3'/f"{c['clip']['id']}.json")
    assert c['methodVersion']=='motionbert-identity-full-timeline-v3'
    assert raw['trackerVersion']=='appearance-lock-v3'
    assert c['times']==[r['sourceTime'] for r in raw['frames']]
    assert c['times'][0]==0 and raw['sourceDuration']-c['times'][-1]<=raw['sampleStep']/raw['fps']+.0001,'source timeline must extend to video end'
    assert all(b>a for a,b in zip(c['times'],c['times'][1:]))
    assert all(raw['frames'][i]['image'] is None for i in c['filled'])
    assert c['missing']==[i for i,frame in enumerate(c['methods']['motionbert']) if frame is None]
    assert all(c['observed'][i] is None for i in c['missing'])
    assert all(frame is None or (len(frame)==17 and all(len(j)==3 and all(math.isfinite(v) for v in j) for j in frame)) for data in c['methods'].values() for frame in data)
    assert all(len(data)==len(c['times']) for data in c['methods'].values())
    assert set(c['methods'])=={'mediapipe','motionbert'}
for file in ['prepare_pitch_motion_demo.py','pitch_motion_tracking.py','build_pitch_motion_demo.py','export_pitch_motion_demo.py','check_pitch_motion_demo.py']:
    ast.parse((ROOT/'backend/scripts'/file).read_text(encoding='utf-8'))
html=(OUT/'index.html').read_text(encoding='utf-8')
scripts=re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.S)
data=json.loads(scripts[0]);assert len(data['clips'])==10
failed=[c for c in data['clips'] if c.get('error')]
assert all(not any(c['methods'].get('motionbert',[])) for c in failed)
check=subprocess.run(['node','--check'],input=scripts[-1],text=True,encoding='utf-8',capture_output=True,timeout=15)
assert check.returncode==0,check.stderr
assert "if($('video').ended)" in scripts[-1] and "current.times.at(-1)){pause()" not in scripts[-1]
# A nearer wrong-colour batter must not replace the locked pitcher; no candidate means missing.
sys.path.insert(0,str(ROOT/'output/ballpark/f2-motion-reference-v1/pose-tools'))
import numpy as np
from pitch_motion_tracking import AppearanceLock
def candidate(x,colour):
    points=np.tile([x,60.],(33,1));points[[11,12]]=[[x-5,40],[x+5,40]]
    points[[23,24]]=[[x-4,60],[x+4,60]];points[[27,28]]=[[x-5,90],[x+5,90]]
    hist=np.zeros((12,4,4),dtype='float32');hist[colour,0,0]=1
    return dict(image=points,confidence=[1]*33,histogram=hist)
lock=AppearanceLock(100,100)
assert lock.choose([candidate(43,1)],0)[0]==0
assert lock.choose([candidate(43,2),candidate(44,1)],.02)[0]==1
assert lock.choose([candidate(44,2)],.04) is None
assert lock.choose([], .06) is None
actor=(ROOT/'frontend/components/charts/replay3d/createReplayActors.ts').read_text(encoding='utf-8')
assert 'PITCHER_DELIVERY_AVAILABLE=false' in actor and 'VIDEO_POSE_RETARGET_AVAILABLE=false' in actor
report=read(ROOT/'data/sample/petehub_pitch_motion_method_demo_v1.json')
assert not report['trainingPerformed'] and not report['holdoutProcessed'] and not report['n5n10n20ExperimentComplete']
print(f'Source/data PASS: frozen split/holdout unchanged; {len(results)} full-video timelines, {len(failed)} clips without reliable segments; explicit missing skeletons, no early cutoff, wrong-appearance/missing-candidate regression, hashes and syntax. No visual/identity/3D accuracy acceptance.')
