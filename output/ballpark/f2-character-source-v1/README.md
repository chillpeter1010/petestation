# Generic baseball rig v1

The user accepted this F2.3 generic appearance/ready-idle milestone on 2026-11-06. It is not a
player scan, player-specific face or recorded pitching/swing mechanics.

- Base: Quaternius Universal Base Characters Standard, **Superhero Male**.
  The free pack does not contain the paid Regular Male or `.blend` source.
- License: CC0 1.0, see `LICENSE-Quaternius.txt`.
- Author/source: https://quaternius.itch.io/universal-base-characters
- Editable delivery: `actor-base-v1.gltf`, `actor-base-v1.bin` and the three
  referenced colour PNGs. Import this glTF into Blender or another glTF editor.
  The original unmodified glTF/bin are retained for provenance, but two optional
  original normal-map URIs were unresolved in the supplied export; the adapted
  editable/runtime deliveries omit those optional normal maps.
- Baseball changes: reshaped cloth shells derived from the indexed mother
  surface. Clothing and skin/sock seam vertices use identical positions, joints
  and skin weights; no independently fitted tubes or nearest-neighbour weight
  transfer. Covered body faces are rendered as the garment, not duplicated below it.
  editable equipment/handed IK/pose recipe in
  `frontend/components/charts/replay3d/createReplayActors.ts`.
- Latest appearance correction: looser torso/sleeves with collar, cuff bands,
  buttoned placket and team-colour piping. Cuff bands now use the actual sleeve
  faces and identical blended skin weights; rigid forearm-mounted rings were
  removed after the user reported protrusion. The old bare-foot triangles are
  removed entirely. Each foot has independent closed cleat upper/outsole,
  four lace cords and eight physical studs, rigidly skinned to that foot joint.
  Footwear is authored in the Python source and included in both glTF and GLB;
  this is no longer a dark material painted onto bare toes. Existing grip is preserved.
- Metres, Y up, +Z forward, positive actor scale. Source ground offset and listed
  height scaling are applied at runtime. Unknown limbs and faces stay generic.
- 65 joints, 13,864 triangles; neutral ready/idle breathing plus eight baked
  pitcher/batter × L/R × ready/idle clips. Runtime uses the editable handed IK
  recipe over the neutral breathing clips; no negative-scale body mirroring.
- Jerseys are generic game-team home/away palette variants, no logos or claim
  of the historical uniform edition. Unknown team is neutral; historical jersey
  number and individual face variations remain future staged work.
- Equipment anchors: two palm grip targets, bat knob/shaft, fielding glove and
  head gear. The primary hand's authored palm socket owns the bat; the secondary
  hand follows its lower grip by two-bone IK. Forearm twist is separated from a
  capped wrist adjustment (no 180-degree palm inversion); fingers use per-joint
  handle targets. Foot targets are preserved through breathing preview.
- Rebuild from repo root: `python backend/scripts/build_replay_character.py`.
  This invokes `frontend/scripts/bake-replay-actors.mjs`; no Blender required.
  GLB bytes/hashes and source hashes are recorded in
  `data/sample/petehub_replay_actor_manifest_v1.json`.
- No rendering/screenshot/browser checks were performed by the agent.
  User accepted the generic body/equipment appearance gate. F2.4 now has a
  procedural per-pitch delivery and batter timeline in the TypeScript recipe,
  pending user motion acceptance. It uses source release/arm angle with generic
  torso/limb/timing priors; no learned personal mechanics or measured contact.
  The GLB still contains the original ten ready/idle clips, not newly baked
  full-motion clips. Runtime motion is sampled deterministically from the UI clock.
  The initial frontal delivery was rejected by the user. The current pitcher
  recipe uses a closed set, hip-before-shoulder opening, planted lead foot and
  trailing-leg follow-through, informed by two official reference videos listed
  in `output/ballpark/f2-motion-reference-v1/metadata.json`. These phase priors
  are hand-authored, not learned 3D motion or measured player-specific mechanics.
  UPDATE: the user also rejected that revision for twisted legs. Runtime pitcher
  delivery is explicitly DISABLED; the accepted ready/idle asset is retained.
  An offline ML keypoint pilot now outputs video overlays/JSON in the reference
  directory. User review and camera/limb-constrained retargeting must precede any
  re-enabling of pitcher delivery. Numeric release fit was not motion acceptance.

## 2026-11-06 acceptance correction

User accepted the two 2D joint overlays, then rejected BOTH Personal In game 3D retarget previews for right-leg/body twisting and a pinned lead stride. Preview playback and runtime video retarget are disabled; general procedural delivery stays disabled. Fixed-bone/knee-sign/seek checks and successful compilation were insufficient for natural motion. Camera orientation, root translation and support-foot transition must be resolved before another candidate. Preserve raw source estimates and accepted generic appearance. No full-team training, measured 3D mocap or visual pass. See `data/sample/petehub_video_pose_retarget_pilot_v1.json`.
