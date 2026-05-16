"""Sandbox event builder — synthesises TDOA events from a geometry config.

Used by the Flask sandbox endpoint (POST /api/sandbox) so the browser
free-play tab can send dragged drone + source positions and get back a
live localization result without needing real audio files.
"""

from __future__ import annotations

import math

import numpy as np

SPEED_OF_SOUND_M_S: float = 343.0
DEG_LAT_M: float = 111_111.0

# Shared reference time (ns) — only relative deltas matter for TDOA.
_BASE_TS_NS: int = 1_778_935_184_893_934_848

_LABEL_HUMAN: dict[str, str] = {
    "gunshot": "Gunfire",
    "missile_launch": "Missile launch",
    "tank": "Tank engine",
    "drone": "UAV",
}


def build_events(
    drones: list[dict],
    source: dict,
    sigma_t_ms: float = 1.0,
    sigma_pos_m: float = 5.0,
    label: str = "gunshot",
    rng: np.random.Generator | None = None,
) -> list[dict]:
    """Return synthetic per-drone rows compatible with ``localize_scenario()``."""
    if rng is None:
        rng = np.random.default_rng()

    src_lat = float(source["lat"])
    src_lon = float(source["lon"])
    deg_lon_m = DEG_LAT_M * math.cos(math.radians(src_lat))
    label_str = str(label)
    label_human = _LABEL_HUMAN.get(label_str, label_str.replace("_", " ").title())

    events: list[dict] = []
    for d in drones:
        d_lat = float(d["lat"])
        d_lon = float(d["lon"])

        dlat_m = (d_lat - src_lat) * DEG_LAT_M
        dlon_m = (d_lon - src_lon) * deg_lon_m
        dist_m = math.hypot(dlat_m, dlon_m)

        true_t_s = dist_m / SPEED_OF_SOUND_M_S
        sigma_t_s = float(sigma_t_ms) / 1000.0
        noisy_t_s = true_t_s + float(rng.normal(0.0, sigma_t_s))
        event_time_ns = _BASE_TS_NS + int(round(noisy_t_s * 1e9))

        events.append({
            "path": "sandbox_scenario.wav",
            "drone_id": str(d["drone_id"]),
            "label": label_str,
            "label_human": label_human,
            "relevant": True,
            "timestamp_ns": _BASE_TS_NS,
            "confidence": 0.95,
            "position": {"lat": d_lat, "lon": d_lon, "alt_m": 42.0},
            "event_time_ns": event_time_ns,
            "toa_offset_ns": 0,
            "time_prediction_error_ms": float(sigma_t_ms),
            "position_error_m": float(sigma_pos_m),
        })

    return events
