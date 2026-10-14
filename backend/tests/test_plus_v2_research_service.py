from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.plus_v2_research_service import (
    PLUS_V2_VERSION,
    artifact_path,
    canonical_pitch_code,
)


def test_canonical_pitch_taxonomy_merges_slider_and_sweeper() -> None:
    assert canonical_pitch_code("ST", "Sweeper") == "SL"
    assert canonical_pitch_code("SL", "Slider") == "SL"
    assert canonical_pitch_code("FF", "4-Seam Fastball") == "FA"
    assert canonical_pitch_code("SV", "Slurve") is None


def test_research_artifact_contracts_are_present() -> None:
    root = Path(__file__).resolve().parents[2] / "data" / "derived"
    for slice_id, artifact_name in (
        (7, "plus_v2_slice7_cleaning_audit"),
        (8, "plus_v2_slice8_stuff_scale_challenger"),
        (9, "plus_v2_slice9_location_taxonomy_challenger"),
        (10, "plus_v2_slice10_calibration_subgroup_release_gate"),
    ):
        path = artifact_path(slice_id, root.parent)
        if not path.exists():
            pytest.skip(f"generated research artifact not present: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["artifact"] == artifact_name
        assert payload["version"] == PLUS_V2_VERSION
        if slice_id in {7, 10}:
            assert payload["production_impact"].startswith("none")
        else:
            assert payload["challenger_type"].endswith("no production promotion")
