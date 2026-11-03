"""Read-only D5 release gate for the Ballpark production asset inventory."""

import hashlib
import json
import struct
import sys
import platform
from datetime import datetime, timezone
from pathlib import Path
from audit_ballpark_characters import audit_character_package


ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "data/sample/petehub_ballpark_d1_d3_asset_inventory_v1.json"
REQUIRED_SCENES = {"campus", "team_office", "clubhouse", "training_lab", "video_game_room"}
PRODUCTION_FIELDS = {"logical_id", "asset_version", "source_path", "source_sha256", "runtime_path", "runtime_sha256", "width", "height", "license", "author", "provenance", "modification_note", "exporter", "exported_at"}


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as file:
        header = file.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"Not a PNG: {path}")
    return struct.unpack(">II", header[16:24])


def audit(inventory_path: Path = INVENTORY, *, require_release: bool = True, measurements: dict | None = None) -> list[str]:
    data = json.loads(inventory_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    layered = data.get("scene_package_manifest")
    if not layered and data.get("tile_size_status") != "approved":
        errors.append("Legacy tilemap contract lacks validated logical dimensions")
    for asset in data.get("reference_assets", []):
        path = ROOT / asset["path"]
        if not path.is_file():
            errors.append(f"Missing concept reference: {asset['logical_id']}")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != asset["sha256"]:
            errors.append(f"Reference hash mismatch: {asset['logical_id']}")
        if list(png_size(path)) != asset["dimensions"]:
            errors.append(f"Reference dimensions mismatch: {asset['logical_id']}")
        if asset.get("production_eligible") is not False:
            errors.append(f"Concept must not be production eligible: {asset['logical_id']}")
    production = data.get("production_assets", [])
    if layered:
        errors.extend(audit_scene_package(ROOT / layered))
    if not production and not layered:
        errors.append("No editable-source production assets or runtime atlases")
    for asset in production:
        missing = sorted(field for field in PRODUCTION_FIELDS if not asset.get(field))
        if missing:
            errors.append(f"Incomplete manifest {asset.get('logical_id', '<unknown>')}: {', '.join(missing)}")
    scenes = {scene["scene_id"]: scene for scene in data.get("scenes", [])}
    for scene_id in sorted(REQUIRED_SCENES):
        scene = scenes.get(scene_id)
        if scene is None:
            errors.append(f"Missing scene: {scene_id}")
            continue
        required = ("editable_source", "scene_data", "collision", "entrances", "foreground") if scene.get("render_mode") == "layered_background" else ("production_tileset", "tilemap", "collision", "entrances")
        missing = [field for field in required if not scene.get(field)]
        if missing:
            errors.append(f"Scene {scene_id} not production ready: {', '.join(missing)}")
    avatar = data.get("avatar_contract", {})
    character_errors, character_metrics = audit_character_package(ROOT / avatar.get("character_manifest", ""))
    errors.extend(character_errors)
    if measurements is not None:
        measurements["characters"] = character_metrics
        backgrounds = []
        if layered:
            package = json.loads((ROOT / layered).read_text(encoding="utf-8"))
            for scene in package["scenes"]:
                path = ROOT / scene["background"]
                width, height = png_size(path)
                backgrounds.append({"path": scene["background"], "bytes": path.stat().st_size, "rgba8_bytes": width * height * 4})
        textures = character_metrics.get("textures", [])
        user_textures = [item for item in textures if "/player-" not in item["path"]]
        measurements.update(backgrounds=backgrounds,
            total_png_bytes=sum(item["bytes"] for item in backgrounds + textures),
            all_texture_rgba8_bytes=sum(item["rgba8_bytes"] for item in backgrounds + textures),
            one_room_user_rgba8_bytes=max((item["rgba8_bytes"] for item in backgrounds), default=0) + sum(item["rgba8_bytes"] for item in user_textures),
            memory_definition="Width*height*4 RGBA8 estimate only, not browser/GPU/heap measurement; one room shares its background texture across masks. Excludes driver/CPU copies and mipmaps.")
    if not avatar.get("neutral_sprite"):
        errors.append("Neutral four-direction avatar sprite is missing")
    if avatar.get("directions") != ["north", "east", "south", "west"]:
        errors.append("Avatar directions are incomplete")
    for clip, frames in (("idle", 4), ("walk", 8)):
        if avatar.get("clips", {}).get(clip, {}).get("frames_per_direction") != frames:
            errors.append(f"Avatar {clip} clip contract is incomplete")
    if require_release and data.get("production_ready") is not True:
        errors.append("Inventory is not marked production ready")
    if require_release and data.get("d5_manual_acceptance", {}).get("status") != "user_accepted":
        errors.append("D5 loading/depth/reduced-motion/device/failure-mode manual acceptance is pending")
    return errors


def audit_scene_package(path: Path) -> list[str]:
    """Source-only D2 package check; does not approve browser behavior or D5."""
    if not path.is_file():
        return ["Missing layered scene package manifest"]
    package = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    root_path = ROOT.resolve()
    def checked_file(relative: str, expected: str) -> Path | None:
        target = (ROOT / relative).resolve()
        if root_path not in target.parents or not target.is_file():
            errors.append(f"Missing or out-of-workspace scene file: {relative}")
            return None
        if sha_file(target) != expected:
            errors.append(f"Scene hash mismatch: {relative}")
        return target
    source = checked_file(package.get("source_path", ""), package.get("source_sha256", ""))
    if not source:
        return errors
    kit = json.loads(source.read_text(encoding="utf-8"))
    if package.get("render_mode") != "layered_background" or package.get("world_size") != kit.get("world_size"):
        errors.append("Scene render mode/world coordinate contract mismatch")
    for field in ("author", "license", "modification_note"):
        if not package.get("provenance", {}).get(field):
            errors.append("Missing scene provenance: " + field)
    unified = "D2.6" in package.get("scope", [])
    required = REQUIRED_SCENES if unified else {"campus", "clubhouse", "team_office"}
    ids = [s["scene_id"] for s in package.get("scenes", [])]
    if set(ids) != required or len(ids) != len(required):
        errors.append("D2 package scene set is incomplete or duplicated")
    if unified:
        if set(package.get("required_scene_ids", [])) != REQUIRED_SCENES:
            errors.append("Unified package must declare all five scene IDs")
        if package.get("footprint") != kit.get("footprint") or package.get("human_acceptance") != kit.get("human_acceptance"):
            errors.append("Unified package footprint/acceptance metadata mismatch")
        for field in ("pending_manual_acceptance", "followup_acceptance"):
            if package.get(field) != kit.get(field):
                errors.append("Scene followup acceptance metadata mismatch: " + field)
        sources = []
        for item in package.get("provenance", {}).get("composition_sources", []):
            pinned = checked_file(item["path"], item["sha256"])
            if pinned:
                sources.append(json.loads(pinned.read_text(encoding="utf-8")))
        if len(sources) != 2:
            errors.append("Missing pinned accepted scene sources")
        else:
            expected = {**sources[0]["scenes"], **sources[1]["scenes"]}
            for portal in expected["campus"]["portals"]:
                portal["target"] = sources[1]["portal_overrides"]["campus"].get(portal["id"], portal["target"])
            # Explicit followups must not mutate the pinned accepted snapshots.
            if package.get("collision_additions", {}) != kit.get("collision_additions", {}):
                errors.append("Collision followup metadata mismatch")
            for room, additions in kit.get("collision_additions", {}).items():
                if room not in expected or any(shape["id"] in {s["id"] for s in expected[room]["collision"]} for shape in additions):
                    errors.append("Collision additions must use new IDs in existing rooms")
                    continue
                expected[room]["collision"].extend(additions)
            if package.get("collision_overrides", {}) != kit.get("collision_overrides", {}):
                errors.append("Collision override metadata mismatch")
            for room, replacements in kit.get("collision_overrides", {}).items():
                originals = {shape["id"]: shape for shape in expected.get(room, {}).get("collision", [])}
                if not set(replacements).issubset(originals) or any(shape.get("id") != key for key, shape in replacements.items()):
                    errors.append("Collision overrides must replace existing IDs without renaming")
                    continue
                expected[room]["collision"] = [replacements.get(shape["id"], shape) for shape in expected[room]["collision"]]
            actual = {room: {k: v for k, v in scene.items() if k != "fallback"} for room, scene in kit["scenes"].items()}
            if actual != expected:
                errors.append("Unified scenes differ from accepted artwork/geometry/effective portals")
    for scene in package.get("scenes", []):
        background = checked_file(scene["background"], scene["background_sha256"])
        editable = checked_file(scene["editable_source"], scene["editable_source_sha256"])
        exported = checked_file(scene["runtime_path"], scene["runtime_sha256"])
        if background and list(png_size(background)) != scene["image_size"]:
            errors.append("Scene background dimensions mismatch: " + scene["room"])
        if editable:
            from xml.etree import ElementTree as ET
            svg = ET.parse(editable).getroot()
            ids = {node.get("id") for node in svg.iter()}
            if not {"ground", "collision", "interactions"}.issubset(ids) or not any((v or "").startswith("mask-") for v in ids):
                errors.append("Editable source lacks independent layers: " + scene["room"])
        if exported:
            geometry = json.loads(exported.read_text(encoding="utf-8"))
            original = kit["scenes"][scene["room"]]
            for field in ("collision", "foreground", "portals", "spawn", "image_size"):
                if not geometry.get(field) or geometry.get(field) != original.get(field):
                    errors.append(f"Missing/stale scene geometry: {scene['room']}/{field}")
            if unified:
                fallback = original.get("fallback", {})
                if fallback.get("static_route") != "/ballpark" or fallback.get("classic_route") not in {"/", "/teams", "/lab"}:
                    errors.append("Missing/invalid scene fallback: " + scene["room"])
                if scene.get("fallback") != fallback or geometry.get("fallback") != fallback:
                    errors.append("Stale scene fallback: " + scene["room"])
                for portal in original["portals"]:
                    target = portal["target"]
                    if "room" not in target:
                        continue
                    destination = kit["scenes"].get(target["room"])
                    if not destination or (target.get("spawn") and not any(p["id"] == target["spawn"] for p in destination["portals"])):
                        errors.append("Broken cross-scene portal: " + scene["room"] + "/" + portal["id"])
    checked_file(package.get("entrance_editable_source", ""), package.get("entrance_editable_sha256", ""))
    if not (ROOT / package.get("entrance_pilot", "")).is_file():
        errors.append("Missing entrance pilot")
    return errors


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    d2_only = "--scope=d2" in sys.argv
    source_only = "--scope=d5-source" in sys.argv
    measurements: dict = {}
    failures = audit_scene_package(ROOT / json.loads(INVENTORY.read_text(encoding="utf-8"))["scene_package_manifest"]) if d2_only else audit(require_release=not source_only, measurements=measurements)
    label = 'D2 scene-package source check' if d2_only else 'D5 source-only gate' if source_only else 'D5 asset gate'
    print(f"{label}: {'FAIL' if failures else 'PASS'} ({len(failures)} findings)")
    for finding in failures:
        print(f"- {finding}")
    if "--report" in sys.argv:
        report_path = (ROOT / sys.argv[sys.argv.index("--report") + 1]).resolve()
        if ROOT.resolve() not in report_path.parents:
            raise ValueError("Report must stay within workspace")
        report = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": label, "source_status": "fail" if failures else "pass", "findings": failures,
            "environment": {"os": platform.platform(), "python": platform.python_version(), "server": "not_started", "browser": "not_used_by_user_rule"},
            "measurements": measurements, "release_status": "pending_user_D5_device_loading_depth_fallback_acceptance",
            "not_measured": ["FPS/frame time", "navigation/loading", "browser/GPU memory", "input latency", "post-unmount resources", "real low-end device", "failure-mode rendering"],
            "prior_acceptance": "User accepted D2 scenes, D4 functionality and all favorite-team/RLS/net/width followups on 2026-11-02; do not repeat those approvals.",
            "future_budgets": {"atlas_target_px": 1024, "candidate_page_cap_px": 2048, "extrusion_candidate_px": 2},
            "limitations": ["Source-only PASS is not visual or runtime performance PASS", "Zero-padding nearest-filter atlases require user bleed review; no texture repacking performed", "Full E6 performance gate remains separate"]}
        inputs = [INVENTORY, Path(__file__), ROOT / "backend/scripts/audit_ballpark_characters.py",
            ROOT / "frontend/config/ballparkUniform.ts", ROOT / "frontend/components/ballpark/runtime/ballparkCharacter.ts",
            ROOT / "frontend/components/ballpark/runtime/createBallparkGame.ts", ROOT / "frontend/components/ballpark/BallparkRuntime.client.vue",
            ROOT / "data/sample/petehub_ballpark_character_manifest_v1.json", ROOT / "data/sample/petehub_ballpark_scene_manifest_v3.json"]
        report["input_hashes"] = {path.relative_to(ROOT).as_posix(): sha_file(path) for path in inputs}
        report["fallback_source_review"] = {"neutral_atlas": "present_and_hash_checked", "silhouette_and_saved_appearance": "implemented_in_ballparkCharacter.ts_not_failure_injected",
            "scene_static_and_classic_links": "implemented_in_BallparkRuntime.client.vue_not_failure_injected", "actual_fallback_rendering": "pending_user"}
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.exit(1 if failures else 0)
