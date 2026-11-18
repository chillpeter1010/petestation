"""Offline method screening; no app rig, render, browser or player-specific training."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/ballpark/motion-method-demo-v1'
OLD=ROOT/'output/ballpark/f2-motion-reference-v1'
sys.path[:0]=[str(OUT/'env'),str(OUT/'vendor'),str(OLD/'pose-tools')]
import cv2
import mediapipe as mp
import numpy as np
import torch
from lib.model.DSTformer import DSTformer
from pitch_motion_tracking import AppearanceLock,MoundTrack,shirt_histogram,TRACKER_VERSION

PARENTS=[-1,0,1,2,0,4,5,0,7,8,9,8,11,12,8,14,15]
NAMES=['pelvis','right hip','right knee','right ankle','left hip','left knee','left ankle',
       'spine proxy','shoulder centre','nose','head proxy','left shoulder','left elbow','left wrist',
       'right shoulder','right elbow','right wrist']
METHOD_VERSION='motionbert-identity-full-timeline-v3'


def mapping(x):
    """MediaPipe anatomical sides -> H36M; pelvis/spine/head are explicit proxies."""
    y=np.zeros((17,x.shape[-1]),dtype=float)
    for a,b in [(1,24),(2,26),(3,28),(4,23),(5,25),(6,27),(9,0),
                (11,11),(12,13),(13,15),(14,12),(15,14),(16,16)]:y[a]=x[b]
    y[0]=(x[23]+x[24])/2;y[8]=(x[11]+x[12])/2
    y[7]=(y[0]+y[8])/2;y[10]=(x[7]+x[8])/2
    return y


def detect(clip):
    path=OUT/clip.get('poseCache','poses-identity-v3')/f"{clip['id']}.json"
    if path.exists():return json.loads(path.read_text(encoding='utf-8'))
    cap=cv2.VideoCapture(str(OUT/clip['video']))
    if not cap.isOpened():raise RuntimeError('Cannot decode '+clip['id'])
    w,h=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps=float(cap.get(cv2.CAP_PROP_FPS));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start,end=clip.get('processingWindow',[0,None]);end=count/fps if end is None else min(end,count/fps);step=max(1,int(round(fps/60)))
    # A fixed, declared centre-field crop; identity remains a user review item.
    rx0,ry0,rx1,ry1=clip.get('roiFractions',[.12,.15,.72,1])
    x0,y0,x1,y1=int(w*rx0),int(h*ry0),int(w*rx1),int(h*ry1)
    tracker=(MoundTrack if clip.get('trackerMode')=='mound-crop-temporal-v1' else AppearanceLock)(w,h);rows=[];valid=0;started=time.monotonic()
    options=mp.tasks.vision.PoseLandmarkerOptions(
      base_options=mp.tasks.BaseOptions(model_asset_path=str(OLD/'pose_landmarker_full.task')),
      running_mode=mp.tasks.vision.RunningMode.VIDEO,num_poses=3,
      min_pose_detection_confidence=.35,min_pose_presence_confidence=.35,min_tracking_confidence=.5)
    try:
      with mp.tasks.vision.PoseLandmarker.create_from_options(options) as landmarker:
        cap.set(cv2.CAP_PROP_POS_FRAMES,int(np.ceil(start*fps/step))*step)
        for index in range(0,count,step):
            row=dict(sourceFrame=index,sourceTime=index/fps,image=None,world=None,confidence=None)
            if index/fps<start or index/fps>end:
                row['missingReason']='outside-processing-window';rows.append(row);continue
            ok,bgr=cap.read()
            if not ok:break
            for _ in range(step-1):cap.grab()
            image=mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(bgr[y0:y1,x0:x1],cv2.COLOR_BGR2RGB))
            result=landmarker.detect_for_video(image,round(index/fps*1000))
            choices=[]
            for i,points in enumerate(result.pose_landmarks):
                coords=np.array([[p.x*(x1-x0)+x0,p.y*(y1-y0)+y0] for p in points])
                confidence=[min(p.visibility,p.presence) for p in points]
                choices.append(dict(image=coords,confidence=confidence,histogram=shirt_histogram(bgr,coords)))
            chosen=tracker.choose(choices,index/fps)
            if chosen:
                i,diagnostic=chosen
                row['image']=choices[i]['image'].tolist();row['tracking']=diagnostic
                row['world']=[[p.x,p.y,p.z] for p in result.pose_world_landmarks[i]]
                row['confidence']=[min(p.visibility,p.presence) for p in result.pose_landmarks[i]];valid+=1
            else:row['missingReason']='no-appearance-locked-candidate-or-ambiguous'
            rows.append(row)
            if len(rows)%40==0:print(clip['id'],'source frames',len(rows),'detected',valid,flush=True)
            if time.monotonic()-started>55:raise TimeoutError('One clip exceeded 55s; stop this clip rather than hang')
    finally:cap.release()
    value=dict(id=clip['id'],width=w,height=h,fps=fps,sampleStep=step,roi=[x0,y0,x1,y1],
      sourceVideoSha256=hashlib.sha256((OUT/clip['video']).read_bytes()).hexdigest(),frames=rows,
      detected=valid,identityAccepted=False,rawUnchanged=True,trackerVersion=clip.get('trackerMode',TRACKER_VERSION),
      sourceDuration=count/fps,processingWindow=[start,end])
    path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(value,separators=(',',':')),encoding='utf-8')
    return value


def fill(raw):
    rows=raw['frames'];valid=[i for i,r in enumerate(rows) if r['image'] is not None]
    if len(valid)<len(rows)*.6:raise RuntimeError('Insufficient tracked frames; source needs manual crop/identity review')
    image=np.full((len(rows),17,3),np.nan);world=np.full((len(rows),17,3),np.nan)
    for i in valid:
        r=rows[i];image[i]=mapping(np.column_stack([r['image'],r['confidence']]))
        world[i]=mapping(np.array(r['world']))
    # Fill only derived model input, with explicit missing-frame flags. Raw stays missing.
    for a in [image,world]:
        for j in range(17):
            for k in range(3):a[:,j,k]=np.interp(np.arange(len(rows)),valid,a[valid,j,k])
    for i,r in enumerate(rows):
        if r['image'] is None:image[i,:,2]=0
    return image,world,[i for i,r in enumerate(rows) if r['image'] is None]


def infer(model,raw):
    # Retain the source timeline; infer each eligible identity-locked segment separately.
    groups=[];group=[];previous=None
    for i,row in enumerate(raw['frames']):
        if row['image'] is None:continue
        torso=np.array(row['image'])[[11,12,23,24]]
        cut=previous is not None and (i-previous[0]>max(3,raw['fps']*.12) or
          np.median(np.linalg.norm((torso-previous[1])/[raw['width'],raw['height']],axis=1))>.1)
        if cut and group:groups.append(group);group=[]
        group.append(i);previous=(i,torso)
    if group:groups.append(group)
    n=len(raw['frames']);result=dict(methodVersion=METHOD_VERSION,times=[r['sourceTime'] for r in raw['frames']],
      observed=[None]*n,methods={k:[None]*n for k in ['mediapipe','motionbert']},metrics={},filled=[],
      width=raw['width'],height=raw['height'],sourceDuration=raw['sourceDuration'],segments=[],inferenceSeconds=0,
      trackerVersion=TRACKER_VERSION,missingReasons=[r.get('missingReason') for r in raw['frames']])
    for group in groups:
        a,b=group[0],group[-1]+1
        if raw['frames'][b-1]['sourceTime']-raw['frames'][a]['sourceTime']<.5:continue
        if len(group)/(b-a)<.6:continue
        part=infer_segment(model,{**raw,'frames':raw['frames'][a:b]})
        result['segments'].append(dict(first=a,last=b-1,start=part['times'][0],end=part['times'][-1],metrics=part['metrics']))
        result['observed'][a:b]=part['observed'];result['filled'] += [a+i for i in part['filled']]
        result['inferenceSeconds']+=part['inferenceSeconds']
        for k in result['methods']:result['methods'][k][a:b]=part['methods'][k]
    result['availableFrames']=sum(x is not None for x in result['methods']['motionbert'])
    result['missing']=[i for i,x in enumerate(result['methods']['motionbert']) if x is None]
    result['metrics']={'segments':result['segments']}
    if not result['availableFrames']:result['error']='No reliable identity-locked segment; source video remains playable in full.'
    return result


def infer_segment(model,raw):
    observed,baseline,filled=fill(raw)
    confident=observed[observed[:,:,2]>.3,:2]
    lo,hi=confident.min(axis=0),confident.max(axis=0)
    scale=float(max(hi-lo));centre=(lo+hi)/2
    inp=observed.copy();inp[:,:,:2]=(inp[:,:,:2]-centre)/scale*2
    # Same clip-wide crop/scale convention as upstream crop_scale([1,1]).
    inp[:,:,:2]=np.clip(inp[:,:,:2],-1,1)
    n=len(inp);parts=[];started=time.monotonic()
    with torch.inference_mode():
        for a in range(0,n,243):
            batch=torch.from_numpy(inp[a:a+243].astype('float32'))[None]
            pred=model(batch)
            # Upstream inference uses paired flip augmentation, then restores anatomy.
            left=[4,5,6,11,12,13];right=[1,2,3,14,15,16]
            flipped=batch.clone();flipped[:,:,:,0]*=-1
            flipped[:,:,left+right]=flipped[:,:,right+left]
            back=model(flipped);back[:,:,:,0]*=-1
            back[:,:,left+right]=back[:,:,right+left]
            parts.append(((pred+back)/2).cpu().numpy()[0])
    predicted=np.concatenate(parts);predicted[0,0,2]=0 # upstream global-lite convention
    elapsed=time.monotonic()-started
    # Preserve each predictor's local pose; fit ONLY image-plane scale/translation.
    # This supplies observed image-plane travel, not calibrated 3D world/root motion.
    methods={};metrics={}
    for name,points in [('mediapipe',baseline),('motionbert',predicted)]:
        centred=points-points[:,0:1]
        target=observed[:,:,:2]-observed[:,0:1,:2]
        weights=np.clip(observed[:,:,2],0,1)**2
        denominator=np.sum(weights[:,:,None]*centred[:,:,:2]**2)
        fitted=float(np.sum(weights[:,:,None]*centred[:,:,:2]*target)/max(denominator,1e-9))
        if fitted<=0:raise RuntimeError('Invalid camera-plane scale')
        pixel=centred*fitted;pixel[:,:,:2]+=observed[:,0:1,:2]
        residual=np.linalg.norm(pixel[:,:,:2]-observed[:,:,:2],axis=-1)
        lengths=np.stack([np.linalg.norm(centred[:,j]-centred[:,p],axis=-1) for j,p in enumerate(PARENTS) if p>=0],axis=1)
        metrics[name]=dict(projectionRmsePx=float(np.sqrt(np.sum(weights*residual**2)/max(weights.sum(),1))),
          medianBoneLengthCV=float(np.median(lengths.std(axis=0)/np.maximum(lengths.mean(axis=0),1e-9))))
        # Common relative units, no real-world metre claim, no forced feet or joint rotations.
        pixel[:,:,:2]-=observed[0,0,:2]
        pixel/=scale/2
        methods[name]=np.round(pixel,5).tolist()
    return dict(methodVersion=METHOD_VERSION,times=[r['sourceTime'] for r in raw['frames']],observed=np.round(observed,3).tolist(),
      methods=methods,metrics=metrics,filled=filled,width=raw['width'],height=raw['height'],
      inferenceSeconds=elapsed,prediction=np.round(predicted,5).tolist(),
      limitation='Camera-relative estimated shape/depth plus fitted image-plane translation; NOT world-grounded root motion, calibrated metres, exact pitching mechanics or rig retarget.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--clip');args=parser.parse_args()
    torch.set_num_threads(4)
    model=DSTformer(dim_in=3,dim_out=3,dim_feat=256,dim_rep=512,depth=5,num_heads=8,
      mlp_ratio=4,num_joints=17,maxlen=243,att_fuse=True)
    checkpoint=torch.load(OUT/'weights/motionbert-lite.bin',map_location='cpu',weights_only=True)
    model.load_state_dict({k.removeprefix('module.'):v for k,v in checkpoint['model_pos'].items()},strict=True);model.eval()
    manifest=json.loads((OUT/'dataset-manifest.json').read_text(encoding='utf-8'))
    results=[];status_path=OUT/'processing-status.json'
    statuses=json.loads(status_path.read_text(encoding='utf-8')) if status_path.exists() else {}
    for p in manifest['players']:
      for c in p['clips']:
        if c['split']!='reference' or c['rank']>5 or c['status']!='downloaded':continue
        if args.clip and c['id']!=args.clip:continue
        target=OUT/f"{c['id']}-comparison.json"
        if target.exists():
            cached=json.loads(target.read_text(encoding='utf-8'))
            if cached.get('methodVersion')==METHOD_VERSION:
                if not cached.get('metrics'):
                    cached['metrics']={'segments':cached['segments']}
                    target.write_text(json.dumps(cached,separators=(',',':')),encoding='utf-8')
                results.append(cached);statuses[c['id']]=dict(status='failed' if cached.get('error') else 'candidate',methodVersion=METHOD_VERSION);continue
        try:
            raw=detect(c);comparison=infer(model,raw);result=dict(clip=c,**comparison)
            target.write_text(json.dumps(result,separators=(',',':')),encoding='utf-8');results.append(result)
            statuses[c['id']]=dict(status='failed' if result.get('error') else 'candidate',methodVersion=METHOD_VERSION)
            print('complete',c['id'],len(comparison['times']),comparison['metrics'],flush=True)
        except Exception as e:
            statuses[c['id']]=dict(status='failed',methodVersion=METHOD_VERSION,error=str(e))
            print('FAILED',c['id'],type(e).__name__,str(e),flush=True)
        status_path.write_text(json.dumps(statuses,indent=2),encoding='utf-8')
    status_path.write_text(json.dumps(statuses,indent=2),encoding='utf-8')
    print('batch completed',len(results),'clips; pending user review',flush=True)


if __name__=='__main__':main()
