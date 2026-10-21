import json
from pathlib import Path

import numpy as np

from decode3d.processing.first_pass import build_dataset


ROOT = Path(__file__).resolve().parents[1]


def test_reservoir_contract_and_depth_sign():
    config = json.loads((ROOT / "config" / "reservoirs.json").read_text())
    spec = next(item for item in config["reservoirs"] if item["id"] == "gassum")
    ds = build_dataset(spec, config, np.array([550000.0]), np.array([6270000.0]))
    assert ds.top_depth.item() > 0
    assert ds.base_depth.item() >= ds.top_depth.item()
    assert ds.thickness_mean.item() >= 0
    assert "well curves" in ds.attrs["property_source"]
