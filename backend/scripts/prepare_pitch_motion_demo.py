"""Bounded, cached source/model preparation for an offline two-pitcher experiment."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import time
import requests
import duckdb
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/ballpark/motion-method-demo-v1'
OUT.mkdir(parents=True, exist_ok=True)
SESSION = requests.Session()
SESSION.mount('https://', HTTPAdapter(max_retries=Retry(total=1,connect=1,read=0,backoff_factor=.3)))


def fetch(url, path):
    path = Path(path)
    if path.exists():
        return {'path': str(path.relative_to(ROOT)), 'url': url,
                'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with SESSION.get(url, timeout=(10, 15), stream=True) as r:
        r.raise_for_status()
        with path.with_suffix(path.suffix + '.part').open('wb') as f:
            for chunk in r.iter_content(1024 * 1024):
                f.write(chunk)
                if time.monotonic() - started > 55:
                    raise TimeoutError('55 second bounded download; partial retained')
    path.with_suffix(path.suffix + '.part').replace(path)
    print('cached', path.name, path.stat().st_size, flush=True)
    return fetch(url, path)


def prepare_model():
    api = SESSION.get('https://huggingface.co/api/models/walterzhu/MotionBERT', timeout=15)
    api.raise_for_status()
    revision = api.json()['sha']
    base = f'https://huggingface.co/walterzhu/MotionBERT/resolve/{revision}/'
    paths = ['lib/model/DSTformer.py', 'lib/model/drop.py', 'LICENSE',
             'configs/pose3d/MB_ft_h36m_global_lite.yaml']
    rows = [fetch(base + p, OUT / 'vendor' / p) for p in paths]
    p = 'checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin'
    rows.append(fetch(base + p, OUT / 'weights/motionbert-lite.bin'))
    (OUT / 'model-provenance.json').write_text(json.dumps({
        'author': 'MotionBERT authors / walterzhu', 'revision': revision,
        'official_repo': 'https://github.com/Walter0807/MotionBERT',
        'license': 'Apache-2.0; retained upstream LICENSE', 'files': rows,
        'mode': 'pretrained inference only; no individual-model training',
        'WHAM': 'not run: official Linux/CUDA pipeline; SMPL requires registration; local GPU is Intel Arc',
    }, indent=2), encoding='utf-8')


def collect():
    conn = duckdb.connect(str(ROOT / 'data/MLB2025/mlb_2025.duckdb'), read_only=True)
    players = []
    for name, pid in [('yesavage', 702056), ('thompson', 657044)]:
        rows = conn.execute('''
          select distinct p.game_pk, cast(p.game_date as date), p.at_bat_number,
            p.pitch_number, v.play_id, v.video_url, p.pitch_type,
            p.release_extension, p.arm_angle, p.release_pos_x, p.release_pos_y, p.release_pos_z
          from pitches p join pitch_play_lookup v using(game_pk,at_bat_number,pitch_number)
          where p.pitcher=? and v.video_url is not null and v.play_id is not null
        ''', [pid]).fetchall()
        games = sorted({r[0] for r in rows}, key=lambda x: hashlib.sha256(str(x).encode()).hexdigest())
        holdout = games[0]
        rank = lambda r: hashlib.sha256(r[4].encode()).hexdigest()
        test = sorted([r for r in rows if r[0] == holdout], key=rank)[:5]
        # Round-robin games prevents five references coming from one outing.
        pools = [sorted([r for r in rows if r[0] == g], key=rank) for g in games[1:]]
        ref = []
        while len(ref) < 20 and any(pools):
            for pool in pools:
                if pool and len(ref) < 20:
                    ref.append(pool.pop(0))
        assert len(ref) == 20 and len(test) == 5
        clips = []
        for split, group in [('reference', ref), ('holdout', test)]:
            for i, r in enumerate(group):
                clips.append(dict(id=f'{name}-{split}-{i+1:02}', playerId=pid, name=name,
                  gamePk=r[0], date=str(r[1]), atBat=r[2], pitchNumber=r[3], playId=r[4],
                  sourcePage=r[5], pitchType=r[6], sourceExtensionFt=r[7], sourceArmAngleDeg=r[8],
                  sourceReleaseFt=list(r[9:12]), split=split, rank=i+1,
                  video=f'videos/{name}-{split}-{i+1:02}.mp4', status='reserved',
                  groups=[n for n in [5,10,20] if split=='reference' and i<n]))
        players.append(dict(name=name,playerId=pid,holdoutGame=holdout,
          availableClips=len(rows),availableGames=len(games),clips=clips))
    conn.close()
    manifest = dict(version='pitch_motion_methods_v1', mode='offline_method_selection',
      created='2026-11-06', players=players, trainingPerformed=False,
      experiment='Nested 5/10/20 reference groups; 5 held-out pitches/player from a separate game. No frame-level random split.',
      currentBatch='First five reference clips/player for method screening only; holdout not processed or used to tune.',
      visualAcceptance='pending_user', numerical3DGroundTruthAvailable=False)
    target = OUT / 'dataset-manifest.json'
    # Frozen IDs are reused on reruns, even if the season database later changes.
    if target.exists():
        manifest = json.loads(target.read_text(encoding='utf-8'))
    target.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    selected = [c for p in manifest['players'] for c in p['clips'] if c['split']=='reference' and c['rank']<=5]
    import re
    def download(c):
        path = OUT / c['video']
        if path.exists():
            c['status']='downloaded';return
        page = requests.get(c['sourcePage'], timeout=15);page.raise_for_status()
        found = re.findall(r'https://[^\s"<>]+\.mp4', page.text)
        found = [u for u in found if 'mlb.com' in u]
        if not found:raise RuntimeError('No official mp4 URL for '+c['id'])
        info = fetch(found[0],path)
        c.update(status='downloaded',directUrl=found[0],videoSha256=info['sha256'],videoBytes=info['bytes'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(download,c):c for c in selected}
        for f in concurrent.futures.as_completed(futures):
            try:f.result()
            except Exception as e:futures[f].update(status='download_failed',error=str(e))
            target.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('clips',[(p['name'],sum(c['status']=='downloaded' for c in p['clips'])) for p in manifest['players']],flush=True)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['model','collect'])
    args=parser.parse_args()
    prepare_model() if args.stage=='model' else collect()
