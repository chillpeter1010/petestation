"""Rank cached sources by coverage/continuity. Heuristics, not visual certification."""
import hashlib
import json
from pathlib import Path
import numpy as np
from build_team_pitch_motion import OUT,ROOT,write

def quality(raw,hand):
    rows=raw['frames'];observed=[i for i,r in enumerate(rows) if r['image'] is not None]
    if not observed:return dict(score=0,bodyCoverage=0,throwingArmCoverage=0,feetCoverage=0,reviewWindow=None,reason='no observed pitcher candidate')
    start,end=observed[0],observed[-1];span=rows[start:end+1];n=len(span)
    arm=[12,14,16] if hand=='R' else [11,13,15]
    feet=[23,24,25,26,27,28]
    valid=lambda r,ids:r['image'] is not None and min(r['confidence'][j] for j in ids)>=.65
    body=sum(r['image'] is not None for r in span)/n
    arms=sum(valid(r,arm) for r in span)/n;legs=sum(valid(r,feet) for r in span)/n
    longest=run=gap=longest_gap=0;steps=[]
    for i,r in enumerate(span):
        if r['image'] is not None:
            run+=1;longest=max(longest,run);gap=0
            if i and span[i-1]['image'] is not None:
                p=np.asarray(r['image']);old=np.asarray(span[i-1]['image'])
                torso=np.linalg.norm(p[[11,12]].mean(0)-p[[23,24]].mean(0))
                steps.append(float(np.linalg.norm(p[arm[-1]]-old[arm[-1]])/max(torso,1)))
        else:run=0;gap+=1;longest_gap=max(longest_gap,gap)
    # Leading/trailing absent or unprocessed frames are excluded, not labelled
    # successful. The selected span may still omit delivery: flag poor arm data.
    jumps=sum(v>1 for v in steps)/max(len(steps),1)
    score=max(0,40*body+35*arms+15*legs+10*longest/n-min(10,jumps*100))
    return dict(score=round(score,2),bodyCoverage=round(body,4),throwingArmCoverage=round(arms,4),feetCoverage=round(legs,4),
      reviewWindow=[rows[start]['sourceTime'],rows[end]['sourceTime']],leadingExcludedFrames=start,trailingExcludedFrames=len(rows)-end-1,
      longestObservedRunSeconds=round(longest/raw['fps'],3),longestMissingGapSeconds=round(longest_gap/raw['fps'],3),
      throwingWristAbruptStepFraction=round(jumps,4),requiresMotionReview=arms<.8 or longest_gap/raw['fps']>.15,
      limitation='Visibility and continuity ranking only; no release/contact/identity or anatomical correctness certification.')

def main():
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'));players=[]
    reports={669194:[180,196],683352:[1,382],703615:[169,280],593958:[188,205],694297:[173,190]}
    for p in manifest['players']:
        selected=json.loads((OUT/f"{p['playerId']}-review.json").read_text(encoding='utf-8'))
        candidates=[]
        for clip in p['clips']:
            # Score every cached crop, keeping different detector revisions visible.
            for cache in ['poses-identity-v3','poses-mound-v1']:
                path=OUT/cache/f"{clip['id']}.json"
                if not path.exists():continue
                raw=json.loads(path.read_text(encoding='utf-8'))
                candidates.append(dict(clipId=clip['id'],tracker=raw['trackerVersion'],rawPath=path.relative_to(ROOT).as_posix(),**quality(raw,clip['pitchHand'])))
        candidates.sort(key=lambda c:c['score'],reverse=True)
        clip=selected['clip'];raw=json.loads((OUT/clip.get('poseCache','poses-identity-v3')/f"{clip['id']}.json").read_text(encoding='utf-8'))
        current=quality(raw,clip['pitchHand']);diagnosis=None
        if p['playerId'] in reports:
            a,b=reports[p['playerId']];idx=range(a-1,min(b,len(raw['frames'])));idx=list(idx)
            diagnosis=dict(displayFrames=[a,b],rawMissingFrames=sum(raw['frames'][i]['image'] is None for i in idx),
              modelMissingFrames=sum(selected['methods']['motionbert'][i] is None for i in idx),
              throwingArmLowConfidenceObservedFrames=sum(raw['frames'][i]['image'] is not None and min(raw['frames'][i]['confidence'][j] for j in ([12,14,16] if clip['pitchHand']=='R' else [11,13,15]))<.65 for i in idx),
              trackerRejectReason='Appearance/motion/scale/confidence/ambiguity gate; old cache does not retain per-candidate rejection details.',
              inferenceReason='Runs shorter than 0.5s or density below 60% are excluded; gaps > max(3 frames,0.12s) split inference.')
        players.append(dict(playerId=p['playerId'],playerName=p['playerName'],selectedClipId=clip['id'],
          sourceArtifactSha256=hashlib.sha256((OUT/f"{p['playerId']}-review.json").read_bytes()).hexdigest(),
          userAccepted=p['playerId'] in [669203,518876],current=current,candidates=candidates,reportedFrames=diagnosis,
          selection='accepted source pinned' if p['playerId'] in [669203,518876] else 'ranked cached candidates only; no silent live-source replacement'))
    result=dict(version='pitch_reference_quality_v1',date='2026-11-07',scoreDefinition='40 body + 35 throwing-arm + 15 feet + 10 longest-run fractions; up to 10 point abrupt-wrist penalty.',
      denominator='First to last observed pitcher candidate, missing interior frames included; excluded leading/trailing frames reported separately. Not delivery completeness.',
      nextCapturePolicy='Scan from source start to source end within bounded clip duration, locate a stable pitcher track; compare up to three same-player candidates by phase/arm/feet coverage. Never fill long occlusions or promote by frame count alone.',
      automaticVisualPass=False,players=players)
    write(OUT/'quality.json',result);write(ROOT/'data/sample/petehub_pitch_motion_quality_v1.json',result)
    print([(p['playerName'],p['current']['score'],p['current']['throwingArmCoverage'],p['current']['reviewWindow']) for p in players])

if __name__=='__main__':main()
