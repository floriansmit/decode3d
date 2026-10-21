from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import xarray as xr
from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "derived"
OUTPUT = ROOT / "apps" / "web" / "public" / "data" / "pythermogis-preview.json"

DYNAMIC_FIELDS = [
    "power",
    "heat_pump_power",
    "capex",
    "opex",
    "utc",
    "npv",
    "hprod",
    "cop",
    "cophp",
    "pres",
    "flow_rate",
    "welld",
    "inj_temp",
    "prd_temp",
    "transmissivity_with_ntg",
    "thickness",
    "transmissivity",
    "permeability",
    "temperature",
]


def finite(value: float) -> float:
    value = float(value)
    return round(value, 4) if np.isfinite(value) else 0.0


def export_reservoir(result_path: Path) -> dict:
    reservoir_id = result_path.stem.split("__", 1)[0]
    input_path = DATA / f"{reservoir_id}__pythermogis_input.nc"
    with xr.open_dataset(result_path) as result, xr.open_dataset(input_path) as source:
        transformer = Transformer.from_crs(source.attrs["crs"], "EPSG:4326", always_xy=True)
        xx, yy = np.meshgrid(result.x.values, result.y.values)
        lon, lat = transformer.transform(xx, yy)
        valid = source.valid_mask.sel(x=result.x, y=result.y).values
        percentiles = [int(value) for value in result.p_value.values]
        arrays: dict[str, np.ndarray] = {}
        for field in DYNAMIC_FIELDS:
            values = result[field]
            if "p_value" in values.dims:
                for percentile in percentiles:
                    arrays[f"{field}_p{percentile}"] = values.sel(p_value=percentile).values
            else:
                arrays[field] = values.values
        points = []
        for row in range(len(result.y)):
            for col in range(len(result.x)):
                point = {
                    "lon": round(float(lon[row, col]), 6),
                    "lat": round(float(lat[row, col]), 6),
                    "valid_mask": finite(valid[row, col]),
                }
                for field, values in arrays.items():
                    point[field] = finite(values[row, col])
                points.append(point)
        return {
            "id": reservoir_id,
            "name": source.attrs["reservoir_name"],
            "assessment_type": source.attrs["assessment_type"],
            "points": points,
        }


def main() -> None:
    paths = sorted(DATA.glob("*__pythermogis_result.nc"))
    payload = {
        "model_version": "pythermogis-3-grid-run",
        "engine": "PyThermoGIS 3",
        "percentiles": [10, 50, 90],
        "spatial_stride": 4,
        "grid_spacing_m": 2000,
        "reservoirs": [export_reservoir(path) for path in paths],
    }
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(payload['reservoirs'])} PyThermoGIS result grids to {OUTPUT}")


if __name__ == "__main__":
    main()
