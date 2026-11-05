"""Build a source-only object inventory; never load images, browsers or runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data/sample/petehub_ballpark_object_catalog_v1.json"
LAYERS = ("collision", "foreground", "portals", "hotspots")


def cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def reference_bounds(record: dict) -> list:
    if "bounds" in record:
        return record["bounds"]
    points = record["polygon"]
    xs, ys = zip(*points)
    return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]


def render() -> tuple[Path, str, int, dict]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    source_bytes = (ROOT / catalog["source"]).read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != catalog["source_sha256"]:
        raise ValueError("Scene source changed: review catalog refs and update its source pin explicitly")
    source = json.loads(source_bytes)
    ids, totals = set(), dict.fromkeys(LAYERS, 0)
    lines = ["# Ballpark 物件盤點（生成檔，不手改）", "",
             f"權威來源：`{CATALOG.relative_to(ROOT).as_posix()}`；更新：{catalog['updated_at']}", "",
             "狀態：使用者已接受盤點與功能配置；未接線的業務功能與 NPC／動畫仍依各物件狀態列為後續工作。" if catalog["status"].startswith("mapping_and_annex_accepted") else "狀態：來源盤點與功能配置草案，待使用者確認；不是畫面完整性或功能通過。", "",
             "物件 ID 使用 `scene/object`；幾何 ID 使用 `scene/layer/id`。同一物件可連多形狀，多個看板也可共用父層形狀，不能把列數當實體物件數。", "",
             "## 共用導覽／首頁需求", "",
             "| ID | 名稱 | 功能 | Fallback | Owner |", "|---|---|---|---|---|"]
    for item in catalog["shared_hud"]:
        lines.append("| " + " | ".join(cell(item[k]) for k in ("id", "label", "feature", "fallback", "owner")) + " |")
    lines += ["", "## 限制與尚未完成項目", ""]
    lines += [f"- {note}" for note in catalog["limitations"]]
    if unified := catalog.get("unified_runtime_source"):
        lines += ["", f"現行九場景 runtime：`{unified}`；原 source pin 保留為五場景 authoring 盤點。完整有效幾何／portal／59 物件對照見 v4 object_index 及 manifest，原表不冒充整合後 target。"]
    for scene in catalog["scenes"]:
        key = scene["source_key"]
        raw = source["scenes"][key] if key else {}
        records = {f"{layer}/{entry['id']}": entry for layer in LAYERS for entry in raw.get(layer, [])}
        if len(records) != sum(len(raw.get(layer, [])) for layer in LAYERS):
            raise ValueError(f"Duplicate geometry IDs: {key}")
        lines += ["", f"## {scene['label']} · {scene['status']}", "",
                  f"場景 ID：`{scene['id']}`；接線：{scene['binding_owner']}；Fallback：`{scene['fallback']}`", ""]
        if brief := scene.get("design_brief"):
            lines += [f"- 場景：{brief['setting']}", f"- 配置草案：{brief['layout']}",
                      f"- 畫風：{brief['style']}", f"- Gate：{brief['approval']}", ""]
        if candidate := scene.get("concept_candidate"):
            lines += [f"- 已核准背景設計：`{candidate}`", ""]
        if supplement := scene.get("supplemental_package"):
            acceptance = "使用者已驗收" if scene.get("supplemental_acceptance") else "待使用者驗收"
            lines += [f"- 新增後門／場景補充包（{acceptance}）：`{supplement}`；下方 base refs 與全量幾何清單仍為凍結來源，新增門見補充包。", ""]
        lines += ["### 功能物件／候選配置", "",
                  "父層 bounds 只供盤點定位，不是可直接啟用的互動區。未定位物件不能當作已接線。", "",
                  "| 穩定 ID／名稱 | 功能 | 位置／來源 refs | Context／權限 | 觸發／狀態 | Fallback／Owner |", "|---|---|---|---|---|---|"]
        for item in scene["objects"]:
            object_id = f"{scene['id']}/{item['id']}"
            if object_id in ids:
                raise ValueError(f"Duplicate semantic object: {object_id}")
            ids.add(object_id)
            missing = set(item["refs"]) - records.keys()
            if missing:
                raise ValueError(f"Unknown references for {object_id}: {missing}")
            merged = catalog["defaults"] | item
            where = item.get("location", "") + " " + ", ".join(item["refs"])
            row = [f"{object_id} · {item['label']}", item["feature"], where.strip() or "未定位",
                   ", ".join(item["context"]) + " / " + merged["access"],
                   merged["planned_trigger"] + " / " + merged["binding_status"], item["fallback"] + " / " + item["owner"]]
            lines.append("| " + " | ".join(map(cell, row)) + " |")
        lines += ["", "### 來源幾何／現有入口全量清單", "",
                  "未另指定用途的形狀維持裝飾／阻擋，不自動成為功能入口；同名 collision／foreground 是不同層參照。", ""]
        if not key:
            if package := scene.get("runtime_package"):
                acceptance = "使用者已接受本場景介面／所列人工項目" if scene["status"] == "user_accepted_scene_object_actions_pending" else "尚待使用者操作驗收"
                lines += [f"獨立新增場景包：`{package}`；含物件 bounds／碰撞／遮擋／出口，{acceptance}。上方 refs 仍以凍結五場景來源為準，新包明細在其 JSON；物件功能未接線。"]
            else:
                lines += ["背景設計已核准，尚無接入的幾何；不虛構座標。"]
            continue
        lines += ["| 幾何 ID | 參考 bounds [x,y,w,h] | 現有 runtime target |", "|---|---|---|"]
        for ref, record in records.items():
            layer = ref.split("/")[0]
            totals[layer] += 1
            target = json.dumps(record.get("target"), ensure_ascii=False, separators=(",", ":")) if "target" in record else "裝飾／阻擋／遮擋；無 action"
            lines.append(f"| {key}/{ref} | {reference_bounds(record)} | {cell(target)} |")
        lines += ["", "背景內無獨立資料的牆面飾條、小植栽／照明與雜物列為本場景裝飾群，待使用者補漏；不是已逐像素盤點。"]
    if len(catalog["scenes"]) != 9 or totals != dict(zip(LAYERS, (138, 82, 16, 2))):
        raise ValueError(f"Unexpected scene/source coverage: {totals}")
    lines += ["", f"來源覆蓋：9 場景（5 base／4 supplemental）；{len(ids)} 個語意物件／候選；凍結五場景來源含 " +
              "、".join(f"{count} {layer}" for layer, count in totals.items()) + "。不是人工畫面驗收。", ""]
    return ROOT / catalog["generated_view"], "\n".join(lines), len(ids), totals


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check sources and generated Markdown without writing")
    args = parser.parse_args()
    output, content, count, totals = render()
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != content:
            raise SystemExit("Generated object catalog is stale")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    print(f"Source-only catalog PASS: {count} semantic objects; {totals}; {output.relative_to(ROOT)}")
