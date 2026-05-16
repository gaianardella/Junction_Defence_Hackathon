"""Compact on-wire payloads (bandwidth-efficient application data)."""

from __future__ import annotations

import hashlib
import json
import struct
from typing import Any

TACTICAL_MAGIC = 0xE001
LOC_SUMMARY_MAGIC = 0xE002
PAYLOAD_VERSION = 1

LABEL_TO_CODE = {
    "gunshot": 1,
    "missile_launch": 2,
    "tank": 3,
    "drone": 4,
}
CODE_TO_LABEL = {v: k for k, v in LABEL_TO_CODE.items()}

TACTICAL_EVENT_FMT = "<HBBBBBQii7x"  # 32 bytes (7-byte pad)
TACTICAL_EVENT_SIZE = struct.calcsize(TACTICAL_EVENT_FMT)

LOC_SUMMARY_FMT = "<HBBHIiiH4x"  # 24 bytes (4-byte pad)
LOC_SUMMARY_SIZE = struct.calcsize(LOC_SUMMARY_FMT)

E7 = 10_000_000


def _lat_e7(lat: float) -> int:
    return int(round(lat * E7))


def _lon_e7(lon: float) -> int:
    return int(round(lon * E7))


def _from_e7(v: int) -> float:
    return v / E7


def scenario_event_id(scenario: str) -> int:
    """Stable 32-bit id from scenario filename."""
    h = hashlib.sha256(scenario.encode()).digest()
    return int.from_bytes(h[:4], "little")


def pack_tactical_event(
    *,
    label: str | None,
    drone_id: str,
    event_time_ns: int,
    lat: float,
    lon: float,
    confidence: float = 0.0,
) -> bytes:
    code = LABEL_TO_CODE.get(label or "", 0)
    drone_num = 0
    if drone_id.startswith("drone_"):
        try:
            drone_num = int(drone_id.split("_", 1)[1])
        except ValueError:
            drone_num = 0
    conf = max(0, min(100, int(round(confidence * 100 if confidence <= 1 else confidence))))
    return struct.pack(
        TACTICAL_EVENT_FMT,
        TACTICAL_MAGIC,
        PAYLOAD_VERSION,
        code,
        drone_num & 0xFF,
        conf,
        0,
        int(event_time_ns),
        _lat_e7(lat),
        _lon_e7(lon),
    )


def unpack_tactical_event(data: bytes) -> dict[str, Any]:
    if len(data) != TACTICAL_EVENT_SIZE:
        raise ValueError(f"tactical event must be {TACTICAL_EVENT_SIZE} bytes, got {len(data)}")
    magic, ver, code, drone_num, conf, _pad, t_ns, lat_e7, lon_e7 = struct.unpack(
        TACTICAL_EVENT_FMT, data
    )
    if magic != TACTICAL_MAGIC:
        raise ValueError(f"bad tactical magic {magic:#x}")
    return {
        "label": CODE_TO_LABEL.get(code),
        "drone_id": f"drone_{drone_num}" if drone_num else "drone_0",
        "event_time_ns": t_ns,
        "lat": _from_e7(lat_e7),
        "lon": _from_e7(lon_e7),
        "confidence": conf / 100.0,
        "version": ver,
    }


def pack_loc_summary(entry: dict) -> bytes:
    src = entry["source"]
    scenario = entry.get("scenario", "")
    label = entry.get("label") or ""
    cep_dm = int(round(float(entry.get("cep50_m", 0)) * 10))
    return struct.pack(
        LOC_SUMMARY_FMT,
        LOC_SUMMARY_MAGIC,
        PAYLOAD_VERSION,
        LABEL_TO_CODE.get(label, 0),
        0,
        scenario_event_id(scenario),
        _lat_e7(float(src["lat"])),
        _lon_e7(float(src["lon"])),
        max(0, min(65535, cep_dm)),
    )


def unpack_loc_summary(data: bytes) -> dict[str, Any]:
    if len(data) != LOC_SUMMARY_SIZE:
        raise ValueError(f"loc summary must be {LOC_SUMMARY_SIZE} bytes, got {len(data)}")
    magic, ver, code, _pad, eid, lat_e7, lon_e7, cep_dm = struct.unpack(
        LOC_SUMMARY_FMT, data
    )
    if magic != LOC_SUMMARY_MAGIC:
        raise ValueError(f"bad loc magic {magic:#x}")
    return {
        "event_id": eid,
        "label": CODE_TO_LABEL.get(code),
        "lat": _from_e7(lat_e7),
        "lon": _from_e7(lon_e7),
        "cep50_m": cep_dm / 10.0,
        "version": ver,
    }


def event_row_to_tactical(row: dict) -> bytes | None:
    if not row.get("relevant"):
        return None
    pos = row.get("position") or {}
    return pack_tactical_event(
        label=row.get("label"),
        drone_id=row.get("drone_id", "drone_1"),
        event_time_ns=int(row.get("event_time_ns", row.get("timestamp_ns", 0))),
        lat=float(pos.get("lat", 0)),
        lon=float(pos.get("lon", 0)),
        confidence=float(row.get("confidence", 0)),
    )


def json_row_wire_size(row: dict) -> int:
    """Bytes if we naively sent the full detection JSON row."""
    return len(json.dumps(row, separators=(",", ":")).encode())


def compare_row_bandwidth(row: dict) -> dict[str, int | bool]:
    pkt = event_row_to_tactical(row)
    return {
        "relevant": bool(row.get("relevant")),
        "json_bytes": json_row_wire_size(row),
        "mesh_bytes": len(pkt) if pkt else 0,
        "saved_bytes": json_row_wire_size(row) - (len(pkt) if pkt else 0),
    }
