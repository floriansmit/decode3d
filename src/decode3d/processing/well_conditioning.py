from __future__ import annotations

import json
import re
import shlex
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
TOPS = ROOT / "all_wells" / "tops" / "DanishNorwegianBasin (unknown sources)"
LAS_DIR = ROOT / "all_wells" / "las"
OUTPUT = ROOT / "data" / "derived" / "well_evidence.json"

BOUNDS = (518000.0, 598500.0, 6249000.0, 6303500.0)
INTERVALS = {
    "chalk_shallow": ("Top Chalk", "Top Lower Cretaceous"),
    "frederikshavn": ("Top Frederikshavn", "Top Børglum"),
    "haldager_sand": ("Top Haldager", "Top Fjerritslev"),
    "gassum": ("Top Gassum in DNB", "Top Vinding"),
    "skagerrak": ("Top Skagerrak", "Top Oddesund"),
    "bunter_sandstone": ("Top Bunter Sandstone", "Top Bunter Shale"),
}


def _normalise(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)
    ).casefold()


def read_study_well_tops() -> dict[str, dict]:
    """Read Petrel well tops and retain wells in the regional model rectangle."""
    wells: dict[str, dict] = {}
    for raw in TOPS.read_text(encoding="cp1252", errors="replace").splitlines():
        try:
            row = shlex.split(raw)
        except ValueError:
            continue
        if len(row) < 12:
            continue
        try:
            x, y, z, md = float(row[0]), float(row[1]), float(row[2]), float(row[6])
        except ValueError:
            continue
        if not (BOUNDS[0] <= x <= BOUNDS[1] and BOUNDS[2] <= y <= BOUNDS[3]):
            continue
        surface, well = row[9], row[10]
        item = wells.setdefault(well, {"name": well, "x": x, "y": y, "tops": {}})
        item["tops"][surface] = {"md": md, "z": z}
    return wells


def _find_las(well: str) -> Path | None:
    wanted = _normalise(well)
    for path in LAS_DIR.glob("*.las"):
        if _normalise(path.stem) == wanted:
            return path
    return None


def _read_las(path: Path) -> tuple[list[str], np.ndarray]:
    """Small Petrel LAS 2.0 reader for the unwrapped numeric files in this delivery."""
    curves: list[str] = []
    rows: list[list[float]] = []
    section = ""
    curve_pattern = re.compile(r"^\s*(.*?)\s+\.[^:]*:")
    with path.open(encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("~"):
                section = stripped[1:].split()[0].casefold()
                continue
            if section.startswith("curve"):
                match = curve_pattern.match(raw)
                if match:
                    curves.append(match.group(1).strip())
            elif section.startswith("ascii"):
                try:
                    values = [float(value) for value in stripped.split()]
                except ValueError:
                    continue
                if len(values) == len(curves):
                    rows.append(values)
    return curves, np.asarray(rows, dtype=float)


def _curve_index(curves: list[str], choices: tuple[str, ...]) -> int | None:
    normalised = [_normalise(item) for item in curves]
    for choice in choices:
        target = _normalise(choice)
        if target in normalised:
            return normalised.index(target)
    return None


def _valid(values: np.ndarray, low: float, high: float) -> np.ndarray:
    return values[np.isfinite(values) & (values > low) & (values < high)]


def build_well_evidence(write: bool = True) -> dict:
    wells = read_study_well_tops()
    reservoir_samples: dict[str, list[dict]] = defaultdict(list)
    records = []
    for well in wells.values():
        path = _find_las(well["name"])
        curves, data = _read_las(path) if path else ([], np.empty((0, 0)))
        depth_i = _curve_index(curves, ("DEPT",))
        phie_i = _curve_index(curves, ("PHIE-iter-1", "PHIE", "NPHI-iter-1", "NPHI"))
        perm_i = _curve_index(curves, ("PERM_GEUS-iter-1",))
        vsh_i = _curve_index(curves, ("Vshale-iter-1",))
        intervals = {}
        tops_by_norm = {_normalise(key): value for key, value in well["tops"].items()}
        for reservoir_id, (top_name, base_name) in INTERVALS.items():
            top = tops_by_norm.get(_normalise(top_name))
            base = tops_by_norm.get(_normalise(base_name))
            if not top or not base or base["md"] <= top["md"]:
                continue
            summary: dict[str, float | int | str] = {
                "top_md_m": round(top["md"], 2),
                "base_md_m": round(base["md"], 2),
                "thickness_m": round(base["md"] - top["md"], 2),
            }
            if data.size and depth_i is not None:
                interval = data[(data[:, depth_i] >= top["md"]) & (data[:, depth_i] < base["md"])]
                if phie_i is not None:
                    values = _valid(interval[:, phie_i], 0.001, 0.55)
                    if values.size:
                        summary["porosity"] = round(float(np.median(values)), 4)
                        summary["porosity_samples"] = int(values.size)
                if perm_i is not None:
                    values = _valid(interval[:, perm_i], 0.001, 100000.0)
                    if values.size:
                        summary["permeability_md"] = round(float(np.exp(np.mean(np.log(values)))), 3)
                        summary["ln_permeability_sd"] = round(float(np.std(np.log(values))), 3)
                        summary["permeability_samples"] = int(values.size)
                if vsh_i is not None:
                    values = _valid(interval[:, vsh_i], -0.01, 1.01)
                    if values.size:
                        summary["ntg"] = round(float(np.mean(values <= 0.4)), 4)
                        summary["vshale_samples"] = int(values.size)
            intervals[reservoir_id] = summary
            reservoir_samples[reservoir_id].append(
                {"well": well["name"], "x": well["x"], "y": well["y"], **summary}
            )
        direct = any(
            "porosity" in interval or "permeability_md" in interval for interval in intervals.values()
        )
        records.append(
            {
                "name": well["name"],
                "x": round(well["x"], 2),
                "y": round(well["y"], 2),
                "role": "conditioning" if direct else "tops_only",
                "las_file": str(path.relative_to(ROOT)) if path else None,
                "intervals": intervals,
            }
        )
    result = {
        "source": "Supplied Petrel well tops and LAS files",
        "method": "Formation-top intervals; median PHIE (NPHI fallback); geometric-mean PERM_GEUS; NTG as Vshale <= 0.4",
        "wells": sorted(records, key=lambda item: item["name"]),
        "reservoir_samples": dict(reservoir_samples),
    }
    if write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


if __name__ == "__main__":
    evidence = build_well_evidence()
    print(f"Wrote {len(evidence['wells'])} study-area wells to {OUTPUT}")
