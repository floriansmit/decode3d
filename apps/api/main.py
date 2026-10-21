from pathlib import Path
from threading import Lock
from typing import Literal

import numpy as np
import xarray as xr
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pythermogis.aquifer import StochasticAquifer
from pythermogis.doublet import ThermoGISDoublet, ThermoGISDoubletResults
from pythermogis.settings import UTCSettings


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "derived"
app = FastAPI(title="DECODE API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://decode-geothermal-explorer.floriansmit88.chatgpt.site",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
PYTHERMOGIS_LOCK = Lock()


class PyThermoGISCell(BaseModel):
    x: float
    y: float
    depth: float = Field(gt=0, le=6000)
    thickness_mean: float = Field(gt=0)
    thickness_sd: float = Field(ge=0)
    ntg: float = Field(gt=0, le=1)
    porosity: float = Field(gt=0, le=1)
    permeability_mean: float = Field(gt=0)
    permeability_ln_sd: float = Field(ge=0)
    temperature: float | None = Field(default=None, gt=0)


class PyThermoGISSettings(BaseModel):
    min_production_temp: float = 20.0
    dh_return_temp: float = 30.0
    optimize_well_distance: bool = True
    well_distance: float = 1500.0
    min_well_distance: float = 100.0
    max_well_distance: float = 3000.0
    max_flow: float = 500.0
    load_hours: float = 6000.0
    use_heatpump: bool = False
    goal_temperature: float = 70.0


class PyThermoGISRun(BaseModel):
    model_name: str = "Uploaded model"
    reservoir_id: str = "reservoir"
    percentiles: list[Literal[10, 50, 90]] = [10, 50, 90]
    cells: list[PyThermoGISCell] = Field(min_length=1, max_length=5000)
    settings: PyThermoGISSettings = PyThermoGISSettings()


def _datasets():
    for path in DATA.glob("*__pythermogis_input.nc"):
        yield path.stem.split("__", 1)[0], path


@app.get("/v1/reservoirs")
def reservoirs():
    result = []
    for reservoir_id, path in _datasets():
        with xr.open_dataset(path) as ds:
            result.append(
                {
                    "id": reservoir_id,
                    "name": ds.attrs["reservoir_name"],
                    "assessment_type": ds.attrs["assessment_type"],
                    "property_source": ds.attrs["property_source"],
                }
            )
    return result


@app.get("/v1/locations/query")
def location_query(
    x: float = Query(..., description="EPSG:23032 easting"),
    y: float = Query(..., description="EPSG:23032 northing"),
):
    stack = []
    for reservoir_id, path in _datasets():
        with xr.open_dataset(path) as ds:
            if not (float(ds.x.min()) <= x <= float(ds.x.max()) and float(ds.y.min()) <= y <= float(ds.y.max())):
                continue
            cell = ds.sel(x=x, y=y, method="nearest")
            stack.append(
                {
                    "reservoir_id": reservoir_id,
                    "reservoir_name": ds.attrs["reservoir_name"],
                    "assessment_type": ds.attrs["assessment_type"],
                    "sample_x": float(cell.x),
                    "sample_y": float(cell.y),
                    "properties": {
                        name: {"value": float(cell[name]), "unit": cell[name].attrs.get("units")}
                        for name in ("top_depth", "thickness_mean", "ntg", "porosity", "permeability", "transmissivity", "temperature", "confidence")
                    },
                }
            )
    if not stack:
        raise HTTPException(status_code=404, detail="Location outside model extent")
    stack.sort(key=lambda item: item["properties"]["top_depth"]["value"])
    return {"x": x, "y": y, "vertical_stack": stack}


@app.get("/v1/pythermogis/health")
def pythermogis_health():
    return {
        "status": "ready",
        "engine": "PyThermoGIS 3",
        "backend": "ThermoGIS Java via JPype",
        "max_cells_per_run": 5000,
    }


@app.post("/v1/pythermogis/run")
def run_pythermogis(request: PyThermoGISRun):
    """Run the real PyThermoGIS 3 stochastic doublet engine for uploaded model cells."""
    cells = request.cells
    coords = {"cell": np.arange(len(cells), dtype=int)}
    data_vars: dict[str, tuple[str, list[float]]] = {
        "thickness_mean": ("cell", [cell.thickness_mean for cell in cells]),
        "thickness_sd": ("cell", [cell.thickness_sd for cell in cells]),
        "ln_permeability_mean": ("cell", [float(np.log(cell.permeability_mean)) for cell in cells]),
        "ln_permeability_sd": ("cell", [cell.permeability_ln_sd for cell in cells]),
        "depth": ("cell", [cell.depth for cell in cells]),
        "ntg": ("cell", [cell.ntg for cell in cells]),
        "porosity": ("cell", [cell.porosity for cell in cells]),
    }
    if all(cell.temperature is not None for cell in cells):
        data_vars["temperature"] = ("cell", [float(cell.temperature) for cell in cells])
    dataset = xr.Dataset(data_vars=data_vars, coords=coords)
    aquifer = StochasticAquifer.from_dataset(dataset)
    settings = UTCSettings(**request.settings.model_dump())
    try:
        # The Java backend is stateful; serialising calls avoids cross-request JVM races.
        with PYTHERMOGIS_LOCK:
            result = ThermoGISDoublet(aquifer, settings=settings).simulate(
                p_values=request.percentiles,
            )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"PyThermoGIS calculation failed: {exc}") from exc
    return _serialise_run(request, result)


def _serialise_run(request: PyThermoGISRun, result: ThermoGISDoubletResults):
    output_names = list(ThermoGISDoubletResults.model_fields)
    outputs: dict[str, list[list[float]]] = {}
    for name in output_names:
        values = np.asarray(getattr(result, name), dtype=float)
        if values.ndim == 1:
            values = np.repeat(values[:, None], len(request.percentiles), axis=1)
        outputs[name] = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0).round(6).tolist()
    return {
        "engine": "PyThermoGIS 3",
        "backend": "ThermoGIS Java via JPype",
        "model_name": request.model_name,
        "reservoir_id": request.reservoir_id,
        "percentiles": request.percentiles,
        "cell_count": len(request.cells),
        "coordinates": [{"x": cell.x, "y": cell.y} for cell in request.cells],
        "outputs": outputs,
    }

