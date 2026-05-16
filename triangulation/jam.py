"""GPS-jamming simulation for demo dataset generation.

Scales the error fields of a target drone in the events list to simulate
degraded positioning under jamming. The math still runs — a jammed fix
is a *low-confidence* fix, not a failed one. The ROE engine picks up the
larger CEP50 and may flip the recommendation from STRIKE → RECON or HOLD.

Usage (library)
---------------
    from triangulation.jam import apply_jamming

    jammed_events = apply_jamming(
        events,
        target_drone_id="drone_2",
        pos_mult=5.0,
        time_mult=1.0,
        jam_label="gps_jammed",
    )

Usage (CLI) — see locate.py --jam-* flags.

Design notes
------------
- Does NOT mutate the input list; returns a new list with copied dicts.
- Jam ONE drone at a time. Multi-drone jamming is future work.
- ``time_mult`` defaults to 1.0 (GPS jamming corrupts position, not clock sync).
"""

from __future__ import annotations

from typing import Sequence


def apply_jamming(
    events: Sequence[dict],
    target_drone_id: str,
    *,
    pos_mult: float = 5.0,
    time_mult: float = 1.0,
    jam_label: str = "gps_jammed",
) -> list[dict]:
    """Return a new event list with ``target_drone_id``'s error fields scaled.

    Parameters
    ----------
    events:
        Flat list of per-drone detection dicts (the ``events.json`` payload).
    target_drone_id:
        The drone whose ``position_error_m`` and ``time_prediction_error_ms``
        will be scaled.
    pos_mult:
        Multiplier applied to ``position_error_m`` for the target drone.
    time_mult:
        Multiplier applied to ``time_prediction_error_ms`` for the target drone.
        Typically 1.0 — GPS jamming primarily corrupts position.
    jam_label:
        String written into ``jam_status`` for the target drone row; clean
        drones get ``"clean"``.
    """
    out: list[dict] = []
    for event in events:
        row = dict(event)
        if row.get("drone_id") == target_drone_id:
            row["position_error_m"] = float(row.get("position_error_m", 0.0)) * pos_mult
            row["time_prediction_error_ms"] = (
                float(row.get("time_prediction_error_ms", 0.0)) * time_mult
            )
            row["jam_status"] = jam_label
        else:
            row["jam_status"] = "clean"
        out.append(row)
    return out
