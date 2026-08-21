import numpy as np
import pandas as pd

from app.services import location_heatmap_service as service


class _FakeModelStep:
    classes_ = np.arange(12)


class _FakeModel:
    named_steps = {"model": _FakeModelStep()}

    def predict_proba(self, frame):
        probabilities = np.full((len(frame), 12), 0.02, dtype="float64")
        probabilities[:, 0] = 0.35
        probabilities[:, 1] = 0.25
        probabilities[:, 2] = 0.12
        probabilities[:, 10] = 0.04
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        return probabilities


def test_build_location_heatmap_returns_all_grid_cells(monkeypatch):
    metadata = {
        "model_version": "test",
        "temperature": 1.0,
        "run_values": {label: float(index) / 100 for index, label in enumerate(service.OUTCOMES)},
        "location_plus_scale": {"mean_xrv_per_100": 4.0, "sd_xrv_per_100": 2.0, "points_per_sd": 10.0},
        "location_heatmap_scale": {"mean_xrv_per_100": 4.0, "sd_xrv_per_100": 4.0, "points_per_sd": 10.0},
    }
    context = pd.DataFrame([{"balls": 0, "strikes": 0, "outs_when_up": 0, "on_1b": 0, "on_2b": 0, "on_3b": 0, "pitches": 10}])
    density = pd.DataFrame([{"x_bin": 12, "z_bin": 12, "pitches": 8}])
    monkeypatch.setattr(service, "load_artifact", lambda: (_FakeModel(), metadata))
    monkeypatch.setattr(service, "_pitch_types", lambda _: ["4-Seam Fastball"])
    monkeypatch.setattr(service, "_observed_context", lambda *args: (context, density, 10))

    response = service.build_location_heatmap()

    assert len(response.cells) == service.GRID_SIZE**2
    assert response.sample_pitches == 10
    assert max(cell.density_pct for cell in response.cells) == 100.0
    assert all(np.isfinite(cell.location_plus) for cell in response.cells)
