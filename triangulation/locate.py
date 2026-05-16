"""TDOA localisation pipeline — events.json -> localizations.json.

Reads the detection JSON, groups events by ``path`` (one scenario =
one event from three drones), filters out non-relevant rows, projects
each drone's lat/lon to a local metric plane, runs the TDOA solver,
and runs a Monte-Carlo cloud using the per-drone error fields from
the input JSON. Writes a sibling JSON with the source coordinates +
95% confidence cloud + CEP statistics for each scenario.

Usage
-----
    python -m triangulation.locate \\
        --in  detection/output/events.json \\
        --out detection/output/localizations.json

Optional flags
--------------
    --mc-samples N        MC sample count (default 400)
    --confidence 0.95     ellipse confidence level (default 0.95)
    --cloud-format ellipse|hull|samples
                          how to dump cloud_95 (default 'ellipse')
    --pretty              pretty-print the output JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np

from .core import (C, ellipse_axes, ellipse_xy, localize, mc_confidence)
from .projection import (latlon_to_local, latlon_to_local_array,
                         local_to_latlon, local_to_latlon_array)


# Field name in the input JSON for per-drone position uncertainty. If the
# field is absent on a given event we fall back to zero (timing-only MC).
POSITION_ERROR_FIELD = "position_error_m"

# Field for the per-drone timing uncertainty. The detector currently
# emits both `_us` and `_ms` columns; the user has confirmed `_ms` is
# the canonical one — single source of truth.
TIME_ERROR_FIELD_MS = "time_prediction_error_ms"


# ---------------------------------------------------------------- grouping
def _group_by_scenario(events: list[dict]) -> dict[str, list[dict]]:
    """Group raw detections by scenario path. Preserves drone order."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        groups[e.get("path", "<unknown>")].append(e)
    return dict(groups)


def _localizable(group: list[dict]) -> tuple[bool, str]:
    """Decide whether a group has enough info for a TDOA fix."""
    if not group:
        return False, "empty group"
    if not all(bool(e.get("relevant")) for e in group):
        return False, "non-relevant rows present"
    drone_ids = {e["drone_id"] for e in group}
    if len(drone_ids) < 3:
        return False, f"only {len(drone_ids)} distinct drone(s); need 3+"
    if any("event_time_ns" not in e or "position" not in e for e in group):
        return False, "missing event_time_ns or position field"
    return True, "ok"


# ------------------------------------------------------------ per-scenario
def _per_drone_sigmas(group: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Pull σ_t (seconds) and σ_pos (metres) per detection from the JSON.

    σ_t comes from ``time_prediction_error_ms`` divided by 1000.
    σ_pos comes from ``position_error_m`` (or 0 if absent).
    """
    sigma_t_s = np.array([float(e.get(TIME_ERROR_FIELD_MS, 0.0)) / 1000.0
                          for e in group])
    sigma_p_m = np.array([float(e.get(POSITION_ERROR_FIELD, 0.0))
                          for e in group])
    return sigma_t_s, sigma_p_m


def _bearing_deg(estimate_xy: np.ndarray,
                 ref_xy: np.ndarray) -> tuple[float, float]:
    """Bearing (degrees from N) and slant distance (m) from `ref` to estimate."""
    dx, dy = float(estimate_xy[0] - ref_xy[0]), float(estimate_xy[1] - ref_xy[1])
    bearing = float(np.degrees(np.arctan2(dx, dy)) % 360.0)
    distance = float(np.hypot(dx, dy))
    return bearing, distance


def _confidence_score(cep50_m: float, scale_m: float = 25.0) -> float:
    """Map CEP50 -> [0, 1]. 25 m maps to ~0.5; sub-metre maps to ~1."""
    return float(1.0 / (1.0 + cep50_m / scale_m))


def _cloud_as(cloud_xy: np.ndarray, ellipse_polygon_xy: np.ndarray,
              fmt: str) -> np.ndarray:
    """Pick the cloud representation requested by --cloud-format."""
    if fmt == "ellipse":
        return ellipse_polygon_xy
    if fmt == "hull":
        try:
            from scipy.spatial import ConvexHull
            hull = ConvexHull(cloud_xy)
            return cloud_xy[hull.vertices]
        except Exception:
            return ellipse_polygon_xy
    if fmt == "samples":
        return cloud_xy
    raise ValueError(f"unknown cloud format: {fmt}")


def localize_scenario(group: list[dict], *,
                       mc_samples: int = 400,
                       confidence: float = 0.95,
                       cloud_format: str = "ellipse",
                       rng: np.random.Generator | None = None) -> dict:
    """Run the full pipeline on one scenario group; return an output dict."""
    rng = rng if rng is not None else np.random.default_rng(7)

    # 1. choose a local projection origin: centroid of the drone positions
    lats = np.array([e["position"]["lat"] for e in group])
    lons = np.array([e["position"]["lon"] for e in group])
    lat0, lon0 = float(lats.mean()), float(lons.mean())

    # 2. project drones to local plane
    xy = latlon_to_local_array(lats, lons, lat0, lon0)
    drone_positions = {e["drone_id"]: tuple(xy[i])
                       for i, e in enumerate(group)}

    # 3. localize (grid + LM)
    estimate_xy, _diag = localize(group, drone_positions,
                                   ts_field="event_time_ns")

    # 4. Monte-Carlo cloud with per-drone σ
    sigma_t_s, sigma_p_m = _per_drone_sigmas(group)
    mc = mc_confidence(group, drone_positions,
                       clock_sigma_s=sigma_t_s,
                       pos_sigma_m=sigma_p_m,
                       n=mc_samples, x0=estimate_xy,
                       ts_field="event_time_ns",
                       rng=rng)

    # 5. ellipse + summary stats
    ellipse_pts_xy = ellipse_xy(mc["mean"], mc["cov"], conf=confidence)
    major, minor = ellipse_axes(mc["cov"], conf=confidence)
    gdop = float(major / max(minor, 1e-9))
    zone_area = float(np.pi * major * minor)
    cep50 = float(mc["cep50"])
    # cep95 ≈ cep50 * 2.08 for a 2-D Rayleigh (good enough as a hint)
    cep95 = cep50 * 2.08

    # 6. project estimate + cloud polygon back to lat/lon
    src_lat, src_lon = local_to_latlon(float(estimate_xy[0]),
                                        float(estimate_xy[1]),
                                        lat0, lon0)
    cloud_xy = _cloud_as(mc["cloud"], ellipse_pts_xy, cloud_format)
    cloud_ll = local_to_latlon_array(cloud_xy, lat0, lon0)

    # 7. handy bearing/distance relative to the first drone (lexical order)
    ids_sorted = sorted({e["drone_id"] for e in group})
    ref_id = ids_sorted[0]
    bearing, distance = _bearing_deg(estimate_xy,
                                      np.asarray(drone_positions[ref_id]))

    return {
        "scenario": Path(group[0].get("path", "")).name,
        "label": group[0].get("label"),
        "label_human": group[0].get("label_human"),
        "event_timestamp_ns": int(group[0].get("timestamp_ns", 0)),
        "drone_ids": ids_sorted,
        "drones_used": [
            {"drone_id": e["drone_id"],
             "lat": float(e["position"]["lat"]),
             "lon": float(e["position"]["lon"]),
             "event_time_ns": int(e["event_time_ns"]),
             "sigma_t_ms": float(e.get(TIME_ERROR_FIELD_MS, 0.0)),
             "sigma_pos_m": float(e.get(POSITION_ERROR_FIELD, 0.0))}
            for e in sorted(group, key=lambda r: r["drone_id"])
        ],
        "source": {
            "lat": src_lat, "lon": src_lon,
            "x_m_local": float(estimate_xy[0]),
            "y_m_local": float(estimate_xy[1]),
            "origin_lat": lat0, "origin_lon": lon0,
        },
        "cep50_m": round(cep50, 3),
        "cep95_m_approx": round(cep95, 3),
        "zone_area_m2": round(zone_area, 3),
        "gdop": round(gdop, 3),
        "localization_confidence": round(_confidence_score(cep50), 3),
        "bearing_from_first_drone_deg": round(bearing, 2),
        "distance_from_first_drone_m": round(distance, 2),
        "cloud_format": cloud_format,
        "cloud_confidence": confidence,
        "cloud_latlon": [{"lat": float(p[0]), "lon": float(p[1])}
                          for p in cloud_ll],
        "cloud_xy_local": [[float(p[0]), float(p[1])] for p in cloud_xy],
        "input_errors": {
            "time_ms_max": float(np.max(sigma_t_s) * 1000.0),
            "position_m_max": float(np.max(sigma_p_m)),
            "time_s_per_drone": [float(x) for x in sigma_t_s],
            "position_m_per_drone": [float(x) for x in sigma_p_m],
        },
    }


# ----------------------------------------------------------------- driver
def run(events_path: Path, out_path: Path, *,
        mc_samples: int = 400,
        confidence: float = 0.95,
        cloud_format: str = "ellipse",
        pretty: bool = False,
        verbose: bool = True) -> list[dict]:
    """Top-level: read events, localise every relevant scenario, write JSON."""
    with open(events_path) as f:
        events: list[dict] = json.load(f)

    groups = _group_by_scenario(events)
    out: list[dict] = []
    skipped: list[tuple[str, str]] = []
    rng = np.random.default_rng(7)

    for scenario, group in groups.items():
        ok, reason = _localizable(group)
        if not ok:
            skipped.append((scenario, reason))
            continue
        try:
            entry = localize_scenario(
                group, mc_samples=mc_samples,
                confidence=confidence,
                cloud_format=cloud_format,
                rng=rng,
            )
        except Exception as exc:  # pragma: no cover (defensive)
            skipped.append((scenario, f"error: {exc}"))
            continue
        out.append(entry)
        if verbose:
            print(f"  ✓ {entry['scenario']:40s} "
                  f"({entry['label']:<14s}) "
                  f"CEP50={entry['cep50_m']:6.2f}m "
                  f"zone={entry['zone_area_m2']:7.1f}m² "
                  f"gdop={entry['gdop']:5.2f}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2 if pretty else None)

    if verbose:
        print(f"\n  Wrote {len(out)} localisations → {out_path}")
        if skipped:
            print(f"  Skipped {len(skipped)} scenarios:")
            for s, r in skipped:
                print(f"    · {s}: {r}")
    return out


def _cli(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m triangulation.locate",
        description="Run TDOA localisation over a detection events.json.",
    )
    p.add_argument("--in", dest="inp",
                   default="detection/output/events.json",
                   help="input events.json path")
    p.add_argument("--out", dest="out",
                   default="detection/output/localizations.json",
                   help="output localizations.json path")
    p.add_argument("--mc-samples", type=int, default=400)
    p.add_argument("--confidence", type=float, default=0.95)
    p.add_argument("--cloud-format",
                   choices=("ellipse", "hull", "samples"),
                   default="ellipse")
    p.add_argument("--pretty", action="store_true")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    run(Path(args.inp), Path(args.out),
        mc_samples=args.mc_samples,
        confidence=args.confidence,
        cloud_format=args.cloud_format,
        pretty=args.pretty,
        verbose=not args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
