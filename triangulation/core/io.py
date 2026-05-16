"""Nanosecond-safe time conversion.

The upstream detector reports absolute ns timestamps near 1.78e18.
float64 keeps ~16 significant digits — that value needs ~19 — so a
naive ``/1e9`` quantises to ~0.4 µs and pollutes any timing-sensitive
math. Subtracting a common integer reference in ns FIRST (exact in
Python int) preserves sub-microsecond precision when converting to
seconds. TDOA only ever needs *relative* time, so nothing is lost.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np


def relative_times(events: Iterable[dict],
                   ts_field: str = "event_time_ns") -> np.ndarray:
    """Per-event arrival time in seconds, referenced to the earliest event.

    Parameters
    ----------
    events
        Iterable of detection records with an integer-ns timestamp field.
    ts_field
        Which JSON field carries the per-drone time of arrival.
        Default ``"event_time_ns"`` matches the detection schema where
        ``event_time_ns = timestamp_ns + toa_offset_ns``.
    """
    ts = [int(e[ts_field]) for e in events]
    t0 = min(ts)
    return np.array([(t - t0) / 1e9 for t in ts])
