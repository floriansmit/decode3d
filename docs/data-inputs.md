# Data inputs and provenance

## Supported model-building roles

Upload evidence separately so its intended role remains explicit:

| Role | Typical formats | Purpose |
| --- | --- | --- |
| Horizons | EarthVision ASCII grid, ZMAP/CPS-3, CSV/XYZ | Reservoir tops, bases, and thickness |
| Property grids | EarthVision ASCII grid, ZMAP/CPS-3, CSV/XYZ, GeoTIFF | Porosity, NTG, permeability, temperature, or uncertainty |
| Wells | LAS plus deviation survey (`.dev`, CSV) | Logs and 3D well trajectories |
| Well tops | CSV, ASCII table, or interpreted tops export | Formation picks and interval calibration |
| Fault surfaces | EarthVision surfaces or triangulated exports | Structural inspection and later compartment modelling |
| Fault sticks/polygons | CPS-3/ZMAP or ASCII coordinates | Fault framework and horizon intersections |
| Eclipse architecture | EGRID/GRDECL | Structural reference and later 3D validation |

The browser workflow currently focuses on assembling horizons, intervals, wells, tops, and property evidence. EGRID and detailed fault ingestion remain processing-library tasks rather than direct browser calculations.

## Coordinate and depth conventions

- Default horizontal CRS: `EPSG:23032` (ED50 / UTM zone 32N)
- Horizontal unit: metres
- Canonical vertical value: positive depth in metres below mean sea level
- Petrel/EarthVision elevation: negative below mean sea level and inverted on import

Do not mix grids with different coordinate systems or vertical datums without reprojecting and documenting the transformation.

## Required reservoir properties

PyThermoGIS cells require:

- top depth or representative depth
- gross thickness mean and standard deviation
- net-to-gross
- porosity
- permeability mean and logarithmic standard deviation
- temperature, or enough information to calculate it from a geothermal gradient

Each property may be supplied by a grid, derived from wells and well tops, or represented by a constant or distribution. The chosen source and fallback must be recorded in the exported model manifest.

## Repository data policy

The following are intentionally excluded from Git:

- `2026 Model Decode Area/`
- `all_wells/`
- raw cultural-data workbooks
- generated NetCDF, GeoTIFF, and Zarr products
- deployment archives

Only lightweight, reviewed demonstration products should be added under `apps/web/public/data`. Confirm redistribution rights and remove confidential metadata before committing any new preview.
