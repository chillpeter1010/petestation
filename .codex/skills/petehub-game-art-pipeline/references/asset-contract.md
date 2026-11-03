# Asset contract

Read this reference for production sprites, atlases, rigs, animation clips, glTF exports, LODs, or manifests.

## Source and runtime separation

- Aseprite and Blender files are editable sources; PNG/WebP atlases, textures, `.gltf`/`.glb`, and compressed variants are generated runtime outputs.
- Record exporter/tool version and meaningful export settings so outputs can be reproduced.
- Generated output must link back to a source identity and provenance record.

## Naming and geometry

Use stable lowercase identifiers for asset, variant, direction, action, and version. Define animation names centrally, including at least the approved idle/movement or baseball-action states. Specify frame order, duration/event markers, looping, origin/anchor, collision reference, pixel density, world scale, axes, and units.

For rigs, freeze skeleton and joint names before reusable clips. Record rest pose, scale, axes, retarget assumptions, root-motion policy, and any IK target. Mirrored or handed variants must state whether they share a skeleton/clip.

## Manifest minimum

Each entry needs logical ID, asset version, source path/identity, runtime files, hashes, dimensions or model statistics, density/LOD/compression tier, directions/clips, anchor or skeleton version, license, author/source URL where applicable, modification note, and build timestamp/tool version.

## Delivery gates

Validate atlas bounds and bleed, texture filtering, direction completeness, animation events, glTF load, missing-file fallback, representative memory/download size, compression artifacts, and LOD transition. AI output may support moodboards or concepts only unless every production requirement is independently authored, licensed, and validated; a single generated image is never an animation atlas.
