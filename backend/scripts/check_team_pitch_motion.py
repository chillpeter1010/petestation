"""Focused source/data checks; never renders or certifies motion/identity."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
from build_team_pitch_motion import OUT,MODEL,associate_sides,write

def main():
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    roster=json.loads((OUT/'roster-source.json').read_text(encoding='utf-8'))
    active={p['person']['id'] for p in roster['payload']['roster'] if p['position']['type']=='Pitcher'}
    model_hash=hashlib.sha256((MODEL/'weights/motionbert-lite.bin').read_bytes()).hexdigest()
    preserved=MODEL/'yesavage-reference-05-comparison.json'
    assert hashlib.sha256(preserved.read_bytes()).hexdigest()=='f2b3a65fefd7a2ea6856bbfa230b66cf35fd981a85db5c9ab1130c05a0ad0fe2'
    rows=[]
    for player in manifest['players']:
        pid=player['playerId'];assert pid in active and player['starts2026']>=3
        target=OUT/f'{pid}-review.json';data=json.loads(target.read_text(encoding='utf-8'))
        clip=data['clip'];assert clip['playerId']==pid and clip['id']==player['selectedClipId']
        source=OUT/clip.get('poseCache','poses-identity-v3')/f"{clip['id']}.json"
        raw=json.loads(source.read_text(encoding='utf-8'));raw_snapshot=json.dumps(raw,sort_keys=True)
        corrected,association=associate_sides(raw)
        assert json.dumps(raw,sort_keys=True)==raw_snapshot
        assert association==data['sideAssociation']
        changed=set(association['changedSourceSeconds'])
        lower={25,26,27,28,29,30,31,32}
        for a,b in zip(raw['frames'],corrected['frames']):
            assert a['sourceTime']==b['sourceTime'] and a['sourceFrame']==b['sourceFrame']
            if a['sourceTime'] not in changed:assert a==b;continue
            for key in ['image','world','confidence']:
                assert sorted(map(str,a[key]))==sorted(map(str,b[key]))
                for j in range(33):
                    if j not in lower:assert a[key][j]==b[key][j]
        n=len(data['times']);assert n==len(raw['frames'])
        assert data['times']==[r['sourceTime'] for r in raw['frames']]
        assert data['times'][-1]>=data['sourceDuration']-2/raw['fps']
        assert len(data['observed'])==len(data['originalObserved'])==len(data['methods']['motionbert'])==len(data['originalMotionbert'])==n
        for seq in [data['methods']['motionbert'],data['originalMotionbert']]:
            for frame in seq:
                if frame is not None:assert np.shape(frame)==(17,3) and np.isfinite(frame).all()
        assert all(data['methods']['motionbert'][i] is None for i in data['missing'])
        assert hashlib.sha256((OUT/clip['video']).read_bytes()).hexdigest()==clip['videoSha256']==raw['sourceVideoSha256']
        assert data['availableFrames']==sum(f is not None for f in data['methods']['motionbert'])>0
        # Add cache provenance only; no rerun or coordinate change.
        data.update(trackerVersion=raw['trackerVersion'],modelProvenance='output/ballpark/motion-method-demo-v1/model-provenance.json',modelSha256=model_hash)
        write(target,data)
        rows.append(dict(playerId=pid,playerName=player['playerName'],clipId=clip['id'],date=clip['date'],
          sourceFrames=n,availableFrames=data['availableFrames'],segments=[{'start':s['start'],'end':s['end']} for s in data['segments']],
          changedLabelFrames=len(changed),sourceSha256=clip['videoSha256'],artifactSha256=hashlib.sha256(target.read_bytes()).hexdigest(),
          userAcceptance='pending',url=f'http://127.0.0.1:3000/pitcher-personal?year=2026&pitcher_id={pid}&tab=in-game'))
    assert len(rows)==8
    # Route callables only: no running server, fixture login or UI inspection.
    sys.path.insert(0,str(ROOT/'backend'))
    from app.api.routes.motion_review import index,data,video
    from fastapi import HTTPException
    assert len(index()['players'])==8
    for row in rows:
        assert Path(data(row['playerId']).path).is_file()
        assert Path(video(row['playerId']).path).is_file()
    try:video(1)
    except HTTPException as error:assert error.status_code==404
    else:raise AssertionError('Unknown player must not select a file')
    evidence=dict(version='team_pitch_motion_review_v1',date='2026-11-07',status='pending_user',scope=manifest['scope'],
      rosterRetrievedAt=manifest['rosterRetrievedAt'],modelSha256=model_hash,players=rows,trainingPerformed=False,
      originalTwoPlayerHoldoutTouched=False,yesavageRef5Preserved=True,sourceChecks='pass: roster/identity keys/full timeline/label permutations/finite arrays/hashes/route files',
      visualAcceptance=False,referenceNotSelectedGame=True,calibratedWorldRoot=False,rigRetargetEnabled=False)
    write(ROOT/'data/sample/petehub_team_pitch_motion_az_v1.json',evidence)
    print(json.dumps({'players':len(rows),'sourceFrames':sum(r['sourceFrames'] for r in rows),'availableFrames':sum(r['availableFrames'] for r in rows),'sourceChecks':'pass','visualAcceptance':False}))

if __name__=='__main__':main()
