"""Build self-contained manual review HTML, without opening/rendering it."""
from pathlib import Path
import hashlib
import json
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/ballpark/motion-method-demo-v1'
manifest=json.loads((OUT/'dataset-manifest.json').read_text(encoding='utf-8'))
clips=[c for p in sorted(OUT.glob('*-comparison.json')) if (c:=json.loads(p.read_text(encoding='utf-8'))).get('methodVersion')=='motionbert-identity-full-timeline-v3']
statuses=json.loads((OUT/'processing-status.json').read_text(encoding='utf-8')) if (OUT/'processing-status.json').exists() else {}
completed=sum(not c.get('error') for c in clips)
if not clips:raise RuntimeError('No actual model results; refuse an empty/fabricated demo')
for player in manifest['players']:
  for clip in player['clips']:
    if clip['split']!='reference' or clip['rank']>5 or any(c['clip']['id']==clip['id'] for c in clips):continue
    path=OUT/'poses-identity-v3'/f"{clip['id']}.json"
    if not path.exists():continue
    raw=json.loads(path.read_text(encoding='utf-8'))
    clips.append(dict(clip=clip,times=[r['sourceTime'] for r in raw['frames']],
      observed=[[[0,0,0] for _ in range(17)] for r in raw['frames']],methods={},metrics={},
      filled=list(range(len(raw['frames']))),width=raw['width'],height=raw['height'],inferenceSeconds=0,
      error=statuses.get(clip['id'],{}).get('error',f"Insufficient tracked source frames ({raw['detected']}/{len(raw['frames'])}); no 3D result generated.")))
clips.sort(key=lambda c:c['clip']['id'])
data=dict(clips=clips,inventory=f"Sources {len(clips)}; model comparisons {completed}; failed tracking {len(clips)-completed}. Frozen per player: reference 20, holdout 5; nested N=5/10/20 reserved. No training or held-out accuracy result yet.")
template=(ROOT/'backend/templates/pitch_motion_demo.html').read_text(encoding='utf-8')
html=template.replace('__DEMO_DATA__',json.dumps(data,separators=(',',':')).replace('</',r'<\/'))
(OUT/'index.html').write_text(html,encoding='utf-8')
report=dict(version='motion_method_screening_v1',date='2026-11-07',
  status='pending_user_method_review',demo='output/ballpark/motion-method-demo-v1/index.html',
  methods=['MediaPipe Full 33-point baseline mapped to 17 proxies','Official MotionBERT-Lite H36M global, flip augmentation'],
  trainingPerformed=False,whamExecuted=False,holdoutProcessed=False,n5n10n20ExperimentComplete=False,
  trackerVersion='appearance-lock-v3',fullSourceTimeline=True,releaseFrameVerified=False,
  userFeedback={'date':'2026-11-07','clip':'yesavage-reference-03','wrongIdentityDuringPreparation':True,
    'reportedSourceSeconds':[1.360,2.518,2.770],'prematureEndBeforeRelease':True,
    'methodPreference':'MotionBERT-Lite relatively preferred; NOT accepted'},
  sourceVideos=len(clips),modelComparisons=completed,failedTracking=len(clips)-completed,frames=sum(len(c['times']) for c in clips),
  metricsMeaning='Projection residuals against model INPUT estimates, not ground-truth error; bone CV reports instability. No measured 3D accuracy.',
  limitations=['MediaPipe to H36M proxy mapping is a domain shift','Camera-plane translation fitted; world root/depth/foot contact uncalibrated','No IK or character retarget in this demo','All visual/interaction acceptance belongs to user'],
  clips=[dict(id=c['clip']['id'],frames=len(c['times']),filled=len(c['filled']),metrics=c['metrics'],seconds=c['inferenceSeconds'],
    sourceDuration=c.get('sourceDuration'),availableFrames=c.get('availableFrames',0),missingFrames=len(c.get('missing',[])),error=c.get('error')) for c in clips],
  model=json.loads((OUT/'model-provenance.json').read_text(encoding='utf-8')),
  hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [OUT/'dataset-manifest.json',OUT/'index.html',ROOT/'backend/scripts/build_pitch_motion_demo.py',ROOT/'backend/templates/pitch_motion_demo.html']})
(ROOT/'data/sample/petehub_pitch_motion_method_demo_v1.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ['status','sourceVideos','frames','trainingPerformed','n5n10n20ExperimentComplete']}))
