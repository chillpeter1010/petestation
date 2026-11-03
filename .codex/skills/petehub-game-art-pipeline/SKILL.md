---
name: petehub-game-art-pipeline
description: Plan or audit Petehub Ballpark production assets from Aseprite or Blender through sprite atlases or glTF, including naming, anchors, directions, density, LOD, compression, manifests, licensing, and provenance. Do not use for one-off moodboards or ordinary website images.
---

# Petehub Game Art Pipeline

Create reproducible, versioned runtime assets while retaining editable sources and provenance. Concept imagery is not a production animation deliverable.

## Workflow

1. Confirm the active Ballpark Slice, approved art direction, target runtime, supported devices, and performance budget.
2. Inventory source files, licenses, authorship, dimensions, directions, clips, skeletons, and export tools.
3. Read [references/asset-contract.md](references/asset-contract.md) when defining an atlas, glTF, skeleton, animation naming, manifest, LOD, or delivery gate.
4. Specify deterministic export settings and keep source, generated runtime asset, and manifest responsibilities distinct.
5. Validate the asset in representative scenes and fallbacks; record measured sizes rather than future targets as passes.

## Required Inputs

- Approved visual reference and target Slice.
- Aseprite/Blender source and ownership/license evidence.
- Runtime format, directions/clips, density/LOD tiers, and device budget.
- Skeleton/anchor contract for assets that must interoperate.

## Output

Deliver or review source assets, runtime exports, a version manifest, naming and anchor/skeleton metadata, compression/LOD choices, provenance, and reproducible validation evidence.

## Prohibited

- Do not stretch or interpolate a single AI-generated image into a production animation atlas.
- Do not ship assets with unknown license, author, model/source, or modification provenance.
- Do not mix pixel densities, camera perspectives, anchors, skeleton names, or coordinate conventions silently.
- Do not discard editable Aseprite/Blender sources when generated files depend on them.
- Do not promise 2K or full 3D character coverage without an approved Slice and measured budget.

## Validation

Check manifest completeness, deterministic export, atlas frame bounds, anchor consistency, direction/clip coverage, skeleton compatibility, texture/model size, compression artifacts, LOD switching, missing-asset fallback, license/provenance, and representative desktop/narrow rendering.
