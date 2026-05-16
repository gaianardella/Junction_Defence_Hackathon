"""Monte-Carlo confidence cloud with per-drone σ.

Unlike a generic synthetic-σ sweep, the production pipeline gets
*per-drone* timing- and position-error estimates from the upstream
detector. The MC loop therefore needs to accept array-valued σ_t and
σ_pos so each drone is perturbed by its own reported noise level.

Both inputs accept scalars too, in which case they broadcast to all
drones (handy for synthetic sweeps and unit tests).
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

import numpy as np
from scipy.stats import chi2

from .solver import localize, localize_fast


def _broadcast(value, n: int) -> np.ndarray:
    """Scalar -> length-n array; array-like -> verified-length array."""
    arr = np.asarray(value, float).ravel()
    if arr.size == 1:
        return np.full(n, float(arr[0]))
    if arr.size != n:
        raise ValueError(f"per-drone σ length {arr.size} != {n} drones")
    return arr


def mc_confidence(events: Sequence[Mapping],
                  drone_positions: Mapping[str, Iterable[float]],
                  clock_sigma_s,
                  pos_sigma_m=0.0,
                  n: int = 400,
                  x0: np.ndarray | None = None,
                  ts_field: str = "event_time_ns",
                  rng: np.random.Generator | None = None) -> dict:
    """MC cloud + ellipse summary at the supplied (per-drone) σ values.

    Parameters
    ----------
    clock_sigma_s
        Timing uncertainty in seconds. Scalar or one value per event.
        Each MC draw perturbs every drone's timestamp by an independent
        Normal(0, σ_t[i]).
    pos_sigma_m
        Drone position uncertainty in metres. Scalar or one value per
        event. When > 0, each draw also re-samples that drone's (x, y)
        from Normal(d_i, σ_pos[i]). Captures the GPS-denied story.
    """
    rng = rng if rng is not None else np.random.default_rng()
    if x0 is None:
        x0, _ = localize(events, drone_positions, ts_field=ts_field)

    n_ev = len(events)
    sigma_t = _broadcast(clock_sigma_s, n_ev)        # seconds per event
    sigma_p = _broadcast(pos_sigma_m, n_ev)          # metres per event

    ids_in_order = [e["drone_id"] for e in events]
    base_pos = {did: np.asarray(drone_positions[did], float)
                for did in set(ids_in_order)}
    base_ts = np.array([int(e[ts_field]) for e in events])
    any_pos_noise = bool(np.any(sigma_p > 0))

    cloud = np.empty((n, 2))
    for k in range(n):
        # Per-drone timestamp jitter
        jit_ns = rng.normal(0.0, sigma_t * 1e9)      # shape (n_ev,)
        pert = [dict(e, **{ts_field: int(b + round(d))})
                for e, b, d in zip(events, base_ts, jit_ns)]

        # Per-drone position jitter (only built when needed)
        if any_pos_noise:
            pos_k = {}
            seen: dict[str, np.ndarray] = {}
            for i, did in enumerate(ids_in_order):
                if did in seen:
                    pos_k[did] = seen[did]
                else:
                    offset = rng.normal(0.0, sigma_p[i], 2) if sigma_p[i] > 0 \
                        else np.zeros(2)
                    pos_k[did] = (base_pos[did] + offset).tolist()
                    seen[did] = pos_k[did]
        else:
            pos_k = drone_positions

        cloud[k] = localize_fast(pert, pos_k, x0, ts_field=ts_field)

    mean = cloud.mean(0)
    cov = np.cov(cloud.T)
    cep50 = float(np.median(np.linalg.norm(cloud - mean, axis=1)))
    return dict(cloud=cloud, mean=mean, cov=cov, cep50=cep50)


def ellipse_xy(mean: Iterable[float], cov: np.ndarray,
               conf: float = 0.95, npts: int = 72) -> np.ndarray:
    """Closed (npts, 2) polyline tracing the confidence ellipse."""
    s = chi2.ppf(conf, df=2)
    vals, vecs = np.linalg.eigh(cov)
    o = vals.argsort()[::-1]
    vals = np.clip(vals[o], 0, None)
    vecs = vecs[:, o]
    th = np.linspace(0, 2 * np.pi, npts)
    e = vecs @ np.diag(np.sqrt(vals * s)) @ np.array([np.cos(th),
                                                      np.sin(th)])
    return (e.T + np.asarray(mean, float))


def ellipse_axes(cov: np.ndarray, conf: float = 0.95) -> tuple[float, float]:
    """Major / minor axis lengths of the confidence ellipse."""
    s = chi2.ppf(conf, df=2)
    vals = np.clip(np.linalg.eigvalsh(cov), 0, None)
    vals.sort()
    return float(np.sqrt(vals[-1] * s)), float(np.sqrt(vals[0] * s))
