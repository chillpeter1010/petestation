"""D5 source-only atlas contracts; no browser, image comparison or visual pass."""
from __future__ import annotations

import hashlib
import json
import struct
import re
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
DIRECTIONS = ["north", "east", "south", "west"]
CLIPS = {"idle": {"frames": 4, "fps": 6}, "walk": {"frames": 8, "fps": 10}}
PARTS = {"head", "torso", "neck", "cap"} | {
    f"{side}_{part}" for side in ("left", "right")
    for part in ("thigh", "lower_leg", "shoe", "upper_arm", "forearm", "hand")
}


def validate_character_contract(manifest: dict, kit: dict, source: dict) -> list[str]:
    errors = []
    for name, value in (("directions", DIRECTIONS), ("clips", CLIPS)):
        if any(data.get(name) != value for data in (manifest, kit, source)):
            errors.append(f"Character {name} contract mismatch")
    if list(kit.get("clips", {})) != ["idle", "walk"]:
        errors.append("Character clip order must match runtime frame offsets")
    if (kit.get("columns"), kit.get("rows")) != (6, 8):
        errors.append("Character atlas grid must contain 48 frames")
    if len(source.get("walk_swing", [])) != 8 or len(source.get("idle_bob", [])) != 4:
        errors.append("Authored pose arrays are incomplete")
    if kit.get("palettes") != source.get("palettes"):
        errors.append("Character source/runtime palettes mismatch")
    for material, keys in (("skin", {"tone_1", "tone_2", "tone_3", "tone_4"}), ("uniform", {"neutral_home", "neutral_away"}), ("accent", {"orange", "teal", "slate"})):
        palette = kit.get("palettes", {}).get(material, {})
        if set(palette) != keys or any(not re.fullmatch(r"#[0-9a-fA-F]{6}", color) for color in palette.values()):
            errors.append(f"Character {material} appearance coverage incomplete")
    assets = {item["path"]: item for item in manifest.get("assets", [])}
    for role, size in (("user", [96, 144]), ("player", [64, 96])):
        spec = kit.get("roles", {}).get(role, {})
        expected = manifest.get("roles", {}).get(role, {})
        if any(spec.get(k) != v for k, v in source.get("roles", {}).get(role, {}).items()):
            errors.append(f"Character {role} authored source/runtime mismatch")
        if {k: v for k, v in spec.items() if k != "number_positions"} != expected:
            errors.append(f"Character {role} manifest/runtime mismatch")
        if spec.get("frame_size") != size or spec.get("frames") != 48:
            errors.append(f"Character {role} frame bounds/count mismatch")
        if spec.get("anchor") != [0.5, 1] or spec.get("world_height") != 80 or spec.get("collision_footprint") != [18, 10]:
            errors.append(f"Character {role} anchor/world scale/footprint mismatch")
        positions = spec.get("number_positions", [])
        if len(positions) != 48:
            errors.append(f"Character {role} number anchors incomplete")
        for index, position in enumerate(positions):
            front_back = index // 12 in (0, 2)
            if front_back != (position is not None) or (position is not None and not (6 <= position[0] <= size[0] - 6 and 5 <= position[1] <= size[1] - 5)):
                errors.append(f"Character {role} number anchor outside frame or wrong facing: {index}")
        files = spec.get("files", {})
        required = {"detail", "skin", "uniform", "accent", "preview"} if role == "user" else {"preview"}
        if set(files) != required:
            errors.append(f"Character {role} material coverage incomplete")
        for filename in files.values():
            item = assets.get("frontend/assets/ballpark/characters/" + filename, {})
            if item.get("dimensions") != [size[0] * 6, size[1] * 8]:
                errors.append(f"Character atlas bounds mismatch: {filename}")
    if kit.get("number_sheet") != {"file": "numbers-v1.png", "frame_size": [12, 10], "columns": 10}:
        errors.append("Number sheet contract mismatch")
    if len(source.get("digits", [])) != 10 or any(len(digit) != 15 or set(digit) - {"0", "1"} for digit in source.get("digits", [])):
        errors.append("Number glyph source must cover digits 0-9")
    return errors


def audit_character_package(path: Path) -> tuple[list[str], dict]:
    errors, metrics = [], {}

    def checked(relative: str, digest: str) -> Path | None:
        target = (ROOT / relative).resolve()
        if ROOT.resolve() not in target.parents or not target.is_file():
            errors.append(f"Missing/out-of-workspace character source: {relative}")
            return None
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            errors.append(f"Character hash mismatch: {relative}")
        return target

    if not path.is_file():
        return ["Missing character manifest"], metrics
    manifest = json.loads(path.read_text(encoding="utf-8"))
    source_path = checked(manifest.get("source_path", ""), manifest.get("source_sha256", ""))
    kit_path = checked(manifest.get("runtime_kit", ""), manifest.get("runtime_kit_sha256", ""))
    checked("backend/scripts/build_ballpark_characters.py", manifest.get("source_script_sha256", ""))
    if not source_path or not kit_path:
        return errors, metrics
    source, kit = [json.loads(p.read_text(encoding="utf-8")) for p in (source_path, kit_path)]
    errors.extend(validate_character_contract(manifest, kit, source))
    for field in ("author", "license", "exporter", "exported_at"):
        if not manifest.get(field):
            errors.append(f"Character provenance missing: {field}")
    if manifest.get("human_acceptance") != source.get("human_acceptance"):
        errors.append("Character acceptance source/manifest mismatch")
    for item in manifest.get("references", []):
        checked(item["path"], item["sha256"])
    if [item["path"] for item in manifest.get("references", [])] != source.get("references"):
        errors.append("Character reference provenance incomplete")
    uniform_path = ROOT / "frontend/config/ballparkUniform.ts"
    team_colors = re.findall(r"([A-Z]+): \['(#[0-9a-f]{6})', '(#[0-9a-f]{6})'\]", uniform_path.read_text(encoding="utf-8"))
    team_codes = re.findall(r"code: '([A-Z]+)'", (ROOT / "frontend/config/mlbTeams.ts").read_text(encoding="utf-8"))
    if len(team_colors) != 30 or {code for code, _, _ in team_colors} != set(team_codes):
        errors.append("Favorite-team appearance palette must cover exactly the 30 supported teams")
    textures = []
    for item in manifest.get("assets", []):
        target = checked(item["path"], item["sha256"])
        if not target:
            continue
        header = target.read_bytes()[:24]
        if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            errors.append(f"Not a PNG atlas: {item['path']}")
            continue
        width, height = struct.unpack(">II", header[16:24])
        if [width, height] != item["dimensions"] or target.stat().st_size != item["bytes"]:
            errors.append(f"Character atlas dimensions/bytes stale: {item['path']}")
        if max(width, height) > 2048:
            errors.append(f"Character page exceeds candidate 2048px cap: {item['path']}")
        textures.append({"path": item["path"], "bytes": target.stat().st_size, "rgba8_bytes": width * height * 4})
    numbers = next((item for item in manifest.get("assets", []) if item["logical_id"] == "character.numbers"), {})
    if numbers.get("dimensions") != [120, 100]:
        errors.append("Number atlas does not contain 100 12x10 cells")
    expected_parts = {f"output/ballpark/characters-v1/{role}-{direction}-parts.svg" for role in ("user", "player") for direction in DIRECTIONS}
    if {item["path"] for item in manifest.get("editable_parts", [])} != expected_parts:
        errors.append("Editable character parts do not cover both roles/four directions")
    for item in manifest.get("editable_parts", []):
        target = checked(item["path"], item["sha256"])
        if target:
            parts = {node.get("data-part") for node in ET.parse(target).getroot().iter()}
            if not PARTS.issubset(parts):
                errors.append(f"Editable named body parts incomplete: {item['path']}")
    metrics.update(textures=textures, frames_per_role=48, total_frames=96,
                   numbers=100, editable_sources=8, header_only=True,
                   appearance_contracts={"neutral_combinations": 4 * 2 * 3 * 101, "favorite_team_combinations": 4 * 2 * len(team_colors) * 101, "meaning": "Available palette/material/number combinations, not rendered image or visual acceptance count"},
                   padding_pixels=0, filtering="nearest/roundPixels",
                   limitation="Frame allocations and editable parts checked, not rendered pose quality or bleed.")
    return errors, metrics
