"""Check the scoped label permutation, not the appearance or truth of a pose."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from review_pitch_foot_occlusion import resolve_lower_leg_sides
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/ballpark/motion-method-demo-v1'
raw=json.loads((OUT/'poses/thompson-reference-01.json').read_text(encoding='utf-8'))
raw={**raw,'frames':[r for r in raw['frames'] if .5<=r['sourceTime']<=3.8]}
original=json.dumps(raw,sort_keys=True)
fixed,changed=resolve_lower_leg_sides(raw)
assert json.dumps(raw,sort_keys=True)==original,'raw points must not change'
assert len(changed)==6 and min(changed)>2.84 and max(changed)<2.93
affected={25,26,27,28,29,30,31,32}
for before,after in zip(raw['frames'],fixed['frames']):
    for key in ['image','world','confidence']:
        for j in range(33):
            if j not in affected or before['sourceTime'] not in changed:assert before[key][j]==after[key][j]
        assert sorted(map(str,before[key]))==sorted(map(str,after[key])),'no invented/moved joint coordinates'
    assert before['sourceFrame']==after['sourceFrame'] and before['sourceTime']==after['sourceTime']
# Regression from the reported frame: original left ankle copied the airborne right side.
before=min(raw['frames'],key=lambda r:abs(r['sourceTime']-2.861));after=min(fixed['frames'],key=lambda r:abs(r['sourceTime']-2.861))
assert after['image'][27]==before['image'][28] and after['image'][28]==before['image'][27]
e=json.loads((ROOT/'data/sample/petehub_pitch_foot_occlusion_review_v1.json').read_text())
assert hashlib.sha256((OUT/'yesavage-reference-05-comparison.json').read_bytes()).hexdigest()==e['ref5PreservedSha256']
html=(OUT/'thompson-foot-review.html').read_text(encoding='utf-8')
scripts=re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.S)
data=json.loads(scripts[0]);assert len(data['clips'])==1
c=data['clips'][0];assert c['clip']['id']=='thompson-reference-01' and c['footSideExperiment']
assert len(c['times'])==804 and c['times'][0]==0
assert c['methods']['motionbert']!=c['originalMotionbert']
syntax=subprocess.run(['node','--check'],input=scripts[-1],text=True,encoding='utf-8',capture_output=True,timeout=15)
assert syntax.returncode==0,syntax.stderr
print('Source PASS: six derived lower-leg L/R permutations only; raw/source times/other joints and Yesavage ref5 unchanged; full source timeline, original/corrected outputs and JS syntax. No ground/contact or visual acceptance.')
