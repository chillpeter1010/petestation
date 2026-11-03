"""Deterministic D2 layered-scene export; does not modify source artwork.

The editable JSON owns geometry. SVGs expose separately named visual, mask,
collision and interaction layers using the original image, with no repainting.
Run from the repository root: python backend/scripts/build_ballpark_scenes.py
"""
from __future__ import annotations

import base64
import hashlib
import json
import struct
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
VERSION = sys.argv[sys.argv.index("--version") + 1] if "--version" in sys.argv else "v1"
if VERSION not in {"v1", "v2", "d2-5-v1", "v3"}:
    raise ValueError("Unknown scene-kit version")
SOURCE = ROOT / f"frontend/assets/ballpark/scenes/scene-kit-{VERSION}.json"
DEST = ROOT / f"output/ballpark/scenes-{VERSION}"
MANIFEST = ROOT / f"data/sample/petehub_ballpark_scene_manifest_{VERSION}.json"
SVG = "http://www.w3.org/2000/svg"
INK = "http://www.inkscape.org/namespaces/inkscape"
ET.register_namespace("", SVG)
ET.register_namespace("inkscape", INK)
CHECK = "--check" in sys.argv


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_output(path: Path, value: bytes) -> None:
    if CHECK:
        if not path.is_file() or path.read_bytes() != value:
            raise ValueError(f"Export is missing or stale: {path.relative_to(ROOT)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


def write_json(path: Path, value: object) -> None:
    # Generated runtime JSON stays compact; the editable source is the scene kit.
    options = {"separators": (",", ":")} if VERSION == "v3" and path.parent == DEST else {"indent": 2}
    write_output(path, (json.dumps(value, ensure_ascii=False, **options) + "\n").encode("utf-8"))


def svg_layer(parent: ET.Element, name: str, **attributes: str) -> ET.Element:
    return ET.SubElement(parent, f"{{{SVG}}}g", {f"{{{INK}}}groupmode": "layer", f"{{{INK}}}label": name, "id": name, **attributes})


def export() -> None:
    kit = json.loads(SOURCE.read_text(encoding="utf-8"))
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = {"schema_version": 2, "asset_version": kit["asset_version"], "source_path": SOURCE.relative_to(ROOT).as_posix(), "source_sha256": sha(SOURCE), "exporter": "build_ballpark_scenes.py:v1", "render_mode": kit["render_mode"], "world_size": kit["world_size"], "footprint": kit["footprint"], "provenance": kit["provenance"], "scope": kit.get("scope", ["D2.1", "D2.2", "D2.3", "D2.4"]), "human_acceptance": kit.get("human_acceptance", "pending_new_layered_three_scene_delivery"), "scenes": []}
    if VERSION == "v3":
        manifest.update(schema_version=3, exporter="build_ballpark_scenes.py:v2", required_scene_ids=kit["required_scene_ids"])
    if "portal_overrides" in kit:
        manifest["portal_overrides"] = kit["portal_overrides"]
    for field in ("collision_additions", "collision_overrides", "pending_manual_acceptance", "followup_acceptance"):
        if field in kit:
            manifest[field] = kit[field]
    for room, scene in kit["scenes"].items():
        image = ROOT / scene["background"]
        image_size = list(struct.unpack(">II", image.read_bytes()[16:24]))
        if image_size != scene["image_size"]:
            raise ValueError(f"Background dimensions do not match explicit source size: {room}")
        width, height = kit["world_size"]
        root = ET.Element(f"{{{SVG}}}svg", {"width": str(width), "height": str(height), "viewBox": f"0 0 {width} {height}"})
        ET.SubElement(root, f"{{{SVG}}}title").text = f"{room}: editable D2 layered source preview"
        defs = ET.SubElement(root, f"{{{SVG}}}defs")
        ET.SubElement(defs, f"{{{SVG}}}image", {"id": "artwork", "width": str(width), "height": str(height), "preserveAspectRatio": "none", "href": "data:image/png;base64," + base64.b64encode(image.read_bytes()).decode("ascii")})
        ground = svg_layer(root, "ground")
        ET.SubElement(ground, f"{{{SVG}}}use", {"href": "#artwork"})
        for item in scene["foreground"]:
            clip_id = "mask-" + item["id"]
            clip = ET.SubElement(defs, f"{{{SVG}}}clipPath", {"id": clip_id})
            ET.SubElement(clip, f"{{{SVG}}}polygon", {"points": " ".join(f"{x},{y}" for x, y in item["polygon"])})
            layer = svg_layer(root, "foreground-" + item["id"], **{"data-depth-y": str(item["depth_y"])})
            ET.SubElement(layer, f"{{{SVG}}}use", {"href": "#artwork", "clip-path": f"url(#{clip_id})"})
        collision = svg_layer(root, "collision", style="display:none")
        for item in scene["collision"]:
            ET.SubElement(collision, f"{{{SVG}}}polygon", {"id": item["id"], "points": " ".join(f"{x},{y}" for x, y in item["polygon"]), "fill": "#ee5555", "fill-opacity": ".35", "stroke": "#ff5500"})
        interactions = svg_layer(root, "interactions", style="display:none")
        for item in scene["portals"] + scene["hotspots"]:
            x, y, w, h = item["bounds"]
            ET.SubElement(interactions, f"{{{SVG}}}rect", {"id": "interaction-" + item["id"], "x": str(x), "y": str(y), "width": str(w), "height": str(h), "fill": "#44bbff", "fill-opacity": ".35"})
        svg_path = DEST / f"{room}-layers.svg"
        write_output(svg_path, ET.tostring(root, encoding="utf-8", xml_declaration=True))
        if room == "campus":
            sample = ET.fromstring(ET.tostring(root))
            sample.set("viewBox", "550 410 650 450")
            sample.set("width", "650")
            sample.set("height", "450")
            write_output(DEST / "game-entrance-layers.svg", ET.tostring(sample, encoding="utf-8", xml_declaration=True))
        scene_path = DEST / f"{room}.json"
        write_json(scene_path, {"asset_version": kit["asset_version"], "world_size": kit["world_size"], "render_mode": kit["render_mode"], **scene})
        manifest["scenes"].append({"scene_id": scene["scene_id"], "room": room, "background": scene["background"], "background_sha256": sha(image), "image_size": image_size, "world_scale": [width / image_size[0], height / image_size[1]], "background_bytes": image.stat().st_size, "editable_source": svg_path.relative_to(ROOT).as_posix(), "editable_source_sha256": sha(svg_path), "runtime_path": scene_path.relative_to(ROOT).as_posix(), "runtime_sha256": sha(scene_path), "collision_count": len(scene["collision"]), "foreground_count": len(scene["foreground"]), "portal_count": len(scene["portals"]), "decoded_texture_bytes": image_size[0] * image_size[1] * 4})
        if "fallback" in scene:
            manifest["scenes"][-1]["fallback"] = scene["fallback"]
    # The entrance pilot is a real region of Campus, not another generated image.
    pilot = {"source_scene": "campus", "world_region": [550, 410, 650, 450], "foreground_ids": ["game-gate", "west-front-lamp", "east-front-lamp", "entrance-lamp-west", "entrance-lamp-east"], "collision_ids": ["field-fence", "gate-lamp-west", "gate-lamp-east"], "portal_ids": ["game"], "visual_direction": "user_approved", "human_acceptance": "included_in_three_scene_delivery"}
    if "campus" in kit["scenes"]:
        if VERSION == "v3":
            pilot["human_acceptance"] = kit["human_acceptance"]
        write_json(DEST / "game-entrance-pilot.json", pilot)
        manifest["entrance_pilot"] = (DEST / "game-entrance-pilot.json").relative_to(ROOT).as_posix()
        manifest["entrance_editable_source"] = (DEST / "game-entrance-layers.svg").relative_to(ROOT).as_posix()
        manifest["entrance_editable_sha256"] = sha(DEST / "game-entrance-layers.svg")
    if VERSION == "v3":
        manifest["totals"] = {field: sum(s[field] for s in manifest["scenes"]) for field in ("collision_count", "foreground_count", "portal_count", "background_bytes", "decoded_texture_bytes")}
    write_json(MANIFEST, manifest)
    print(f"{'Verified reproducible exports for' if CHECK else 'Exported'} {len(manifest['scenes'])} editable scenes and manifest; human acceptance: {manifest['human_acceptance']}.")


if __name__ == "__main__":
    export()
