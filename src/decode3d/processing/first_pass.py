from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio
import xarray as xr
from pyproj import Transformer, datadir as pyproj_datadir
from rasterio.transform import from_origin

from decode3d.io.earthvision import nearest_resample, read_surface
from decode3d.processing.well_conditioning import build_well_evidence


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "2026 Model Decode Area" / "Depth horizons EarthVision"
CONFIG = ROOT / "config" / "reservoirs.json"
OUTPUT = ROOT / "data" / "derived"
WEB_OUTPUT = ROOT / "apps" / "web" / "public" / "data" / "model-preview.json"


def _property_fields(spec: dict, depth: np.ndarray, x: np.ndarray, y: np.ndarray, samples: list[dict]):
    """Blend regional trends with traceable formation-level well summaries."""
    spatial = 1.0 + 0.12 * np.sin((x - x.mean()) / 9500.0) * np.cos(
        (y - y.mean()) / 8000.0
    )
    burial = np.exp(-np.maximum(depth - 1500.0, 0.0) / 5500.0)
    porosity = np.clip(spec["porosity"] * burial**0.35 * spatial, 0.03, 0.42)
    ntg = np.clip(spec["ntg"] * (0.94 + 0.08 * spatial), 0.02, 0.95)
    permeability = np.clip(spec["permeability_md"] * burial * spatial**2.0, 0.01, 5000)
    support = np.zeros_like(depth)
    usable = [item for item in samples if any(key in item for key in ("porosity", "permeability_md", "ntg"))]
    if usable:
        weights = np.stack(
            [np.exp(-(((x - item["x"]) ** 2 + (y - item["y"]) ** 2) ** 0.5 / 25000.0) ** 2) for item in usable]
        )
        total = np.sum(weights, axis=0)
        support = np.clip(total, 0.0, 1.0)
        blend = 0.72 * support
        for key, field in (("porosity", porosity), ("ntg", ntg)):
            available = np.array([key in item for item in usable])
            if available.any():
                weighted = np.sum(weights[available] * np.array([item[key] for item in usable if key in item])[:, None, None], axis=0)
                denominator = np.maximum(np.sum(weights[available], axis=0), 1e-12)
                field[:] = field * (1.0 - blend) + weighted / denominator * blend
        available = np.array(["permeability_md" in item for item in usable])
        if available.any():
            weighted_log = np.sum(weights[available] * np.array([np.log(item["permeability_md"]) for item in usable if "permeability_md" in item])[:, None, None], axis=0)
            denominator = np.maximum(np.sum(weights[available], axis=0), 1e-12)
            permeability[:] = np.exp(np.log(permeability) * (1.0 - blend) + weighted_log / denominator * blend)
    return np.clip(porosity, 0.03, 0.42), np.clip(ntg, 0.02, 0.95), np.clip(permeability, 0.01, 5000), support


def build_dataset(spec: dict, config: dict, x: np.ndarray, y: np.ndarray, samples: list[dict] | None = None) -> xr.Dataset:
    xx, yy = np.meshgrid(x, y)
    top = nearest_resample(read_surface(SOURCE / spec["top_horizon"]), xx, yy)
    base = nearest_resample(read_surface(SOURCE / spec["base_horizon"]), xx, yy)
    top_depth = -top
    base_depth = -base
    thickness = np.maximum(top - base, 0.0)
    midpoint_depth = 0.5 * (top_depth + base_depth)
    temperature = (
        config["temperature_model"]["surface_temperature_c"]
        + config["temperature_model"]["gradient_c_per_m"] * midpoint_depth
    )
    samples = samples or []
    porosity, ntg, permeability, well_support = _property_fields(spec, midpoint_depth, xx, yy, samples)
    net_thickness = thickness * ntg
    transmissivity = permeability * net_thickness / 1000.0
    thickness_sd = np.maximum(3.0, thickness * spec["thickness_relative_sd"])
    valid = (
        (top_depth >= spec["valid_depth_min_m"])
        & (top_depth <= spec["valid_depth_max_m"])
        & (thickness >= spec["minimum_thickness_m"])
    )
    confidence = np.where(valid, 0.35 + 0.4 * well_support, 0.1)

    data_vars = {
        "top_depth": (("y", "x"), top_depth),
        "base_depth": (("y", "x"), base_depth),
        "thickness_mean": (("y", "x"), thickness),
        "thickness_sd": (("y", "x"), thickness_sd),
        "net_thickness": (("y", "x"), net_thickness),
        "ntg": (("y", "x"), ntg),
        "porosity": (("y", "x"), porosity),
        "permeability": (("y", "x"), permeability),
        "ln_permeability_mean": (("y", "x"), np.log(permeability)),
        "ln_permeability_sd": (
            ("y", "x"),
            np.full_like(permeability, spec["ln_permeability_sd"]),
        ),
        "transmissivity": (("y", "x"), transmissivity),
        "temperature": (("y", "x"), temperature),
        "confidence": (("y", "x"), confidence),
        "well_support": (("y", "x"), well_support),
        "valid_mask": (("y", "x"), valid.astype(np.uint8)),
    }
    ds = xr.Dataset(data_vars, coords={"x": x, "y": y})
    units = {
        "top_depth": "m bMSL",
        "base_depth": "m bMSL",
        "thickness_mean": "m",
        "thickness_sd": "m",
        "net_thickness": "m",
        "ntg": "1",
        "porosity": "1",
        "permeability": "mD",
        "ln_permeability_mean": "ln(mD)",
        "ln_permeability_sd": "1",
        "transmissivity": "Dm",
        "temperature": "degC",
        "confidence": "1",
        "well_support": "1",
        "valid_mask": "1",
    }
    for name, unit in units.items():
        ds[name].attrs["units"] = unit
    ds.attrs.update(
        {
            "contract_version": config["contract_version"],
            "reservoir_id": spec["id"],
            "reservoir_name": spec["name"],
            "assessment_type": spec["assessment_type"],
            "crs": config["crs"],
            "vertical_reference": "MSL",
            "geometry_source": "DECODE EarthVision horizons",
            "property_source": "supplied PHIE (NPHI fallback), PERM_GEUS and Vshale well curves blended with regional priors",
            "temperature_source": "linear geothermal gradient",
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    return ds


def write_geotiffs(ds: xr.Dataset, reservoir_id: str, resolution: int) -> None:
    transform = from_origin(
        float(ds.x.min()) - resolution / 2,
        float(ds.y.max()) + resolution / 2,
        resolution,
        resolution,
    )
    for variable in ("top_depth", "thickness_mean", "porosity", "permeability", "temperature", "transmissivity", "confidence"):
        values = np.flipud(ds[variable].values).astype("float32")
        path = OUTPUT / f"{reservoir_id}__{variable}.tif"
        # Avoid an unrelated system-wide PROJ_DATA setting overriding Rasterio's
        # compatible database (common on workstations that also run PostGIS).
        rasterio_proj = Path(rasterio.__file__).resolve().parent / "proj_data"
        with rasterio.Env(PROJ_DATA=str(rasterio_proj), PROJ_LIB=str(rasterio_proj)):
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                width=values.shape[1],
                height=values.shape[0],
                count=1,
                dtype="float32",
                crs=ds.attrs["crs"],
                transform=transform,
                tiled=True,
                compress="deflate",
                nodata=np.nan,
            ) as dst:
                dst.write(values, 1)
                dst.update_tags(**{k: str(v) for k, v in ds.attrs.items()})


def _preview_record(ds: xr.Dataset, spec: dict, step: int = 4) -> dict:
    pyproj_datadir.set_data_dir(pyproj_datadir.get_data_dir())
    transformer = Transformer.from_crs(ds.attrs["crs"], "EPSG:4326", always_xy=True)
    xs = ds.x.values[::step]
    ys = ds.y.values[::step]
    xx, yy = np.meshgrid(xs, ys)
    lon, lat = transformer.transform(xx, yy)
    fields = ["top_depth", "thickness_mean", "ntg", "porosity", "permeability", "temperature", "transmissivity", "confidence", "well_support", "valid_mask"]
    values = {field: ds[field].values[::step, ::step] for field in fields}
    points = []
    for row in range(len(ys)):
        for col in range(len(xs)):
            points.append(
                {
                    "lon": round(float(lon[row, col]), 6),
                    "lat": round(float(lat[row, col]), 6),
                    **{
                        key: round(float(array[row, col]), 4)
                        for key, array in values.items()
                    },
                }
            )
    return {
        "id": spec["id"],
        "name": spec["name"],
        "assessment_type": spec["assessment_type"],
        "status": spec["status"],
        "points": points,
    }


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    resolution = int(config["grid_resolution_m"])
    # Bounds come from the supplied CRS companion metadata and cover all horizons.
    x = np.arange(518000.0, 598501.0, resolution)
    y = np.arange(6249000.0, 6303501.0, resolution)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    WEB_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    evidence = build_well_evidence()
    xx, yy = np.meshgrid(x, y)
    topography = nearest_resample(read_surface(SOURCE / "Topography"), xx, yy)
    preview = {
        "model_version": "well-conditioned-first-pass-2026-09-16",
        "contract_version": config["contract_version"],
        "crs": config["crs"],
        "disclaimer": "Geometry is model-derived. Properties are a first-pass blend of supplied well curves and regional priors; GO-Forward relationships are not present in this delivery.",
        "topography": {"points": []},
        "wells": [],
        "reservoirs": [],
    }
    manifest = {"datasets": []}
    for spec in config["reservoirs"]:
        print(f"Building {spec['name']}...")
        ds = build_dataset(spec, config, x, y, evidence["reservoir_samples"].get(spec["id"], []))
        nc_path = OUTPUT / f"{spec['id']}__pythermogis_input.nc"
        ds.to_netcdf(nc_path)
        write_geotiffs(ds, spec["id"], resolution)
        preview["reservoirs"].append(_preview_record(ds, spec))
        manifest["datasets"].append(
            {
                "reservoir_id": spec["id"],
                "path": str(nc_path.relative_to(ROOT)),
                "assessment_type": spec["assessment_type"],
                "status": spec["status"],
            }
        )
    transformer = Transformer.from_crs(config["crs"], "EPSG:4326", always_xy=True)
    topo_points = []
    for row in range(0, len(y), 4):
        for col in range(0, len(x), 4):
            lon, lat = transformer.transform(float(x[col]), float(y[row]))
            topo_points.append({"lon": round(lon, 6), "lat": round(lat, 6), "elevation": round(float(topography[row, col]), 2)})
    preview["topography"] = {"points": topo_points}
    for well in evidence["wells"]:
        lon, lat = transformer.transform(well["x"], well["y"])
        preview["wells"].append({"name": well["name"], "lon": round(lon, 6), "lat": round(lat, 6), "role": well["role"]})
    WEB_OUTPUT.write_text(json.dumps(preview, separators=(",", ":")), encoding="utf-8")
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(manifest['datasets'])} reservoir datasets to {OUTPUT}")


if __name__ == "__main__":
    main()
