"""Deterministic, original pixel-tile study for D2 visual approval.

This script is an editable procedural source, not an Aseprite production source.
It exports a small atlas and assembled preview; neither is a released tilemap.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).resolve()
ATLAS = ROOT / "frontend/assets/ballpark/pilot/campus-tiles-v1.png"
PREVIEW = ROOT / "output/ballpark/d2-campus-tile-pilot-v1.png"
MANIFEST = ROOT / "data/sample/petehub_ballpark_d2_tile_pilot_v1.json"
TILE = 32
GRASS = "#477a4b"
GRASS_LIGHT = "#60935b"
GRASS_DARK = "#315b38"
CLAY = "#b86b3d"
CLAY_LIGHT = "#d08a55"
CLAY_DARK = "#824c34"
STONE = "#a79b86"
STONE_DARK = "#655f5a"
INK = "#17202a"
ORANGE = "#f39b2d"


def tile(kind: str) -> Image.Image:
    image = Image.new("RGB", (TILE, TILE), GRASS if kind not in {"clay", "chalk", "stone"} else CLAY if kind in {"clay", "chalk"} else STONE)
    draw = ImageDraw.Draw(image)
    rng = random.Random(kind)
    if kind in {"grass", "stripe", "fence", "shrub", "edge"}:
        if kind == "stripe":
            for x in range(-32, 64, 12):
                draw.polygon([(x, 0), (x + 5, 0), (x + 37, 32), (x + 32, 32)], fill=GRASS_LIGHT)
        for _ in range(18):
            x, y = rng.randrange(0, 32, 2), rng.randrange(0, 32, 2)
            draw.rectangle((x, y, x + 1, y + 1), fill=rng.choice([GRASS_LIGHT, GRASS_DARK]))
    if kind in {"clay", "chalk"}:
        for _ in range(22):
            x, y = rng.randrange(0, 32, 2), rng.randrange(0, 32, 2)
            draw.rectangle((x, y, x + 1, y + 1), fill=rng.choice([CLAY_LIGHT, CLAY_DARK]))
        if kind == "chalk":
            draw.line((0, 28, 31, 3), fill="#f3efe3", width=2)
    if kind in {"stone", "edge"}:
        if kind == "edge":
            draw.rectangle((0, 9, 31, 31), fill=STONE)
            draw.rectangle((0, 8, 31, 9), fill="#c5bba6")
            start = 10
        else:
            start = 0
        for y in range(start, 32, 8):
            draw.line((0, y, 31, y), fill=STONE_DARK, width=1)
            offset = 0 if (y // 8) % 2 else 8
            for x in range(offset, 32, 16):
                draw.line((x, y, x, min(31, y + 7)), fill=STONE_DARK, width=1)
            draw.line((0, min(31, y + 1), 31, min(31, y + 1)), fill="#beb3a0", width=1)
    if kind == "fence":
        draw.rectangle((0, 8, 31, 9), fill=ORANGE)
        draw.rectangle((0, 11, 31, 12), fill=INK)
        draw.rectangle((0, 27, 31, 28), fill=INK)
        for x in range(0, 32, 7):
            draw.line((x, 12, min(31, x + 14), 27), fill="#a1aaa4", width=1)
            draw.line((x, 27, min(31, x + 14), 12), fill="#a1aaa4", width=1)
        draw.rectangle((0, 5, 3, 31), fill=INK)
        draw.rectangle((28, 5, 31, 31), fill=INK)
    if kind == "shrub":
        draw.ellipse((3, 14, 29, 31), fill="#1f3b32")
        for x, y, size in [(5, 10, 13), (15, 5, 13), (18, 15, 12), (4, 20, 9)]:
            draw.ellipse((x, y, x + size, y + size), fill=GRASS_DARK, outline="#1e432d", width=2)
            draw.rectangle((x + 3, y + 3, x + 5, y + 5), fill=GRASS_LIGHT)
    return image


def export() -> None:
    names = ["grass", "stripe", "clay", "chalk", "stone", "edge", "fence", "shrub"]
    tiles = {name: tile(name) for name in names}
    atlas = Image.new("RGB", (4 * TILE, 2 * TILE), INK)
    for index, name in enumerate(names):
        atlas.paste(tiles[name], ((index % 4) * TILE, (index // 4) * TILE))

    preview = Image.new("RGB", (20 * TILE, 12 * TILE), GRASS)
    for y in range(12):
        for x in range(20):
            kind = "stripe" if x % 4 < 2 else "grass"
            if 2 <= y <= 6 and 5 <= x <= 14 and abs(x - 9.5) + abs(y - 4) < 7:
                kind = "clay"
            if y == 7:
                kind = "fence" if x not in {9, 10} else "edge"
            if y >= 8:
                kind = "stone" if 7 <= x <= 12 else "grass"
            if y == 8 and x in {7, 12}:
                kind = "edge"
            if (x, y) in {(2, 8), (4, 10), (16, 8), (18, 10)}:
                kind = "shrub"
            preview.paste(tiles[kind], (x * TILE, y * TILE))
    draw = ImageDraw.Draw(preview)
    # Independent object layer: scoreboard, gate and field chalk.
    draw.rectangle((246, 0, 393, 58), fill="#41414a", outline=ORANGE, width=3)
    draw.rectangle((252, 5, 387, 53), fill=INK)
    draw.text((277, 12), "LEADERBOARD", font=ImageFont.load_default(), fill="#f3efe3")
    draw.text((280, 32), "AWAY  2   HOME  3", font=ImageFont.load_default(), fill="#f3efe3")
    draw.line((320, 223, 195, 151), fill="#f3efe3", width=2)
    draw.line((320, 223, 445, 151), fill="#f3efe3", width=2)
    draw.polygon([(320, 223), (312, 216), (320, 209), (328, 216)], fill="#f3efe3")
    draw.rectangle((288, 213, 291, 256), fill=INK)
    draw.rectangle((348, 213, 351, 256), fill=INK)
    draw.rectangle((287, 218, 352, 221), fill=ORANGE)
    draw.rectangle((293, 229, 346, 250), fill=INK, outline=ORANGE, width=2)
    draw.text((306, 235), "GAME", font=ImageFont.load_default(), fill="#f3efe3")
    draw.rectangle((294, 256, 345, 259), fill=INK)

    ATLAS.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(ATLAS, optimize=False)
    preview.resize((1280, 768), Image.Resampling.NEAREST).save(PREVIEW, optimize=False)
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "status": "visual_review_pilot_not_production",
        "tile_size": [TILE, TILE],
        "source_path": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": digest(SOURCE),
        "author": "Petehub project / Codex-authored procedural study",
        "license": "internal review only; release rights not yet cleared",
        "exporter": "Pillow deterministic nearest-neighbor export",
        "atlas_path": str(ATLAS.relative_to(ROOT)).replace("\\", "/"),
        "atlas_sha256": digest(ATLAS),
        "atlas_dimensions": [atlas.width, atlas.height],
        "preview_path": str(PREVIEW.relative_to(ROOT)).replace("\\", "/"),
        "preview_sha256": digest(PREVIEW),
        "tiles": {name: [index % 4, index // 4] for index, name in enumerate(names)},
        "collision_and_entrances": "not authored; visual pilot only",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"D2 pilot: {ATLAS.relative_to(ROOT)} + {PREVIEW.relative_to(ROOT)}")


if __name__ == "__main__":
    export()
