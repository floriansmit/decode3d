from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from pyproj import Transformer

from decode3d.io.earthvision import nearest_resample, read_surface


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "2026 Model Decode Area" / "Depth horizons EarthVision"
DEV_SOURCE = ROOT / "all_wells" / "dev"
OUTPUT = ROOT / "apps" / "web" / "public" / "data" / "architecture-3d.json"

STUDY_WELLS = ["Farsø-1", "Gassum-1", "Hobro-1", "Hyllebjerg-1", "Kvols-1", "Voldum-1", "Års-1"]

HORIZONS = [
    ("top_chalk", "Top Chalk Group", "Top B (Top Chalk Grp)"),
    ("base_chalk", "Base Chalk Group", "Base B (Base Chalk Grp)"),
    ("top_frederikshavn", "Top Frederikshavn Formation", "Top D1 (Top Frederikshavn Fm)"),
    ("top_borglum", "Top Børglum Formation", "Top D2 (Top Børglum Fm)"),
    ("top_haldager", "Top Haldager Formation", "Top D3 (Top Haldager Fm)"),
    ("top_fjerritslev", "Top Fjerritslev Formation", "Top E1 (Top Fjerritslev Fm)"),
    ("top_gassum", "Top Gassum Formation", "Top E2'  (Top Gassum Fm ~ TS9)"),
    ("top_vinding", "Top Vinding Formation", "Top F1' (Top Vinding Fm ~ SB5)"),
    ("top_skagerrak", "Top Skagerrak Formation", "Top F1'' (Top Skagerrak)"),
    ("top_oddesund", "Top Oddesund Formation", "Top F2 (Top Oddesund Fm)"),
    ("top_tonder", "Top Tønder Formation", "Top F3 (Top Tønder Fm)"),
    ("top_falster", "Top Falster Formation", "Top F4 (Top Falster Fm)"),
    ("top_orslev", "Top Ørslev Formation", "Top F5 (Top Ørslev Fm)"),
    ("top_bunter_sandstone", "Top Bunter Sandstone Formation", "Top F6 (Top (Bunter Sst Fm)"),
    ("top_bunter_shale", "Top Bunter Shale Formation", "Top F7 (Top (Bunter Sh Fm)"),
    ("top_zechstein", "Top Zechstein Group", "Top G (Top Zechstein Grp)"),
    ("base_zechstein", "Base Zechstein / Top pre-Zechstein", "Base G (Top pre-Zechstein)"),
]

RESERVOIR_PAIRS = {
    ("top_chalk", "base_chalk"): "chalk_shallow",
    ("top_frederikshavn", "top_borglum"): "frederikshavn",
    ("top_haldager", "top_fjerritslev"): "haldager_sand",
    ("top_gassum", "top_vinding"): "gassum",
    ("top_skagerrak", "top_oddesund"): "skagerrak",
    ("top_bunter_sandstone", "top_bunter_shale"): "bunter_sandstone",
}


def read_well_trajectory(path: Path, transformer: Transformer) -> dict:
    """Read Petrel DEV XYZ traces and convert ED50 / UTM 32N to WGS84."""
    samples = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split()
        if len(fields) < 5:
            continue
        try:
            md, x, y, elevation = map(float, fields[:4])
        except ValueError:
            continue
        lon, lat = transformer.transform(x, y)
        samples.append(
            {
                "md_m": round(md, 1),
                "lon": round(float(lon), 6),
                "lat": round(float(lat), 6),
                "depth_m_bmsl": round(-elevation, 1),
            }
        )
    return {"name": path.stem, "source": str(path.relative_to(ROOT)).replace("\\", "/"), "trajectory": samples}


def main() -> None:
    resolution = 500
    step = 4
    x = np.arange(518000.0, 598501.0, resolution)
    y = np.arange(6249000.0, 6303501.0, resolution)
    xs, ys = x[::step], y[::step]
    xx, yy = np.meshgrid(xs, ys)
    transformer = Transformer.from_crs("EPSG:23032", "EPSG:4326", always_xy=True)
    lon, lat = transformer.transform(xx, yy)

    horizons = []
    for horizon_id, name, filename in HORIZONS:
        print(f"Sampling {name}...")
        elevation = nearest_resample(read_surface(SOURCE / filename), xx, yy)
        horizons.append(
            {
                "id": horizon_id,
                "name": name,
                "source": filename,
                "depths_m_bmsl": [round(float(value), 1) for value in (-elevation).ravel()],
            }
        )

    intervals = []
    for index in range(len(HORIZONS) - 1):
        top_id, top_name, _ = HORIZONS[index]
        base_id, base_name, _ = HORIZONS[index + 1]
        reservoir_id = RESERVOIR_PAIRS.get((top_id, base_id))
        intervals.append(
            {
                "id": reservoir_id or f"architecture_{index + 1:02d}",
                "name": (
                    next(
                        label
                        for key, label in {
                            "chalk_shallow": "Shallow Chalk / ATES",
                            "frederikshavn": "Frederikshavn Formation",
                            "haldager_sand": "Haldager Sand Formation",
                            "gassum": "Gassum Formation",
                            "skagerrak": "Skagerrak Formation",
                            "bunter_sandstone": "Bunter Sandstone Formation",
                        }.items()
                        if key == reservoir_id
                    )
                    if reservoir_id
                    else f"Non-reservoir: {top_name} to {base_name}"
                ),
                "top_horizon": top_id,
                "base_horizon": base_id,
                "kind": "reservoir" if reservoir_id else "non_reservoir",
            }
        )

    wells = [read_well_trajectory(DEV_SOURCE / f"{name}.dev", transformer) for name in STUDY_WELLS]

    payload = {
        "model_version": "earthvision-architecture-v1",
        "crs": "EPSG:23032",
        "vertical_reference": "MSL",
        "vertical_units": "m",
        "grid": {
            "rows": len(ys),
            "cols": len(xs),
            "spacing_m": resolution * step,
            "longitude": [round(float(value), 6) for value in lon.ravel()],
            "latitude": [round(float(value), 6) for value in lat.ravel()],
        },
        "horizons": horizons,
        "intervals": intervals,
        "wells": wells,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(horizons)} horizons, {len(intervals)} intervals and {len(wells)} wells to {OUTPUT}")


if __name__ == "__main__":
    main()
