"""A bounded, user-reported L/R association experiment; not ground/contact recovery."""
from pathlib import Path
import copy
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/ballpark/motion-method-demo-v1'


def resolve_lower_leg_sides(raw,start=2.70,end=3.02):
    """Two-state temporal assignment, with original labels at reviewed endpoints.

    Changes labels only. Never moves a point, forces a foot down or edits raw data.
    Window/endpoints are a user-report-specific experiment, not automatic all-pitch logic.
    """
    derived=copy.deepcopy(raw)
    frames=[r for r in derived['frames'] if start<=r['sourceTime']<=end]
    if len(frames)<3 or any(r['image'] is None for r in frames):
        raise ValueError('The scoped side-assignment review requires observed endpoint frames')
    left=[25,27,29,31];right=[26,28,30,32];weights=[.15,.4,.225,.225]
    def points(row,state):
        ids=left+right if state==0 else right+left
        return [[row['image'][j][0]/raw['width'],row['image'][j][1]/raw['height']] for j in ids]
    costs=[[0,float('inf')]];backs=[]
    for i in range(1,len(frames)):
        new=[];back=[]
        for state in [0,1]:
            current=points(frames[i],state);choices=[]
            for previous in [0,1]:
                old=points(frames[i-1],previous)
                distance=sum(weights[j%4]*sum((a-b)**2 for a,b in zip(current[j],old[j])) for j in range(8))
                choices.append(costs[-1][previous]+distance+(1e-5 if state else 0))
            choice=min(range(2),key=lambda k:choices[k]);new.append(choices[choice]);back.append(choice)
        costs.append(new);backs.append(back)
    state=0;states=[0]
    for back in reversed(backs):state=back[state];states.append(state)
    states.reverse();changed=[]
    for row,state in zip(frames,states):
        if not state:continue
        for key in ['image','world','confidence']:
            for a,b in zip(left,right):row[key][a],row[key][b]=row[key][b],row[key][a]
        changed.append(row['sourceTime'])
    return derived,changed


def main():
    if '--export-only' in sys.argv:
        cache=OUT/'thompson-foot-review-data.json'
        if cache.exists():data=json.loads(cache.read_text(encoding='utf-8'))
        else:
            import re
            html=(OUT/'thompson-foot-review.html').read_text(encoding='utf-8')
            data=json.loads(re.search(r'<script id="demoData" type="application/json">(.*?)</script>',html,re.S).group(1))
        data.update(pageTitle='Thompson ref01 · 左腳遮擋比較',pageIntro='只比較同一支影片的下肢側別修正；原始標點與 MotionBERT 結果可切換。',pageNotice='這是短段左右下肢側別推估，不是接地量測或自動辨識全體投手；沒有把腳鎖在地上。原片與其他影片未改。')
        cache.write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
        template=(ROOT/'backend/templates/pitch_motion_demo.html').read_text(encoding='utf-8')
        (OUT/'thompson-foot-review.html').write_text(template.replace('__DEMO_DATA__',json.dumps(data,separators=(',',':')).replace('</',r'<\/')),encoding='utf-8')
        print('Re-exported foot review without inference');return
    import build_pitch_motion_demo as build
    import torch
    torch.set_num_threads(4)
    preserved=OUT/'yesavage-reference-05-comparison.json'
    ref5_hash=hashlib.sha256(preserved.read_bytes()).hexdigest()
    source=OUT/'poses/thompson-reference-01.json'
    original=json.loads(source.read_text(encoding='utf-8'))
    # Same old source interval shown in the user's 198-frame screenshots.
    original={**original,'frames':[r for r in original['frames'] if .50<=r['sourceTime']<=3.80]}
    corrected,changed=resolve_lower_leg_sides(original)
    model=build.DSTformer(dim_in=3,dim_out=3,dim_feat=256,dim_rep=512,depth=5,num_heads=8,
      mlp_ratio=4,num_joints=17,maxlen=243,att_fuse=True)
    checkpoint=torch.load(OUT/'weights/motionbert-lite.bin',map_location='cpu',weights_only=True)
    model.load_state_dict({k.removeprefix('module.'):v for k,v in checkpoint['model_pos'].items()},strict=True);model.eval()
    before=build.infer_segment(model,original);after=build.infer_segment(model,corrected)
    base=json.loads((OUT/'thompson-reference-01-comparison.json').read_text(encoding='utf-8'))
    review=dict(clip=base['clip'],times=base['times'],width=base['width'],height=base['height'],
      sourceDuration=base['sourceDuration'],observed=[None]*len(base['times']),
      methods={k:[None]*len(base['times']) for k in ['mediapipe','motionbert']},
      originalMotionbert=[None]*len(base['times']),correctedObserved=[None]*len(base['times']),
      filled=[],segments=[],metrics={'original':before['metrics'],'sideAssignmentCandidate':after['metrics']},
      reviewNote='Ryan ref01 足部遮擋比較：沿用你回報的舊來源候選區間，只有左右膝踝／腳跟腳尖側別的推估修正；身分、接地與三維仍待驗。原始模式可切換。',
      footSideExperiment=True)
    indices={r['sourceFrame']:i for i,r in enumerate(json.loads((OUT/'poses-identity-v3/thompson-reference-01.json').read_text())['frames'])}
    mapped=[]
    for k,row in enumerate(original['frames']):
        i=indices[row['sourceFrame']];mapped.append(i)
        review['observed'][i]=before['observed'][k];review['correctedObserved'][i]=after['observed'][k]
        review['methods']['mediapipe'][i]=before['methods']['mediapipe'][k]
        review['methods']['motionbert'][i]=after['methods']['motionbert'][k]
        review['originalMotionbert'][i]=before['methods']['motionbert'][k]
    review['segments']=[{'first':mapped[0],'last':mapped[-1]}]
    template=(ROOT/'backend/templates/pitch_motion_demo.html').read_text(encoding='utf-8')
    data=dict(clips=[review],pageTitle='Thompson ref01 · 左腳遮擋比較',pageIntro='只比較同一支影片的下肢側別修正；原始標點與 MotionBERT 結果可切換。',pageNotice='這是短段左右下肢側別推估，不是接地量測或自動辨識全體投手；沒有把腳鎖在地上。原片與其他影片未改。',inventory='One reported Ryan Thompson ref01 case; label-association experiment only. No new detector, training or ground measurement. Yesavage ref5 preserved.')
    (OUT/'thompson-foot-review-data.json').write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
    html=template.replace('__DEMO_DATA__',json.dumps(data,separators=(',',':')).replace('</',r'<\/'))
    (OUT/'thompson-foot-review.html').write_text(html,encoding='utf-8')
    evidence=dict(version='lower_leg_side_review_v1',date='2026-11-07',status='pending_user',
      clip='thompson-reference-01',source=str(source.relative_to(ROOT)),sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),
      mode='label-association experiment on original user-reviewed source candidate; no ground locking or exact biomechanics',
      window=[2.70,3.02],endpointLabels='original anatomical labels assumed at both window endpoints',
      changedFrames=len(changed),changedSourceSeconds=changed,rawSourceModified=False,
      ref5PreservedSha256=ref5_hash,ref5UserReport='User says Yesavage ref5 reasonable; snapshot version not established, do not generalize acceptance',
      demo='output/ballpark/motion-method-demo-v1/thompson-foot-review.html',
      checks='Only identity permutations in derived lower-leg points; original data/other clips unchanged; visual pending')
    (ROOT/'data/sample/petehub_pitch_foot_occlusion_review_v1.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    assert hashlib.sha256(preserved.read_bytes()).hexdigest()==ref5_hash
    print(json.dumps({'changedFrames':len(changed),'range':[min(changed),max(changed)],'ref5Unchanged':True}))


if __name__=='__main__':main()
