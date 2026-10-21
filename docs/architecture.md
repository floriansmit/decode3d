# Architecture

## System overview

DECODE is separated into a browser application, a geological processing library, and an optional calculation API.

```text
Geological deliveries and wells
          |
          v
src/decode3d processing pipeline
          |
          +--> scientific products in data/derived
          |
          +--> lightweight JSON previews in apps/web/public/data
                                      |
                                      v
                         apps/web interactive viewer
                                      |
                                      | HTTPS / JSON
                                      v
                  apps/api FastAPI + PyThermoGIS + Java
```

## Browser application

`apps/web` provides the demonstration and model-builder workspaces. The demonstration is driven by versioned JSON products under `apps/web/public/data`; it does not require the Python API. OpenStreetMap tiles and address-search requests require an internet connection.

The Build Model workflow keeps uploaded source files in the browser session. It records data roles, interval definitions, property methods, and provenance. When a model is ready, its calculation cells are submitted to the configured PyThermoGIS API.

## Processing library

`src/decode3d` contains:

- EarthVision horizon ingestion and gridding
- Reservoir construction and property priors
- Well-evidence conditioning
- 3D architecture preview creation
- Cultural-data preview creation
- PyThermoGIS input and result adapters

The common spatial reference for the supplied Denmark model is ED50 / UTM zone 32N (`EPSG:23032`). The canonical depth convention is positive metres below mean sea level. Petrel/EarthVision negative elevation values are inverted during ingestion.

## Calculation API

`apps/api/main.py` exposes:

- `GET /v1/pythermogis/health`
- `POST /v1/pythermogis/run`
- reservoir catalogue and location-stack endpoints for locally generated NetCDF products

The run endpoint constructs a `StochasticAquifer`, executes `ThermoGISDoublet`, and returns every result family for requested P10/P50/P90 percentiles. Calls are serialised because the Java backend is stateful. Requests are limited to 5,000 cells.

## Hosted versus local behavior

The public Site can serve all static demonstration functionality. It cannot run PyThermoGIS itself because the hosted runtime is JavaScript-based and PyThermoGIS depends on a JVM through JPype. Local execution uses the API in this repository. A future online deployment requires an authorised Python/Java container with an HTTPS endpoint.

## Security and data handling

- Raw geological and well deliveries stay outside version control.
- Browser uploads are not persisted by the current frontend.
- The PyThermoGIS package is never copied into the repository.
- Production deployments should configure allowed CORS origins rather than permitting arbitrary origins.
- Large or confidential model uploads should use authenticated object storage and expiring URLs in a future multi-user deployment.
