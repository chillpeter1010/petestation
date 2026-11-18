# Two-pitcher motion method screening v1

## 2026-11-07 identity / premature cutoff correction

User reported that `yesavage-reference-03` follows the batter during preparation
(including source 1.360s), and that the source stops at 2.770s before release.
User relatively prefers MotionBERT-Lite; this is not acceptance of the input or 3D.
The previous nearest-hip selector could switch people; its longest-segment export
also incorrectly shortened the entire playback to the pose coverage interval.

Current `appearance-lock-v3` adds a fixed torso HSV appearance template, foreground
seed constraints, motion/torso-size gates and ambiguity rejection. It is conservative
candidate association, **not a trained identity recognizer**; initial identity and
mixed-person limbs still require user review. No automatic visual pass is claimed.
New raw detections are in `poses-identity-v3/`; old raw evidence is retained.

The timeline now spans the complete source video. Only the first 0.5-8s are scanned
for poses; remaining source frames explicitly lack skeletons. Eligible continuous
tracks are inferred separately; long losses remain null and ankle trails do not
join across tracks. The player stops at the video's actual end, not the last pose.
Some clips/frames therefore show no skeleton; **complete delivery through release
has not been established**. Sequential decoding replaces repeated per-frame seeks.

Source regression checks cover a nearer wrong-appearance candidate, missing/ambiguous
candidates, complete source timestamps and null pose gaps. User must check identity,
release/follow-through coverage and viewing/controls. No full build/browser/server.
The earlier method-screening snapshot below does not certify these corrected data.

Open `index.html` yourself in a browser. This is an offline local demo; no server,
CDN, login fixture or application route is needed. The agent did not open/render it.
It does not enable the rejected Personal/Game actor animation.

Current scope: ten official 2025 reference pitch videos, five each for Trey Yesavage
(702056) and Ryan Thompson (657044). Eight continuous-track model comparisons;
two Yesavage sources failed continuous tracking and remain visible as failures.
The raw detections are retained; missing source frames are not overwritten.
Long track losses/cuts are split before inference; only the longest eligible
continuous segment is compared. Selection is heuristic and remains user-reviewable.

This is **method screening**, not completed 5/10/20 learning curves. The manifest
freezes 20 nested reference pitches and five held-out pitches per player. Holdout
pitches come from a different game; none have been downloaded or processed.
Yesavage only has three games in the local 2025 source: references use two games,
holdout uses one. This cannot establish full-season generalization.

Methods:

- Google MediaPipe Pose Landmarker Full: 33 raw points, confidence and hip-relative
  depth; mapped to the 17-joint comparison skeleton with declared centre/head proxies.
- MotionBERT-Lite official pretrained H36M global-lite checkpoint, strict state-dict
  load, evaluation mode and upstream-style flip augmentation. Frozen revision and
  SHA-256 values are in `model-provenance.json`. No personal-model training.
  Author source: https://github.com/Walter0807/MotionBERT
  Official author model mirror: https://huggingface.co/walterzhu/MotionBERT
  Apache-2.0 license retained at `vendor/LICENSE` with the downloaded model source.
- Both viewers fit image-plane scale/translation to the same 2D input. This shows
  observed camera-plane travel, **not calibrated 3D root/stride in metres**.
  No feet are fixed, no manual knee Euler angles, and no character rig is retargeted.
  Grid and ankle trails are comparison aids, not measured floor/contact claims.
- WHAM was not executed: the official install targets Linux/CUDA, and SMPL body
  models need registration. This computer has Intel Arc, Python 3.14. No account,
  cloud upload or paid compute was used. MotionBERT ran on CPU in isolated `env/`.
  WHAM references: https://github.com/yohanshin/WHAM/blob/main/docs/INSTALL.md and
  https://github.com/yohanshin/WHAM/blob/main/fetch_demo_data.sh

Projection residuals compare predictions against their **input estimates**, not
manual ground truth. Bone-length CV reports instability and does not certify
anatomical correctness. Some MotionBERT outputs are less stable than baseline;
this is an experiment, not a claim of improvement or full-body accuracy.

Reproduce from repository root (existing MediaPipe isolated pilot prerequisites):

```powershell
python -m pip install --target output/ballpark/motion-method-demo-v1/env torch --index-url https://download.pytorch.org/whl/cpu
python backend/scripts/prepare_pitch_motion_demo.py model
python backend/scripts/prepare_pitch_motion_demo.py collect
python backend/scripts/build_pitch_motion_demo.py
python backend/scripts/export_pitch_motion_demo.py
python backend/scripts/check_pitch_motion_demo.py
```

Downloads and per-source detection have bounded timeouts. Completed source/model
artifacts are reused; stale comparison versions are retained but excluded from
the current exported demo. Original videos, weights and dependencies are locally
ignored and are not runtime artwork or packaged app dependencies.

User review: compare identity, anatomical sides, stride/ankle travel, hip/shoulder
rotation and throwing arm at the same source seconds. Pause, frame seek, speed
and the two synchronized 3D cameras are available. Keep 3D depth uncertainty
explicit; accept neither a new method nor the characters from numerical checks.
After selecting a usable method, proceed to calibrated root/contact estimation,
then nested 5/10/20 reference experiments and fixed holdout review. Do not average
unaligned pitches, train on the holdout or enable the failed application animation.
