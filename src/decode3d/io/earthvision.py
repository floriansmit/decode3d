from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


@dataclass(frozen=True)
class EarthVisionSurface:
    name: str
    x: np.ndarray
    y: np.ndarray
    z_msl: np.ndarray


def read_surface(path: Path) -> EarthVisionSurface:
    """Read an EarthVision scattered grid while preserving Petrel Z elevation."""
    xyz: list[tuple[float, float, float]] = []
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) < 3:
                continue
            try:
                x, y, z = map(float, fields[:3])
            except ValueError:
                continue
            if np.isfinite(z) and abs(z) < 1.0e20:
                xyz.append((x, y, z))
    if not xyz:
        raise ValueError(f"No valid XYZ values in {path}")
    values = np.asarray(xyz, dtype=np.float64)
    return EarthVisionSurface(path.name, values[:, 0], values[:, 1], values[:, 2])


def nearest_resample(
    surface: EarthVisionSurface, target_x: np.ndarray, target_y: np.ndarray
) -> np.ndarray:
    """Nearest-neighbour first-pass resampling onto a common projected grid."""
    source = np.column_stack((surface.x, surface.y))
    target = np.column_stack((target_x.ravel(), target_y.ravel()))
    _, indices = cKDTree(source).query(target, workers=-1)
    return surface.z_msl[indices].reshape(target_x.shape)

