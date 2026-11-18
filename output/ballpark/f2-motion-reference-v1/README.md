# Pitch video pose pilot — pending user review

Open `pose-review.html` yourself to inspect the two annotated clips. No agent
browser/app screenshot or visual acceptance was performed. The raw official
source videos are references only, excluded from Git and runtime packaging.
The source URLs, play IDs and SHA-256 values are in `metadata.json`.

`*-pose.json` contains raw per-frame ML estimates, visibility/presence and
source timestamps. Image pixels refer to the full source frame. Hip-relative
3D predictions are not camera/field calibrated or measured motion capture.
Confidence is not proof of correct identity, anatomical side or joint position.
Missing detections remain missing; uncertain links are not drawn as reliable.

The pretrained model is Google MediaPipe Pose Landmarker Full float16/1:
https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task
Documentation: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker
The model is used locally for inference; no individual pitcher model was trained.

Dependencies are isolated under `pose-tools` (MediaPipe 1.2.2, OpenCV 5.0.0)
and `tools` (imageio-ffmpeg); application environments were not modified.
From the repository root:

```powershell
python backend/scripts/extract_pitch_video_pose.py --name yesavage
python backend/scripts/extract_pitch_video_pose.py --name thompson
python backend/scripts/extract_pitch_video_pose.py --review-only
```

Review pitcher identity, anatomical left/right, hips/knees/ankles and fast or
occluded shoulder/elbow/wrist points. Report clip name and SOURCE seconds.
The rejected procedural pitcher delivery remains disabled. Camera calibration,
temporal quality, fixed limb lengths and constrained rig retargeting follow
keypoint review; these raw predictions are not fed directly into the rig.

## 2026-11-06 acceptance correction

User accepted the two 2D joint overlays, then rejected BOTH Personal In game 3D retarget previews for right-leg/body twisting and a pinned lead stride. Preview playback and runtime video retarget are disabled; general procedural delivery stays disabled. Fixed-bone/knee-sign/seek checks and successful compilation were insufficient for natural motion. Camera orientation, root translation and support-foot transition must be resolved before another candidate. Preserve raw source estimates and accepted generic appearance. No full-team training, measured 3D mocap or visual pass. See `data/sample/petehub_video_pose_retarget_pilot_v1.json`.
