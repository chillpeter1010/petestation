"""Offline ML keypoints on two bounded reference clips; never drives the app rig.

Install analysis dependencies into the reference directory's pose-tools, not the
application environment. Source video annotations are NOT application visual QA.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / 'output/ballpark/f2-motion-reference-v1'
sys.path.insert(0, str(REFERENCE / 'pose-tools'))
sys.path.insert(0, str(REFERENCE / 'tools'))

import cv2
import imageio_ffmpeg
import mediapipe as mp
import numpy as np

NAMES = ['nose', 'left_eye_inner', 'left_eye', 'left_eye_outer',
         'right_eye_inner', 'right_eye', 'right_eye_outer', 'left_ear',
         'right_ear', 'mouth_left', 'mouth_right', 'left_shoulder',
         'right_shoulder', 'left_elbow', 'right_elbow', 'left_wrist',
         'right_wrist', 'left_pinky', 'right_pinky', 'left_index',
         'right_index', 'left_thumb', 'right_thumb', 'left_hip', 'right_hip',
         'left_knee', 'right_knee', 'left_ankle', 'right_ankle', 'left_heel',
         'right_heel', 'left_foot_index', 'right_foot_index']
EDGES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
         (11, 23), (12, 24), (23, 24), (23, 25), (25, 27),
         (27, 29), (29, 31), (27, 31), (24, 26), (26, 28),
         (28, 30), (30, 32), (28, 32)]
IMPORTANT = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
MODEL = REFERENCE / 'pose_landmarker_full.task'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_review():
    panels, lookup, summaries = [], {}, []
    sources = {s['name']: s for s in json.loads((REFERENCE/'metadata.json').read_text(encoding='utf-8'))}
    for name in ['yesavage', 'thompson']:
        p = json.loads((REFERENCE/(name+'-pose.json')).read_text(encoding='utf-8'))
        summary = p['summary'];summaries.append({'name':name, **summary})
        lookup[name] = [f['source_time_seconds'] for f in p['frames']]
        rows = ''.join(f'<tr><td>{joint}</td><td>{count} / {summary["frames"]}</td></tr>' for joint,count in summary['joint_frames_above_065'].items())
        panels.append(f'''<section><h2>{name.title()}</h2>
<video id="{name}" controls preload="metadata" src="{name}-pose-review.mp4"></video>
<p id="{name}-time" aria-live="polite">Source video keypoints · pending review</p>
<label>逐幀：<input aria-label="{name} frame" type="range" min="0" max="{summary['frames']-1}" value="0" oninput="seekFrame('{name}',Number(this.value))"></label>
<p><button onclick="step('{name}',-1)">上一幀</button> <button onclick="step('{name}',1)">下一幀</button>
<button onclick="seekTime('{name}',2.15)">抬腿／下沉附近</button> <button onclick="seekTime('{name}',2.85)">放球附近</button></p>
<p>模型返回投手候選 {summary['detected']} / {summary['frames']} 幀；此數量不代表辨識正確。<a href="{html.escape(sources[name]['page'])}">官方來源影片</a> · <a href="{name}-pose.json">逐幀 JSON</a></p>
<details><summary>各關節信心 ≥ 0.65 的幀數</summary><table>{rows}</table></details></section>''')
    document = '''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>Petehub 投手關節辨識原型</title>
<style>body{margin:24px auto;max-width:1200px;padding:0 20px;background:#111b25;color:#edf1f4;font:17px/1.6 system-ui}section{padding:20px;margin:24px 0;border:1px solid #587081;border-radius:10px}video{width:100%;max-height:700px}input{width:80%}button{font:inherit;padding:8px;margin:4px;background:#253847;color:white;border:1px solid #8ea4b3;border-radius:5px}a{color:#8bd6ff}td{padding:3px 18px}summary{cursor:pointer}</style>
<h1>投手關節辨識原型：先驗標點，再接三維骨架</h1>
<p>這是預訓練 MediaPipe 模型的影片推論，尚未訓練球員專屬模型。投手身分、左右肢體和追蹤結果待使用者確認。網站的問題投手動畫已停用，沒有把這批預測接回模型。</p>
<p>青色為解剖左側，橘色為右側；紅叉為低信心。低信心部位不連骨架線，遺失幀保留遺失。影片以 0.5×供檢查，頂端時間仍為來源影片時間。</p>
<ol><li>標點是否一直跟著投手，沒有切到打者、捕手或裁判？</li><li>髖、膝、踝有沒有左右互換、瞬間跳點或落在錯誤位置？</li><li>肩、肘、腕在揮臂與遮擋時是否可信？請指出影片、來源秒數與部位。</li></ol>
<p>JSON 的影像座標對應原影片像素；三維數值是以髖部為中心的單眼估測，尚未做球場相機校準，不能當 Statcast 三維座標或實測動作。</p>'''+''.join(panels)+'''<script>
const times=LOOKUP;
function seekFrame(id,i){const v=document.getElementById(id);v.pause();v.currentTime=Math.max(0,Math.min(times[id].length-1,i))/15;label(id)}
function seekTime(id,t){let i=0;times[id].forEach((s,k)=>{if(Math.abs(s-t)<Math.abs(times[id][i]-t))i=k});seekFrame(id,i)}
function step(id,d){seekFrame(id,Math.round(document.getElementById(id).currentTime*15)+d)}
function label(id){const v=document.getElementById(id),i=Math.min(times[id].length-1,Math.floor(v.currentTime*15+.01));document.getElementById(id+'-time').textContent='來源 '+times[id][i].toFixed(3)+' s · 取樣幀 '+i+' / '+(times[id].length-1)}
Object.keys(times).forEach(id=>document.getElementById(id).addEventListener('timeupdate',()=>label(id)));
</script></html>'''.replace('LOOKUP',json.dumps(lookup))
    (REFERENCE/'pose-review.html').write_text(document,encoding='utf-8')
    print(json.dumps(summaries),flush=True)


def infer_clip(name, start=1.8, end=3.65, sample_fps=30):
    source = REFERENCE / (name + '.mp4')
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise RuntimeError(f'Cannot decode {source}')
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    # Explicit pilot ROI excludes the batter/umpire upper-right. This is a
    # clip-specific crop, not an automatic whole-MLB player identity system.
    x = round((200 if name == 'yesavage' else 360) * width / 1280)
    y, w, h = round(180 * height / 720), round(640 * width / 1280), round(520 * height / 720)
    previous = np.array([.28 if name == 'yesavage' else .18, .52])
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_poses=3, min_pose_detection_confidence=.35,
        min_pose_presence_confidence=.35, min_tracking_confidence=.5)
    output = REFERENCE / (name + '-pose-review.mp4')
    log = (REFERENCE / (name + '-encode.log')).open('w', encoding='utf-8')
    encoder = subprocess.Popen([
        imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error',
        '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', '960x600',
        '-r', str(sample_fps / 2), '-i', '-', '-an', '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(output)],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
    frames, next_time, index = [], start, -1
    try:
        with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                index += 1
                time = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                if time <= 0 and index:
                    time = index / fps
                if time > end:
                    break
                if time + .0001 < next_time:
                    continue
                next_time += 1 / sample_fps
                roi = frame[y:y+h, x:x+w]
                result = detector.detect_for_video(mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=np.ascontiguousarray(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))), round(time*1000))
                candidates = []
                for pose_index, landmarks in enumerate(result.pose_landmarks):
                    hip = np.array([(landmarks[23].x + landmarks[24].x)/2,
                                    (landmarks[23].y + landmarks[24].y)/2])
                    confidence = float(np.mean([landmarks[j].visibility for j in IMPORTANT]))
                    if hip[1] < .32 or not -.05 < hip[0] < .8:
                        continue
                    distance = float(np.linalg.norm(hip - previous))
                    if distance < .28:
                        candidates.append((distance + .15*(1-confidence), pose_index, hip))
                chosen = min(candidates, default=None, key=lambda c: c[0])
                points = []
                if chosen:
                    _, pose_index, previous = chosen
                    landmarks = result.pose_landmarks[pose_index]
                    world = result.pose_world_landmarks[pose_index]
                    for j, (p, q) in enumerate(zip(landmarks, world)):
                        points.append({'id': j, 'name': NAMES[j],
                                       'image_x_px': round(x+p.x*w, 3), 'image_y_px': round(y+p.y*h, 3),
                                       'visibility': round(p.visibility, 5), 'presence': round(p.presence, 5),
                                       'estimated_hip_relative_m': [round(q.x, 6), round(q.y, 6), round(q.z, 6)]})
                annotated = cv2.resize(roi, (640, 520))
                for a, b in EDGES if points else []:
                    pa, pb = landmarks[a], landmarks[b]
                    if min(pa.visibility, pb.visibility, pa.presence, pb.presence) < .65:
                        continue  # Never connect uncertain joints into a confident skeleton.
                    colour = (255, 210, 30) if a % 2 else (30, 150, 255)
                    cv2.line(annotated, (round(pa.x*640), round(pa.y*520)),
                             (round(pb.x*640), round(pb.y*520)), colour, 2, cv2.LINE_AA)
                for j in IMPORTANT if points else []:
                    p = landmarks[j]
                    if not 0 <= p.x <= 1 or not 0 <= p.y <= 1:
                        continue
                    xy = (round(p.x*640), round(p.y*520))
                    conf = min(p.visibility, p.presence)
                    colour = (255, 210, 30) if j % 2 else (30, 150, 255)
                    if conf >= .65:
                        cv2.circle(annotated, xy, 4, colour, -1, cv2.LINE_AA)
                        cv2.putText(annotated, str(j), (xy[0]+5, xy[1]-3), cv2.FONT_HERSHEY_SIMPLEX, .4, colour, 1, cv2.LINE_AA)
                    else:
                        cv2.drawMarker(annotated, xy, (80, 80, 255), cv2.MARKER_TILTED_CROSS, 7, 1)
                canvas = np.full((600, 960, 3), (25, 22, 18), dtype=np.uint8)
                canvas[50:570, :640] = annotated
                cv2.putText(canvas, f'{name.upper()}  source {time:.3f}s  frame {index}', (12, 27), cv2.FONT_HERSHEY_SIMPLEX, .6, (240, 240, 240), 1, cv2.LINE_AA)
                cv2.putText(canvas, 'ML estimate | review at 0.5x | NOT validated 3D motion', (12, 592), cv2.FONT_HERSHEY_SIMPLEX, .48, (200, 220, 255), 1, cv2.LINE_AA)
                for n, j in enumerate(IMPORTANT):
                    label = f'{j:02} {NAMES[j]}  {min(points[j]["visibility"],points[j]["presence"]):.2f}' if points else f'{j:02} {NAMES[j]}  MISSING'
                    cv2.putText(canvas, label, (654, 85+n*28), cv2.FONT_HERSHEY_SIMPLEX, .43, (230, 230, 230), 1, cv2.LINE_AA)
                for n, label in enumerate(['cyan: anatomical left', 'orange: anatomical right', 'red X: confidence below .65', 'missing lines stay missing', 'confirm identity / L-R / jumps']):
                    cv2.putText(canvas, label, (654, 460+n*24), cv2.FONT_HERSHEY_SIMPLEX, .4, (190, 210, 240), 1, cv2.LINE_AA)
                encoder.stdin.write(canvas.tobytes())
                frames.append({'frame_index': index, 'source_time_seconds': round(time, 6), 'landmarks': points})
                if len(frames) % 15 == 0:
                    print(f'{name}: {len(frames)} sampled frames processed', flush=True)
    finally:
        cap.release()
        encoder.stdin.close()
        encoder.wait(timeout=20)
        log.close()
    if encoder.returncode:
        raise RuntimeError(f'Encoder failed; see {name}-encode.log')
    detected = sum(bool(f['landmarks']) for f in frames)
    coverage = {NAMES[j]: sum(bool(f['landmarks']) and min(f['landmarks'][j]['visibility'], f['landmarks'][j]['presence']) >= .65 for f in frames) for j in IMPORTANT}
    payload = {'schema': 'pitch_video_pose_estimate_v1', 'source': str(source.relative_to(ROOT)),
               'source_sha256': sha(source), 'source_dimensions': [width, height], 'decoder_fps': fps,
               'crop_px': [x, y, w, h], 'sample_fps_target': sample_fps, 'review_playback_rate': .5,
               'model': 'Google MediaPipe Pose Landmarker Full float16/1', 'model_sha256': sha(MODEL),
               'mediapipe_version': mp.__version__, 'model_url': 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task',
               'coordinate_notice': 'Image pixels use full source frame. Estimated hip-relative metres are monocular ML predictions, NOT field-calibrated Statcast positions or measured mocap.',
               'identity_notice': 'Clip-specific ROI and temporal hip proximity; pitcher identity and anatomical left/right need user review.',
               'visual_acceptance': 'pending_user', 'retargeting_enabled': False,
               'summary': {'frames': len(frames), 'detected': detected, 'missing': len(frames)-detected, 'joint_frames_above_065': coverage},
               'frames': frames}
    (REFERENCE / (name+'-pose.json')).write_text(json.dumps(payload, separators=(',', ':'))+'\n', encoding='utf-8')
    print(json.dumps({'name': name, **payload['summary']}), flush=True)
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', choices=['yesavage', 'thompson', 'all'], default='all')
    parser.add_argument('--review-only', action='store_true')
    args = parser.parse_args()
    if not args.review_only:
        for name in ['yesavage', 'thompson'] if args.name == 'all' else [args.name]:
            infer_clip(name)
    if all((REFERENCE/(name+'-pose.json')).exists() for name in ['yesavage','thompson']):
        write_review()
