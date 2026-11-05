"""Author/export D4 pixel parts and poses. Never samples or resizes concept pixels."""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageColor, ImageDraw
from PIL import __version__ as PILLOW_VERSION

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "frontend/assets/ballpark/characters/avatar-source-v1.json"
DEST = SOURCE.parent
EDITABLE = ROOT / "output/ballpark/characters-v1"
MANIFEST = ROOT / "data/sample/petehub_ballpark_character_manifest_v1.json"
LAYERS = ("detail", "skin", "uniform", "accent")
CHECK = "--check" in sys.argv
INK = "#18212e"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit(path, content):
    if CHECK:
        if not path.is_file() or path.read_bytes() != content:
            raise ValueError(f"Stale character export: {path.relative_to(ROOT)}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def png_bytes(image):
    from io import BytesIO
    stream = BytesIO()
    image.save(stream, format="PNG", optimize=False, compress_level=9)
    return stream.getvalue()


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


class PixelParts:
    def __init__(self, size):
        self.size = size
        self.scale = size[0] / 96
        self.layers = {name: Image.new("RGBA", size) for name in LAYERS}
        self.svg = ET.Element("svg", xmlns="http://www.w3.org/2000/svg", width=str(size[0]), height=str(size[1]), viewBox=f"0 0 {size[0]} {size[1]}", **{"shape-rendering": "crispEdges"})
        self.part = "body"

    def paint(self, points, material, color, outline=True):
        if not points:
            return
        vertices = [(round(x * self.scale), round(y * self.scale)) for x, y in points]
        mask = Image.new("L", self.size)
        draw = ImageDraw.Draw(mask)
        draw.polygon(vertices, fill=255)
        if outline:
            draw.line(vertices + vertices[:1], fill=255, width=max(1, round(2 * self.scale)), joint="curve")
        for image in self.layers.values():
            image.paste((0, 0, 0, 0), (0, 0), mask)
        self.layers["detail"].paste(ImageColor.getrgb(INK) + (255,), (0, 0), mask)
        fill = Image.new("L", self.size)
        ImageDraw.Draw(fill).polygon(vertices, fill=255)
        self.layers[material].paste(ImageColor.getrgb(color) + (255,), (0, 0), fill)
        ET.SubElement(self.svg, "polygon", {"points": " ".join(f"{x},{y}" for x, y in vertices), "fill": color, "stroke": INK if outline else "none", "stroke-width": str(max(1, round(2 * self.scale))), "data-part": self.part, "data-material": material})

    def rect(self, box, material, color, outline=False):
        x, y, w, h = box
        self.paint([(x, y), (x + w - 1, y), (x + w - 1, y + h - 1), (x, y + h - 1)], material, color, outline)

    def bone(self, a, b, width, material, color):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy) or 1
        nx, ny = dy / length * width / 2, -dx / length * width / 2
        self.paint([(a[0] - nx, a[1] - ny), (a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny)], material, color)


def moved(points, bob, head_scale=1):
    return [(48 + (x - 48) * head_scale, 35 + (y - 35) * head_scale + bob) for x, y in points]


def pose(source, role, direction, action, frame):
    config = source["roles"][role]
    art = PixelParts(config["frame_size"])
    side = direction in ("east", "west")
    facing = 1 if direction == "east" else -1
    swing = source["walk_swing"][frame] if action == "walk" else 0
    bob = (-1 if frame % 4 in (1, 2) else 0) if action == "walk" else source["idle_bob"][frame]
    shapes = source["shapes"][direction]
    # Each joint pose is authored in source-space; PNGs never derive from a concept.
    for index, sign in enumerate((-1, 1)):
        leg_side = "left" if index == 0 else "right"
        art.part = leg_side + "_thigh"
        phase = swing * sign
        x = (44 + sign * 4) if side else (48 + sign * 11)
        hip = (x, 99 + bob)
        knee = (x + phase * (9 if side else 2), 115 - max(phase, 0) * 3)
        ankle = (x + phase * (16 if side else 3), 134 - max(phase, 0) * 7)
        art.bone(hip, knee, 13 if side else 14, "uniform", "#c0c0c0")
        art.part = leg_side + "_lower_leg"
        art.bone(knee, ankle, 12, "uniform", "#ededed")
        art.rect([ankle[0] - 6, ankle[1] - 15, 2, 12], "accent", "#c4c4c4")
        art.part = leg_side + "_shoe"
        toe = facing * 5 if side else 0
        art.paint([(ankle[0]-7,ankle[1]-2),(ankle[0]+7,ankle[1]-2),(ankle[0]+9+toe,ankle[1]+5),(ankle[0]+8+toe,ankle[1]+9),(ankle[0]-8+toe,ankle[1]+9),(ankle[0]-9,ankle[1]+5)], "detail", "#253044")
        art.rect([ankle[0] - 7 + toe, ankle[1] + 6, 15, 3], "detail", "#e9edf2")
        art.rect([ankle[0] - 3, ankle[1] + 1, 8, 2], "detail", "#99a5b4")
    art.part = "torso"
    art.paint([(x, y + bob) for x, y in shapes["torso"]], "uniform", "#ededed")
    art.rect([35 if not side else 39, 68 + bob, 3, 27], "uniform", "#ffffff")
    art.rect([60 if not side else 58, 71 + bob, 4, 27], "uniform", "#bcbcbc")
    art.rect([31 if not side else 35, 98 + bob, 35 if not side else 27, 5], "detail", "#263143", True)
    art.rect([46, 99 + bob, 5, 3], "detail", "#b9c2cc")
    if not side:
        art.rect([46, 68 + bob, 3, 29], "accent", "#e5e5e5")
        for y in (74, 82, 90):
            art.rect([47, y + bob, 1, 2], "detail", "#73818e")
    else:
        art.rect([40 if direction == "east" else 54, 70 + bob, 3, 26], "accent", "#dddddd")
    for index, sign in enumerate((-1, 1)):
        art.part = ("left" if index == 0 else "right") + "_upper_arm"
        phase = swing * sign
        shoulder = ((43 + sign * 5) if side else (48 + sign * 20), 70 + bob)
        elbow = (shoulder[0] + phase * (8 if side else 3), 87 + bob - phase * 2)
        wrist = (shoulder[0] + phase * (15 if side else 4), 102 + bob - phase * (4 if side else 5))
        # Far side arm is narrower; the separately authored torso/head remain unmirrored.
        width = 8 if side and index == 0 else 11
        art.bone(shoulder, elbow, width + 2, "uniform", "#dedede")
        art.bone((elbow[0], elbow[1]-3), elbow, width + 2, "accent", "#e5e5e5")
        art.part = art.part.replace("upper_arm", "forearm")
        art.bone(elbow, wrist, width - 1, "skin", "#e0e0e0")
        art.rect([wrist[0] - width/2, wrist[1] - 4, width, 5], "detail", "#293446")
        art.part = art.part.replace("forearm", "hand")
        art.paint([(wrist[0]-5,wrist[1]),(wrist[0]+4,wrist[1]),(wrist[0]+5,wrist[1]+7),(wrist[0]+2,wrist[1]+10),(wrist[0]-4,wrist[1]+8)], "skin", "#f4f4f4")
        art.rect([wrist[0]+1, wrist[1]+3, 2, 4], "skin", "#b9b9b9")
    art.part = "neck"
    art.rect([41, 57 + bob, 15, 11], "skin", "#c7c7c7", True)
    art.paint([(37,64+bob),(45,69+bob),(50,69+bob),(59,64+bob),(57,69+bob),(49,73+bob),(44,73+bob),(38,69+bob)], "accent", "#dddddd", False)
    art.part = "head"
    hs = config["head_scale"]
    for key in ("ear_left", "ear_right", "head"):
        art.paint(moved(shapes[key], bob, hs), "skin", "#ededed")
    art.paint(moved(shapes["hair"], bob, hs), "detail", "#27303c", False)
    art.part = "face"
    if direction != "north":
        art.paint(moved(shapes["nose"], bob, hs), "skin", "#bababa", False)
        for x, y, w, h in shapes["brows"]:
            art.rect([48+(x-48)*hs,35+(y-35)*hs+bob,w,h], "detail", "#413c36")
        for x, y, w, h in shapes["eyes"]:
            art.rect([48+(x-48)*hs,35+(y-35)*hs+bob,w,h], "detail", "#162133")
            art.rect([48+(x-48)*hs+1,35+(y-35)*hs+bob,1,1], "detail", "#f9faf4")
        if role == "player":
            beard = [(31,49),(36,51),(39,58),(56,58),(63,51),(67,49),(64,59),(57,64),(39,64),(31,57)] if not side else ([(54,49),(63,49),(66,54),(61,59),(54,62),(44,59),(44,56),(56,57)] if direction == "east" else [(42,49),(33,49),(30,54),(35,59),(42,62),(52,59),(52,56),(40,57)])
            art.paint(moved(beard, bob, hs), "detail", "#363135", False)
        art.paint(moved(shapes["mouth"], bob, hs), "detail", "#eee3d4", False)
    art.part = "cap"
    art.paint(moved(shapes["cap"], bob, hs), "detail", "#b92f3b" if role == "player" else "#263244")
    art.paint(moved(shapes["visor"], bob, hs), "detail", "#172333")
    if direction == "south":
        art.rect([44, 15+bob, 8, 9], "accent", "#ffffff")
        art.rect([46, 17+bob, 4, 5], "detail", "#263244")
    elif direction == "north":
        art.rect([44, 24+bob, 9, 4], "detail", "#d5dce4")
        art.rect([47, 25+bob, 3, 2], "accent", "#ffffff")
    number = [round(48*art.scale),round((85+bob)*art.scale)] if not side else None
    return art, number


def tint(image, color):
    rgb = ImageColor.getrgb(color)
    channels = image.split()
    return Image.merge("RGBA", tuple(channels[i].point(lambda v, c=rgb[i]: round(v*c/255)) for i in range(3)) + (channels[3],))


def compose(layers, palette):
    out = Image.new("RGBA", next(iter(layers.values())).size)
    for name in LAYERS:
        out.alpha_composite(layers[name] if name == "detail" else tint(layers[name], palette[name]))
    return out


def number_image(source, value, scale=1):
    image = Image.new("RGBA", (12, 10))
    draw = ImageDraw.Draw(image)
    digits = str(value)
    left = (12 - (len(digits)*4-1)) // 2
    for index, digit in enumerate(digits):
        for i, bit in enumerate(source["digits"][int(digit)]):
            if bit == "1":
                draw.point((left+index*4+i%3,2+i//3), fill=(35,45,60,255))
    return image


def build():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    kit = {"asset_version": source["asset_version"], "columns": 6, "rows": 8, "directions": source["directions"], "clips": source["clips"], "palettes": source["palettes"], "roles": {}}
    exported = []
    for role, config in source["roles"].items():
        w, h = config["frame_size"]
        sheets = {name: Image.new("RGBA", (w*6,h*8)) for name in LAYERS}
        sample = Image.new("RGBA", (w*6,h*8))
        positions = []
        index = 0
        for direction in source["directions"]:
            for action, clip in source["clips"].items():
                for frame in range(clip["frames"]):
                    parts, position = pose(source, role, direction, action, frame)
                    xy = (index%6*w,index//6*h)
                    for name in LAYERS:
                        sheets[name].paste(parts.layers[name], xy)
                    palette = source["palettes"]["player"] if role == "player" else {"skin": source["palettes"]["skin"]["tone_2"], "uniform": source["palettes"]["uniform"]["neutral_home"], "accent": source["palettes"]["accent"]["orange"]}
                    composed = compose(parts.layers, palette)
                    if role == "player" and position:
                        composed.alpha_composite(number_image(source, 14), (position[0]-6,position[1]-5))
                    sample.paste(composed, xy)
                    positions.append(position)
                    if action == "idle" and frame == 0:
                        emit(EDITABLE/f"{role}-{direction}-parts.svg", ET.tostring(parts.svg, encoding="utf-8", xml_declaration=True))
                    index += 1
        paths = {}
        for name, sheet in ({**sheets,"preview":sample} if role == "user" else {"preview":sample}).items():
            path = DEST/f"{role}-{name}-v1.png"
            emit(path, png_bytes(sheet))
            paths[name] = path.name
            exported.append({"logical_id":f"character.{role}.{name}", "path":path.relative_to(ROOT).as_posix(), "sha256":sha(path), "dimensions":list(sheet.size), "bytes":path.stat().st_size})
        kit["roles"][role] = {**config,"frames":48,"number_positions":positions,"files":paths,"anchor":[0.5,1],"collision_footprint":[18,10]}
    numbers = Image.new("RGBA",(120,100))
    for value in range(100):
        numbers.paste(number_image(source,value),(value%10*12,value//10*10))
    number_path = DEST/"numbers-v1.png"
    emit(number_path,png_bytes(numbers))
    exported.append({"logical_id":"character.numbers","path":number_path.relative_to(ROOT).as_posix(),"sha256":sha(number_path),"dimensions":[120,100],"bytes":number_path.stat().st_size})
    kit["number_sheet"] = {"file":number_path.name,"frame_size":[12,10],"columns":10}
    emit(DEST/"character-kit-v1.json",json_bytes(kit))
    manifest = {"asset_version":source["asset_version"],"source_path":SOURCE.relative_to(ROOT).as_posix(),"source_sha256":sha(SOURCE),"source_script_sha256":sha(Path(__file__)),"author":source["author"],"license":source["license"],"exporter":f"build_ballpark_characters.py:v1/Pillow-{PILLOW_VERSION}","exported_at":source["authored_at"],"references":[{"path":p,"sha256":sha(ROOT/p)} for p in source["references"]],"assets":exported,"editable_parts":[{"path":p.relative_to(ROOT).as_posix(),"sha256":sha(p)} for p in sorted(EDITABLE.glob("*-parts.svg"))],"roles":{role:{k:v for k,v in spec.items() if k != "number_positions"} for role,spec in kit["roles"].items()},"clips":source["clips"],"directions":source["directions"],"runtime_kit":"frontend/assets/ballpark/characters/character-kit-v1.json","runtime_kit_sha256":sha(DEST/"character-kit-v1.json"),"human_acceptance":"pending_user_D4_character_acceptance","production_ready":False}
    manifest["human_acceptance"] = source.get("human_acceptance", "pending_user_D4_character_acceptance")
    manifest["production_ready"] = source.get("d5_asset_accepted", False)
    manifest["readiness_scope"] = "D5_character_asset_only_not_runtime_release"
    manifest["d5_acceptance_date"] = source.get("d5_acceptance_date")
    emit(MANIFEST,(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    print(f"{'Verified' if CHECK else 'Exported'} D4: 48 frames per role, 4 User material layers, 100 numbers; acceptance: {manifest['human_acceptance']}")


if __name__ == "__main__":
    build()
