"""Lat/lon ↔ local-plane metres.

Equirectangular ("flat-earth") projection around a user-supplied origin.
Accurate to cm over the ~1 km area a drone swarm occupies; do NOT use
this over tens of km — switch to UTM if scale grows.

The local plane has +x = east, +y = north, in metres relative to the
chosen origin.
"""

from __future__ import annotations

import numpy as np

EARTH_RADIUS_M = 6_371_000.0


def latlon_to_local(lat: float, lon: float,
                    lat0: float, lon0: float) -> tuple[float, float]:
    """Project (lat, lon) → local (x, y) metres relative to (lat0, lon0)."""
    lat_r0 = np.radians(lat0)
    x = EARTH_RADIUS_M * np.radians(lon - lon0) * np.cos(lat_r0)
    y = EARTH_RADIUS_M * np.radians(lat - lat0)
    return float(x), float(y)


def local_to_latlon(x: float, y: float,
                    lat0: float, lon0: float) -> tuple[float, float]:
    """Inverse of ``latlon_to_local``."""
    lat_r0 = np.radians(lat0)
    lat = lat0 + np.degrees(y / EARTH_RADIUS_M)
    lon = lon0 + np.degrees(x / (EARTH_RADIUS_M * np.cos(lat_r0)))
    return float(lat), float(lon)


def latlon_to_local_array(lats: np.ndarray, lons: np.ndarray,
                          lat0: float, lon0: float) -> np.ndarray:
    """Vectorised projection. Returns an (N, 2) array of (x, y)."""
    lat_r0 = np.radians(lat0)
    x = EARTH_RADIUS_M * np.radians(lons - lon0) * np.cos(lat_r0)
    y = EARTH_RADIUS_M * np.radians(lats - lat0)
    return np.column_stack([x, y])


def local_to_latlon_array(xy: np.ndarray,
                          lat0: float, lon0: float) -> np.ndarray:
    """Vectorised inverse. Input shape (N, 2). Returns (N, 2) (lat, lon)."""
    lat_r0 = np.radians(lat0)
    lat = lat0 + np.degrees(xy[:, 1] / EARTH_RADIUS_M)
    lon = lon0 + np.degrees(xy[:, 0] / (EARTH_RADIUS_M * np.cos(lat_r0)))
    return np.column_stack([lat, lon])
