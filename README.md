# DECODE 3D Geothermal Explorer

DECODE turns regional geological-model inputs into reservoir maps, an interactive 2D/3D browser, probabilistic geothermal screening outputs, and an adjustable doublet assessment.

The repository contains the processing code, FastAPI service, website, configuration, tests, and lightweight demonstration assets. Original geological deliveries, well files, generated scientific rasters, and the licensed PyThermoGIS distribution are intentionally not included.

Hosted demonstration: <https://decode-geothermal-explorer.floriansmit88.chatgpt.site/>

## Main capabilities

- Reservoir maps for depth, thickness, net-to-gross, porosity, permeability, temperature, transmissivity, and confidence
- Interactive OpenStreetMap view with address search and selectable model cells
- 3D geological architecture, formation visibility controls, property colouring, and well trajectories
- Fixed colour scales for meaningful P10/P50/P90 comparisons
- Heat-demand, district-heating, and industrial-demand context layers
- Browser-based model-building workflow for horizons, wells, tops, property grids, and uncertainty assignments
- Local FastAPI endpoint for the real PyThermoGIS 3 Java-backed calculation engine
- DoubletCalc1D workspace initialised from PyThermoGIS results

## Repository layout

```text
apps/api/               FastAPI and PyThermoGIS HTTP service
apps/web/               Interactive website and bundled demo assets
config/                 Reservoir definitions and provisional priors
docs/                   Architecture, data formats, and model contract
src/decode3d/           Geological ingestion and processing library
tests/                  Python processing tests
setup-local.cmd         One-time Windows setup launcher
run-local.cmd           Windows launcher for website + API
```

## Run locally on Windows

### Requirements

- Windows 10 or 11
- Python 3.11–3.13 available as `python`
- Node.js 22 or newer with `npm`
- A Java runtime compatible with the installed PyThermoGIS distribution
- An authorised installation of PyThermoGIS 3 in the base Python environment

PyThermoGIS 3 is licensed software and is not fetched from public PyPI by this repository. Obtain and install it through the authorised distribution channel before running the live calculation engine.

### Installation

```powershell
git clone https://github.com/floriansmit/decode3d.git
cd decode3d
.\setup-local.cmd
```

The setup creates `.venv`, installs the DECODE package and API dependencies, verifies access to PyThermoGIS 3, and installs the website dependencies. The `.cmd` launcher applies `ExecutionPolicy Bypass` only to its child process and does not modify the machine-wide PowerShell policy.

### Start the application

```powershell
.\run-local.cmd
```

Then open:

- Website: <http://localhost:5173>
- API health: <http://127.0.0.1:8000/v1/pythermogis/health>
- FastAPI schema: <http://127.0.0.1:8000/docs>

Keep the launcher window open while using the application. Press `Ctrl+C` to stop both services.

## Manual installation

The following is useful on macOS/Linux or when managing the processes independently:

```bash
python -m venv --system-site-packages .venv
# Windows: .venv/Scripts/python -m pip install -e ".[api,test]"
# macOS/Linux: .venv/bin/python -m pip install -e ".[api,test]"
cd apps/web
npm install
```

Start the API from the repository root:

```bash
.venv/bin/python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

Start the website in another terminal:

```bash
cd apps/web
NEXT_PUBLIC_PYTHERMOGIS_API=http://127.0.0.1:8000 npm run dev
```

## Data and first-pass processing

The source deliveries expected by the processing workflow are deliberately ignored by Git. Place authorised local data in the documented folders, then run:

```powershell
.\.venv\Scripts\python.exe -m decode3d.processing.first_pass
.\.venv\Scripts\python.exe -m decode3d.calculations.pythermogis_adapter --dry-run
```

Generated NetCDF and GeoTIFF products are written to `data/derived`. Downsampled, browser-safe demonstration products are written to `apps/web/public/data`.

See [Data inputs and provenance](docs/data-inputs.md) and the [data contract](docs/data-contract.md) before adding a new delivery.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest
cd apps\web
npm run build
```

GitHub Actions runs the public Python tests and frontend production build. Tests requiring the licensed PyThermoGIS engine remain local.

## Deployment boundary

The hosted demonstration uses precomputed outputs and browser-side interactions. The Build Model workflow can prepare inputs online, but executing the real PyThermoGIS engine requires the Python/Java API. A future production deployment can connect the public frontend to an authorised private container endpoint over HTTPS.

See [Architecture](docs/architecture.md) for details.

## Licensing and data rights

No licence is granted for third-party geological deliveries, well data, cultural datasets, or PyThermoGIS by this repository. Confirm the applicable licences before publishing derived data or deploying the calculation engine. See [NOTICE.md](NOTICE.md).
