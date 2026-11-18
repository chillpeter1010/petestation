"""Two-sided Perdomo source-landmark/B pilot; no bat-path or mesh reconstruction."""
from pathlib import Path
import hashlib
import json
import re
import time
from urllib.parse import urlparse
import duckdb
from build_team_pitch_motion import write,ROOT,MODEL

OUT=ROOT/'output/ballpark/perdomo-swing-v1'
TRACKER='batter-source-window-v2'
# Declared original-video analysis windows: isolate the standing batter, exclude
# the opening close-up/camera cut, retain preparation through follow-through.
PILOT={
 'L':dict(clip='perdomo-l-01',window=[1.05,4.1],roi=[.33,.15,.51,.72],seed=[.42,.43]),
 'R':dict(clip='perdomo-r-01',window=[.05,4.1],roi=[.53,.15,.69,.72],seed=[.60,.43]),
}

def prepare():
    path=OUT/'manifest.json'
    if path.exists():return json.loads(path.read_text(encoding='utf-8'))
    db=duckdb.connect(str(ROOT/'data/MLB2026/mlb_2026.duckdb'),read_only=True);groups=[]
    for side in ['L','R']:
        rows=db.execute('''select distinct p.game_pk,cast(p.game_date as date),p.at_bat_number,p.pitch_number,
          v.play_id,v.video_url,p.stand,p.pitcher,p.description,p.events,p.pitch_type,p.bat_speed,p.swing_length,p.p_throws
          from pitches p join pitch_play_lookup v using(game_pk,at_bat_number,pitch_number)
          where p.batter=672695 and p.stand=? and p.description='hit_into_play' and v.video_url is not null
          order by cast(p.game_date as date) desc,p.at_bat_number,p.pitch_number limit 3''',[side]).fetchall()
        clips=[]
        for rank,r in enumerate(rows,1):
            cid=f'perdomo-{side.lower()}-{rank:02}'
            clips.append(dict(id=cid,playerId=672695,playerName='Geraldo Perdomo',year=2026,gamePk=r[0],date=str(r[1]),
              atBat=r[2],pitchNumber=r[3],playId=r[4],sourcePage=r[5],stand=r[6],pitcherId=r[7],description=r[8],event=r[9],
              pitchType=r[10],sourceBatSpeedMph=r[11],sourceSwingLengthFt=r[12],pitchHand=r[13],video=f'videos/{cid}.mp4',status='reserved'))
        groups.append(dict(stand=side,selectedClipId=None,clips=clips))
    db.close();result=dict(version='perdomo_swing_review_v1',date='2026-11-07',playerId=672695,playerName='Geraldo Perdomo',sides=groups,
      scope='One reference per actual batting side; pretrained human pose only, no training/mesh/bat endpoint recovery.',userAcceptance='pending')
    write(path,result);return result

def detect(clip,build):
    import numpy as np
    cv2,mp=build.cv2,build.mp
    path=OUT/'raw-v2'/f"{clip['id']}.json"
    if path.exists():return json.loads(path.read_text(encoding='utf-8'))
    cap=cv2.VideoCapture(str(OUT/clip['video']));assert cap.isOpened()
    w,h=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT));fps=float(cap.get(cv2.CAP_PROP_FPS));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    plan=PILOT[clip['stand']];start,end=plan['window']
    step=max(1,int(round(fps/60)));roi=[int(v*(w if i%2==0 else h)) for i,v in enumerate(plan['roi'])];x0,y0,x1,y1=roi
    previous=None;anchor=None;torso_size=None;last=None;rows=[];started=time.monotonic()
    options=mp.tasks.vision.PoseLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(build.OLD/'pose_landmarker_full.task')),
      running_mode=mp.tasks.vision.RunningMode.VIDEO,num_poses=3,min_pose_detection_confidence=.35,min_pose_presence_confidence=.35,min_tracking_confidence=.5)
    with mp.tasks.vision.PoseLandmarker.create_from_options(options) as landmarker:
      for index in range(0,count,step):
        ok,bgr=cap.read()
        if not ok:break
        for _ in range(step-1):cap.grab()
        row=dict(sourceFrame=index,sourceTime=index/fps,image=None,world=None,confidence=None)
        # Bound source analysis, but retain the complete source timeline below.
        if not start<=index/fps<=end:row['missingReason']='outside-declared-source-window';rows.append(row);continue
        image=mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(bgr[y0:y1,x0:x1],cv2.COLOR_BGR2RGB))
        result=landmarker.detect_for_video(image,round(index/fps*1000));choices=[];diagnostics=[]
        for i,points in enumerate(result.pose_landmarks):
          p=np.array([[pt.x*(x1-x0)+x0,pt.y*(y1-y0)+y0] for pt in points]);conf=[min(pt.visibility,pt.presence) for pt in points]
          hip=p[[23,24]].mean(0)/[w,h];shoulder=p[[11,12]].mean(0)/[w,h];ankle=max(p[27,1],p[28,1])/h;torso=float(np.linalg.norm(hip-shoulder))
          hist=build.shirt_histogram(bgr,p)
          reason='candidate';cost=0;distance=0
          if min(conf[23],conf[24],conf[11],conf[12])<.5:reason='low-torso-confidence'
          elif not(x0/w<hip[0]<x1/w and .30<hip[1]<.65 and ankle-hip[1]>.075):reason='not-standing-home-plate-candidate'
          elif hist is None:reason='no-torso-appearance'
          elif previous is None:
            cost=float(np.linalg.norm(hip-plan['seed']))
          else:
            movement=float(np.linalg.norm(hip-previous));distance=float(cv2.compareHist(anchor,hist,cv2.HISTCMP_BHATTACHARYYA))
            if movement>min(.11,.02+(index/fps-last)*.12) or not .45<torso/torso_size<2 or distance>.85:reason='identity-motion-scale-gate'
            cost=movement*5+distance*.08+abs(np.log(torso/torso_size))*.1
          diagnostics.append(dict(candidate=i,hip=hip.tolist(),reason=reason,appearanceDistance=distance))
          if reason=='candidate':choices.append((cost,i,p,conf,hist,hip,torso))
        choices.sort(key=lambda c:c[0]);row['candidateDiagnostics']=diagnostics
        if choices and not(len(choices)>1 and previous is not None and choices[1][0]-choices[0][0]<.025):
          _,i,p,conf,hist,hip,torso=choices[0]
          if previous is None:anchor=hist.copy();torso_size=torso
          previous=hip;last=index/fps;row.update(image=p.tolist(),confidence=conf,world=[[v.x,v.y,v.z] for v in result.pose_world_landmarks[i]])
        else:row['missingReason']='no-unambiguous-standing-batter-candidate'
        rows.append(row)
        if len(rows)%40==0:print(clip['id'],'source frames',len(rows),'observed',sum(r['image'] is not None for r in rows),flush=True)
        if time.monotonic()-started>55:cap.release();raise TimeoutError('55s capture limit; retry only this clip')
    cap.release()
    raw=dict(id=clip['id'],width=w,height=h,fps=fps,sampleStep=step,roi=roi,frames=rows,sourceDuration=count/fps,
      sourceVideoSha256=hashlib.sha256((OUT/clip['video']).read_bytes()).hexdigest(),trackerVersion=TRACKER,
      processingWindow=[start,end],identityAccepted=False)
    write(path,raw);return raw

def score(raw):
    start,end=raw['processingWindow'];rows=[r for r in raw['frames'] if start<=r['sourceTime']<=end]
    valid=[i for i,r in enumerate(rows) if r['image'] is not None]
    if not valid:return dict(score=0,bodyCoverage=0,bothWristsCoverage=0,observedWindow=None)
    body=sum(r['image'] is not None for r in rows)/len(rows)
    wrists=sum(r['image'] is not None and min(r['confidence'][j] for j in [13,14,15,16])>=.65 for r in rows)/len(rows)
    return dict(score=round(50*body+50*wrists,2),bodyCoverage=body,bothWristsCoverage=wrists,
      analysisWindow=[start,end],denominatorFrames=len(rows),
      observedWindow=[rows[valid[0]]['sourceTime'],rows[valid[-1]]['sourceTime']],
      armVisibility={side:sum(r['image'] is not None and min(r['confidence'][j] for j in joints)>=.65 for r in rows)/len(rows)
        for side,joints in [('left',[13,15]),('right',[14,16])]},
      limitation='Torso/wrist visibility only; not swing completeness, bat tracking or correct 3D motion.')

def main():
    import build_pitch_motion_demo as build
    from prepare_pitch_motion_demo import fetch,SESSION
    build.torch.set_num_threads(4)
    model=build.DSTformer(dim_in=3,dim_out=3,dim_feat=256,dim_rep=512,depth=5,num_heads=8,mlp_ratio=4,num_joints=17,maxlen=243,att_fuse=True)
    checkpoint=build.torch.load(MODEL/'weights/motionbert-lite.bin',map_location='cpu',weights_only=True)
    model.load_state_dict({k.removeprefix('module.'):v for k,v in checkpoint['model_pos'].items()},strict=True);model.eval()
    manifest=prepare()
    for side in manifest['sides']:
      target=OUT/f"{side['stand']}-review.json"
      if target.exists() and json.loads(target.read_text(encoding='utf-8')).get('trackerVersion')==TRACKER:print('cached',side['stand'],flush=True);continue
      if target.exists():
        rejected=json.loads(target.read_text(encoding='utf-8'))
        rejected['rejection']='Preparation-only track before camera cut; first-to-last-observation denominator inflated coverage. Not a usable full swing.'
        write(OUT/'rejected'/f"{side['stand']}-preparation-only-v1.json",rejected)
      for clip in side['clips']:
        if clip['id']!=PILOT[side['stand']]['clip']:continue
        try:
          path=OUT/clip['video']
          if not path.exists():
            page=SESSION.get(clip['sourcePage'],timeout=(8,15));page.raise_for_status()
            urls=[u for u in re.findall(r'https://[^\s"<>]+\.mp4',page.text) if (urlparse(u).hostname or '').endswith('.mlb.com')]
            if not urls:raise RuntimeError('No official mp4')
            info=fetch(urls[0],path);clip.update(directUrl=urls[0],videoSha256=info['sha256'])
          clip['videoSha256']=hashlib.sha256(path.read_bytes()).hexdigest()
          raw=detect(clip,build);q=score(raw);clip['quality']=q
          comparison=build.infer(model,raw)
          comparison['trackerVersion']=TRACKER
          if comparison['availableFrames']<90 or q['bodyCoverage']<.7:raise RuntimeError('Insufficient declared-window body evidence; do not publish as a swing')
          clip.pop('error',None);clip['status']='candidate';side['selectedClipId']=clip['id']
          write(target,dict(clip=clip,**comparison,quality=q,mode='batter_reference_pose_estimate',batEndpointsAvailable=False,contactTime=None,
            trainingPerformed=False,userAcceptance='pending',sideMirrored=False,
            processingWindow=raw['processingWindow'],sourceVideoSha256=raw['sourceVideoSha256'],
            modelProvenance='output/ballpark/motion-method-demo-v1/model-provenance.json'))
          print('candidate',clip['id'],comparison['availableFrames'],q,flush=True);break
        except Exception as e:clip.update(status='failed',error=str(e));print('failed',clip['id'],str(e),flush=True)
        finally:write(OUT/'manifest.json',manifest)

if __name__=='__main__':main()
