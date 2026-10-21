from __future__ import annotations

import argparse
import json
from pathlib import Path

import xarray as xr


ROOT = Path(__file__).resolve().parents[3]


def prepare_aquifer_dataset(dataset: xr.Dataset) -> xr.Dataset:
    """Return only the stochastic aquifer variables expected by pythermogis."""
    required = [
        "thickness_mean",
        "thickness_sd",
        "ntg",
        "porosity",
        "top_depth",
        "ln_permeability_mean",
        "ln_permeability_sd",
    ]
    missing = [name for name in required if name not in dataset]
    if missing:
        raise ValueError(f"Missing pythermogis inputs: {', '.join(missing)}")
    aquifer = dataset[required].rename({"top_depth": "depth"})
    return aquifer.where(dataset.valid_mask == 1)


def simulate(
    path: Path,
    output: Path,
    p_values: list[int],
    chunk_size: int,
    stride: int = 1,
) -> None:
    from pythermogis.aquifer import StochasticAquifer
    from pythermogis.doublet import ThermoGISDoublet

    source = xr.load_dataset(path)
    aquifer_data = prepare_aquifer_dataset(source)
    if stride > 1:
        aquifer_data = aquifer_data.isel(x=slice(None, None, stride), y=slice(None, None, stride))
    aquifer = StochasticAquifer.from_dataset(aquifer_data)
    result = ThermoGISDoublet(aquifer=aquifer).simulate(
        p_values=p_values, chunk_size=chunk_size
    ).to_dataset()
    result.attrs.update(
        {
            "input_dataset": str(path),
            "reservoir_id": source.attrs["reservoir_id"],
            "input_contract_version": source.attrs["contract_version"],
            "spatial_stride": stride,
        }
    )
    result.to_netcdf(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reservoir", default="gassum")
    parser.add_argument("--p-values", default="10,50,90")
    parser.add_argument("--chunk-size", type=int, default=100)
    parser.add_argument("--stride", type=int, default=1, help="Run every Nth grid cell for pilot calculations")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    source = ROOT / "data" / "derived" / f"{args.reservoir}__pythermogis_input.nc"
    output = ROOT / "data" / "derived" / f"{args.reservoir}__pythermogis_result.nc"
    dataset = xr.load_dataset(source)
    aquifer = prepare_aquifer_dataset(dataset)
    if args.dry_run:
        report = {
            "reservoir_id": dataset.attrs["reservoir_id"],
            "dimensions": dict(aquifer.sizes),
            "variables": list(aquifer.data_vars),
            "valid_cells": int(dataset.valid_mask.sum()),
            "ready": True,
        }
        print(json.dumps(report, indent=2))
        return
    simulate(
        source,
        output,
        [int(v) for v in args.p_values.split(",")],
        args.chunk_size,
        args.stride,
    )


if __name__ == "__main__":
    main()
