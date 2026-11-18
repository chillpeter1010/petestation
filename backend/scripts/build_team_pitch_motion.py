"""Resumable one-reference-per-starter B review. No training or app rendering."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import re
from datetime import datetime, timezone
import duckdb
import requests

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'output/ballpark/team-motion-az-v1'
MODEL=ROOT/'output/ballpark/motion-method-demo-v1'

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.part')
    temp.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8')
    temp.replace(path)

def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'manifest.json'
    if path.exists():return json.loads(path.read_text(encoding='utf-8'))
    url='https://statsapi.mlb.com/api/v1/teams/109/roster?rosterType=active&season=2026&hydrate=person'
    response=requests.get(url,timeout=(8,15));response.raise_for_status()
    roster=response.json();stamp=datetime.now(timezone.utc).isoformat()
    write(OUT/'roster-source.json',dict(sourceUrl=url,retrievedAt=stamp,payload=roster))
    active={r['person']['id']:r['person']['fullName'] for r in roster['roster'] if r['position']['type']=='Pitcher'}
    db=duckdb.connect(str(ROOT/'data/MLB2026/mlb_2026.duckdb'),read_only=True)
    starts=db.execute("""select pitcher,count(distinct game_pk) from pitches where inning=1
      and ((inning_topbot='Top' and home_team='AZ') or (inning_topbot='Bot' and away_team='AZ'))
      group by pitcher having count(distinct game_pk)>=3 order by count(distinct game_pk) desc,pitcher""").fetchall()
    players=[]
    for pid,gs in starts:
        if pid not in active:continue
        rows=db.execute('''select distinct p.game_pk,cast(p.game_date as date),p.at_bat_number,p.pitch_number,
          v.play_id,v.video_url,p.pitch_type,p.p_throws,p.release_extension,p.arm_angle,
          p.release_pos_x,p.release_pos_y,p.release_pos_z
          from pitches p join pitch_play_lookup v using(game_pk,at_bat_number,pitch_number)
          where p.pitcher=? and p.inning=1 and v.video_url is not null and v.play_id is not null
          and ((p.inning_topbot='Top' and p.home_team='AZ') or (p.inning_topbot='Bot' and p.away_team='AZ'))
          order by cast(p.game_date as date) desc,p.at_bat_number,p.pitch_number''',[pid]).fetchall()
        clips=[]
        # Freeze alternate sources too, so a failed download does not change the sample silently.
        for rank,r in enumerate(rows[:3],1):
            clips.append(dict(id=f'az-{pid}-reference-{rank:02}',playerId=pid,playerName=active[pid],name=str(pid),
              year=2026,gamePk=r[0],date=str(r[1]),atBat=r[2],pitchNumber=r[3],playId=r[4],sourcePage=r[5],
              pitchType=r[6],pitchHand=r[7],sourceExtensionFt=r[8],sourceArmAngleDeg=r[9],sourceReleaseFt=list(r[10:13]),
              video=f'videos/az-{pid}-reference-{rank:02}.mp4',roiFractions=[.15,.28,.57,1],processingWindow=[0,None],status='reserved'))
        players.append(dict(playerId=pid,playerName=active[pid],starts2026=gs,clips=clips,selectedClipId=None,status='pending'))
    db.close()
    manifest=dict(version='team_pitch_motion_review_v1',team='AZ',teamId=109,year=2026,rosterRetrievedAt=stamp,
      rosterSourceUrl=url,scope='Official current active pitchers with >=3 AZ first-inning appearances in local 2026 data; not a declared future rotation.',
      referenceLimitPerPlayer=1,trainingPerformed=False,visualAcceptance='pending_user',players=players)
    write(path,manifest);return manifest

def associate_sides(raw):
    """Apply accepted label-only DP separately to continuous observed runs.

    Original anatomical endpoint labels are an assumption, not ground truth. Never
    reuse Thompson timestamps, bridge missing frames, or move/plant an ankle.
    """
    from review_pitch_foot_occlusion import resolve_lower_leg_sides
    derived=copy.deepcopy(raw);runs=[];run=[]
    for i,row in enumerate(raw['frames']):
        if row['image'] is None or min(row['confidence'][j] for j in [25,26,27,28])<.65:
            if run:runs.append(run);run=[]
        else:run.append(i)
    if run:runs.append(run)
    changed=[];intervals=[]
    for run in runs:
        if len(run)<3:continue
        start,end=[raw['frames'][i]['sourceTime'] for i in [run[0],run[-1]]]
        part,times=resolve_lower_leg_sides({**raw,'frames':[raw['frames'][i] for i in run]},start,end)
        for i,row in zip(run,part['frames']):derived['frames'][i]=row
        changed+=times;intervals.append([start,end])
    return derived,dict(version='continuous-run-label-dp-v1',changedSourceSeconds=changed,intervals=intervals,
      endpointAssumption='Original anatomical labels at each continuous observed run endpoint; requires user review.',
      coordinatesMoved=False,footContactForced=False)

def process(player_id,retry_short=False):
    import build_pitch_motion_demo as build
    from prepare_pitch_motion_demo import fetch,SESSION
    build.torch.set_num_threads(4)
    build.OUT=OUT
    model=build.DSTformer(dim_in=3,dim_out=3,dim_feat=256,dim_rep=512,depth=5,num_heads=8,
      mlp_ratio=4,num_joints=17,maxlen=243,att_fuse=True)
    checkpoint=build.torch.load(MODEL/'weights/motionbert-lite.bin',map_location='cpu',weights_only=True)
    model.load_state_dict({k.removeprefix('module.'):v for k,v in checkpoint['model_pos'].items()},strict=True);model.eval()
    manifest=prepare()
    for player in manifest['players']:
        if player_id and player['playerId']!=player_id:continue
        target=OUT/f"{player['playerId']}-review.json"
        if target.exists():
            cached=json.loads(target.read_text(encoding='utf-8'))
            if not retry_short or max((s['end']-s['start'] for s in cached['segments']),default=0)>=2:
                print('cached',player['playerName'],flush=True);continue
            write(OUT/'revisions'/f"{player['playerId']}-appearance-v1.json",cached)
        for clip in player['clips']:
            try:
                if retry_short:clip.update(trackerMode='mound-crop-temporal-v1',poseCache='poses-mound-v1')
                print('processing',player['playerName'],clip['id'],flush=True)
                video=OUT/clip['video']
                if not video.exists():
                    page=SESSION.get(clip['sourcePage'],timeout=(8,15));page.raise_for_status()
                    urls=re.findall(r'https://[^\s"<>]+\.mp4',page.text)
                    urls=[u for u in urls if (requests.utils.urlparse(u).hostname or '').endswith('.mlb.com')]
                    if not urls:raise RuntimeError('No official MLB mp4 in source page')
                    clip['directUrl']=urls[0];info=fetch(urls[0],video);clip['videoSha256']=info['sha256']
                clip['videoSha256']=hashlib.sha256(video.read_bytes()).hexdigest()
                raw=build.detect(clip);corrected,association=associate_sides(raw)
                before=build.infer(model,raw)
                after=build.infer(model,corrected) if association['changedSourceSeconds'] else before
                if not after['availableFrames']:raise RuntimeError('No reliable continuous pitcher segment; identity/crop review required')
                data=dict(clip=clip,**after,originalMotionbert=before['methods']['motionbert'],
                  originalObserved=before['observed'],sideAssociation=association,
                  mode='reference_video_pose_estimate',visualAcceptance='pending_user',
                  limitation='Estimated camera-relative depth and image-plane travel, not calibrated world root, measured contact or game-pitch rig motion.')
                data['trackerVersion']=raw['trackerVersion']
                data['modelProvenance']='output/ballpark/motion-method-demo-v1/model-provenance.json'
                data['modelSha256']=hashlib.sha256((MODEL/'weights/motionbert-lite.bin').read_bytes()).hexdigest()
                clip['status']='candidate';player.update(status='candidate',selectedClipId=clip['id'])
                write(target,data)
                print('candidate',player['playerName'],after['availableFrames'],'frames; side labels',len(association['changedSourceSeconds']),flush=True)
                break
            except Exception as error:
                clip.update(status='failed',error=str(error));player['status']='unavailable'
                print('unavailable',clip['id'],str(error),flush=True)
            finally:write(OUT/'manifest.json',manifest)
        write(OUT/'manifest.json',manifest)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','process']);parser.add_argument('--player',type=int);parser.add_argument('--retry-short',action='store_true')
    args=parser.parse_args()
    if args.stage=='prepare':
        m=prepare();print([(p['playerName'],p['starts2026']) for p in m['players']])
    else:process(args.player,args.retry_short)
