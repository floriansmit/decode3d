import json
from pathlib import Path

import numpy as np

from decode3d.processing import first_pass


ROOT = Path(__file__).resolve().parents[1]


def test_reservoir_contract_and_depth_sign(tmp_path, monkeypatch):
    config = json.loads((ROOT / "config" / "reservoirs.json").read_text())
    spec = next(item for item in config["reservoirs"] if item["id"] == "gassum")
    (tmp_path / spec["top_horizon"]).write_text("550000 6270000 -1800\n")
    (tmp_path / spec["base_horizon"]).write_text("550000 6270000 -1900\n")
    monkeypatch.setattr(first_pass, "SOURCE", tmp_path)

    ds = first_pass.build_dataset(
        spec, config, np.array([550000.0]), np.array([6270000.0])
    )
    assert ds.top_depth.item() > 0
    assert ds.base_depth.item() >= ds.top_depth.item()
    assert ds.thickness_mean.item() >= 0
    assert "well curves" in ds.attrs["property_source"]
