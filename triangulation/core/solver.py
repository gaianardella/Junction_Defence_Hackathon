"""TDOA non-linear least-squares localizer.

Grid-search global init (robust to hyperbola branch ambiguity) followed
by Levenberg-Marquardt refinement. ``localize_fast`` skips the grid
when a known-good seed is available, e.g. inside the Monte-Carlo loop.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares

from .io import relative_times

C = 343.0  # speed of sound, m/s, at ~20 °C dry air


def _residuals(pos: np.ndarray, drones: np.ndarray,
               dd_meas: np.ndarray, ref: int) -> np.ndarray:
    d = np.linalg.norm(drones - pos, axis=1)
    res = (d - d[ref]) - dd_meas
    return np.delete(res, ref)  # drop the structural zero


def _solve(drones: np.ndarray, dd_meas: np.ndarray,
           ref: int, x0: np.ndarray) -> np.ndarray:
    return least_squares(
        _residuals, x0, args=(drones, dd_meas, ref), method="lm"
    ).x


def localize(events: Sequence[Mapping],
             drone_positions: Mapping[str, Iterable[float]],
             ts_field: str = "event_time_ns",
             area: tuple[float, float, float, float] | None = None,
             grid: int = 120) -> tuple[np.ndarray, dict]:
    """Grid-init followed by LS refinement. Returns ``(estimate, diag)``.

    Parameters
    ----------
    events, drone_positions
        Detection records and a ``{drone_id: (x, y)}`` map in the local
        plane (metres).
    ts_field
        Which JSON field carries the per-drone arrival time.
    area
        ``(xmin, xmax, ymin, ymax)`` for the grid search. Auto-derived
        from the drone bounding box (±2× spread) if omitted.
    grid
        Resolution of the grid search per axis.
    """
    ids = [e["drone_id"] for e in events]
    drones = np.array([drone_positions[i] for i in ids], float)
    t = relative_times(events, ts_field=ts_field)
    ref = 0
    dd_meas = (t - t[ref]) * C

    if area is None:
        spread = max(float(np.ptp(drones, axis=0).max()), 50.0)
        cx, cy = drones.mean(axis=0)
        area = (cx - 2 * spread, cx + 2 * spread,
                cy - 2 * spread, cy + 2 * spread)

    xs = np.linspace(area[0], area[1], grid)
    ys = np.linspace(area[2], area[3], grid)
    cost = np.empty((grid, grid))
    for iy, yv in enumerate(ys):
        for ix, xv in enumerate(xs):
            r = _residuals(np.array([xv, yv]), drones, dd_meas, ref)
            cost[iy, ix] = r @ r
    j, i = np.unravel_index(np.argmin(cost), cost.shape)
    est = _solve(drones, dd_meas, ref, np.array([xs[i], ys[j]]))
    return est, dict(drones=drones, ref=ref, x0=np.array([xs[i], ys[j]]),
                     area=area)


def localize_fast(events: Sequence[Mapping],
                  drone_positions: Mapping[str, Iterable[float]],
                  x0: Iterable[float],
                  ts_field: str = "event_time_ns") -> np.ndarray:
    """No grid: refine from a known-good init. Used inside the MC loop."""
    ids = [e["drone_id"] for e in events]
    drones = np.array([drone_positions[i] for i in ids], float)
    t = relative_times(events, ts_field=ts_field)
    dd_meas = (t - t[0]) * C
    return _solve(drones, dd_meas, 0, np.asarray(x0, float))
