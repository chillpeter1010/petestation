"""Compose the accepted live scene overlays into v4 without changing their values.

Sources are retained as editable authoring packages; v4 is a deterministic bundle.
This checks source contracts only, never browser rendering or movement feel.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "frontend/assets/ballpark/scenes"
VERSIONS = ("v3", "e2-2-v1", "e2-3-4-v1", "clubhouse-annex-v1")
CATALOG = ROOT / "data/sample/petehub_ballpark_object_catalog_v1.json"
DEST = SOURCE_DIR / "scene-kit-v4.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compose() -> dict:
    paths = [SOURCE_DIR / f"scene-kit-{version}.json" for version in VERSIONS]
    packages = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    base = packages[0]
    scenes = copy.deepcopy(base["scenes"])
    for package in packages[1:]:
        assert package["world_size"] == base["world_size"]
        assert package["footprint"] == base["footprint"]
        assert not scenes.keys() & package["scenes"].keys()
        scenes.update(copy.deepcopy(package["scenes"]))
        for room, overrides in package.get("portal_overrides", {}).items():
            for portal_id, target in overrides.items():
                portal = next(p for p in scenes[room]["portals"] if p["id"] == portal_id)
                portal["target"] = copy.deepcopy(target)
        for room, additions in package.get("portal_additions", {}).items():
            scenes[room]["portals"].extend(copy.deepcopy(additions))
        for room, override in package.get("background_overrides", {}).items():
            scenes[room].update(copy.deepcopy(override))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert sha(paths[0]) == catalog["source_sha256"], "Pinned base changed"
    assert set(scenes) == {s["id"] for s in catalog["scenes"]}, "Scene/catalog mismatch"
    index = []
    for entry in catalog["scenes"]:
        room = entry["id"]
        scene = scenes[room]
        for item in entry["objects"]:
            authored = next((o for o in scene.get("objects", []) if o["id"] == item["id"]), None)
            portals = [p for p in scene["portals"] if p["id"] == item["id"] or f"portals/{p['id']}" in item["refs"]]
            references = list(item["refs"])
            if authored:
                references += ["collision/" + ref for ref in authored["collision_refs"]]
                references += ["foreground/" + ref for ref in authored["foreground_refs"]]
            references += ["portals/" + p["id"] for p in portals]
            references = sorted(set(references))
            for ref in references:
                layer, geometry_id = ref.split("/", 1)
                assert any(v["id"] == geometry_id for v in scene[layer]), (room, ref)
            bounds = authored["bounds"] if authored else portals[0]["bounds"] if portals else None
            index.append({"id": f"{room}/{item['id']}", "scene": room,
                          "geometry_refs": references, "bounds": bounds,
                          "bounds_status": "authored" if bounds else "reference_group_or_unlocated_candidate",
                          "planned_feature": item["feature"], "owner": item["owner"],
                          "context": item["context"], "fallback": item["fallback"],
                          "runtime_binding": authored["binding"] if authored else "portal" if portals else "not_connected_by_this_package",
                          "runtime_targets": [p["target"] for p in portals]})
    assert len(index) == len({o["id"] for o in index}) == 59
    for room, scene in scenes.items():
        for layer in ("collision", "foreground", "portals", "hotspots"):
            assert len(scene[layer]) == len({v["id"] for v in scene[layer]}), (room, layer)
        for portal in scene["portals"]:
            target = portal["target"]
            if target.get("room"):
                destination = scenes[target["room"]]
                assert not target.get("spawn") or any(p["id"] == target["spawn"] for p in destination["portals"])
    return {"schema_version": 4, "asset_version": "e2-scenes-v4", "scope": ["E2.5"],
            "render_mode": base["render_mode"], "world_size": base["world_size"],
            "footprint": base["footprint"], "shared": base["shared"],
            "required_scene_ids": [s["scene_id"] for s in scenes.values()],
            "human_acceptance": "authoring_scenes_catalog_and_v4_unified_navigation_accepted_by_user_2026-11-05",
            "provenance": {"author": "Petehub project / deterministic composition of accepted scene packages",
                           "license": "Retains each source package artwork/license/provenance; no new art generated",
                           "modification_note": "Exactly the live overlay composition, same backgrounds/geometry/targets; no new actions or NPCs. Old sources retained. Runtime release remains E6.",
                           "composition_sources": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p), "provenance": k["provenance"]} for p, k in zip(paths, packages)],
                           "catalog": CATALOG.relative_to(ROOT).as_posix(), "catalog_sha256": sha(CATALOG)},
            "object_index": index, "scenes": scenes}


def render(kit: dict) -> str:
    # One geometry/object record per line; never expand every coordinate to a line.
    compact = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    lines = ["{"]
    for key, value in kit.items():
        if key not in {"object_index", "scenes"}:
            lines.append(f"  {compact(key)}:{compact(value)},")
    lines.append('  "object_index":[')
    lines += ["    " + compact(value) + ("," if i < len(kit["object_index"]) - 1 else "") for i, value in enumerate(kit["object_index"])]
    lines.append('  ],\n  "scenes":{')
    for i, (room, scene) in enumerate(kit["scenes"].items()):
        lines.append(f"    {compact(room)}:{{")
        fields = list(scene.items())
        for j, (key, value) in enumerate(fields):
            suffix = "," if j < len(fields) - 1 else ""
            if key in {"collision", "foreground", "portals", "hotspots", "objects"}:
                lines.append(f"      {compact(key)}:[")
                lines += ["        " + compact(v) + ("," if k < len(value) - 1 else "") for k, v in enumerate(value)]
                lines.append("      ]" + suffix)
            else:
                lines.append(f"      {compact(key)}:{compact(value)}{suffix}")
        lines.append("    }" + ("," if i < len(kit["scenes"]) - 1 else ""))
    return "\n".join(lines + ["  }", "}", ""])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    kit = compose()
    content = render(kit)
    if args.check:
        assert DEST.read_text(encoding="utf-8") == content, "v4 package stale"
    else:
        DEST.write_text(content, encoding="utf-8")
    print(f"Source-only composition PASS: {len(kit['scenes'])} scenes, {len(kit['object_index'])} objects; exact live-overlay values; {len(content.splitlines())} lines")
