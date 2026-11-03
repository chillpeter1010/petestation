"""Source-contract regressions only; never launches a browser or reads pixels."""
from copy import deepcopy
import json

import pytest

from scripts.audit_ballpark_characters import ROOT, audit_character_package, validate_character_contract


def contract():
    manifest = json.loads((ROOT / "data/sample/petehub_ballpark_character_manifest_v1.json").read_text(encoding="utf-8"))
    kit = json.loads((ROOT / manifest["runtime_kit"]).read_text(encoding="utf-8"))
    source = json.loads((ROOT / manifest["source_path"]).read_text(encoding="utf-8"))
    return manifest, kit, source


def test_delivered_character_contract():
    assert validate_character_contract(*contract()) == []


@pytest.mark.parametrize("change", ["frames", "fps", "anchor", "material", "number", "directions", "palette"])
def test_rejects_incomplete_character_contract(change):
    manifest, kit, source = deepcopy(contract())
    user = kit["roles"]["user"]
    if change == "frames":
        user["frames"] = 47
    elif change == "fps":
        kit["clips"]["walk"]["fps"] = 6
    elif change == "anchor":
        user["anchor"] = [0.5, 0.5]
    elif change == "material":
        del user["files"]["skin"]
    elif change == "number":
        user["number_positions"][0] = [999, 999]
    elif change == "directions":
        kit["directions"] = ["south"]
    else:
        del kit["palettes"]["skin"]["tone_4"]
    assert validate_character_contract(manifest, kit, source)


def test_reports_missing_manifest(tmp_path):
    errors, _ = audit_character_package(tmp_path / "absent.json")
    assert errors == ["Missing character manifest"]


def test_rejects_hash_tampering(tmp_path):
    manifest, _, _ = contract()
    manifest["assets"][0]["sha256"] = "0" * 64
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    errors, _ = audit_character_package(path)
    assert any("Character hash mismatch" in message for message in errors)
