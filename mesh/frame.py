"""Mesh frame wrapper (header + payload + optional HMAC)."""

from __future__ import annotations

import hashlib
import hmac
import os
import struct
from typing import Any

FRAME_MAGIC = 0x4D455348  # "MESH"
FRAME_VERSION = 1
HEADER_FMT = "<IBBBBIIB"  # magic, ver, ptype, src, ttl, seq, dst, plen
HEADER_SIZE = struct.calcsize(HEADER_FMT)
HMAC_SIZE = 16

PTYPE_DATA = 1
PTYPE_HELLO = 2

PRIORITY_HIGH = 1
PRIORITY_BULK = 2

PSK_ENV = "MESH_PSK"


def _psk() -> bytes:
    key = os.environ.get(PSK_ENV, "junction-defence-hackathon-demo").encode()
    return key


def pack_frame(
    *,
    payload: bytes,
    src_id: int,
    seq: int,
    ptype: int = PTYPE_DATA,
    ttl: int = 4,
    dst: int = 0,
    sign: bool = True,
) -> bytes:
    header = struct.pack(
        HEADER_FMT,
        FRAME_MAGIC,
        FRAME_VERSION,
        ptype,
        src_id & 0xFF,
        ttl & 0xFF,
        seq & 0xFFFFFFFF,
        dst & 0xFFFFFFFF,
        len(payload) & 0xFFFF,
    )
    body = header + payload
    if sign:
        tag = hmac.new(_psk(), body, hashlib.sha256).digest()[:HMAC_SIZE]
        return body + tag
    return body + (b"\x00" * HMAC_SIZE)


def unpack_frame(data: bytes, *, verify: bool = True) -> dict[str, Any]:
    if len(data) < HEADER_SIZE + HMAC_SIZE:
        raise ValueError("frame too short")
    body, tag = data[: -HMAC_SIZE], data[-HMAC_SIZE:]
    if verify:
        expected = hmac.new(_psk(), body, hashlib.sha256).digest()[:HMAC_SIZE]
        if not hmac.compare_digest(tag, expected):
            raise ValueError("HMAC verification failed")
    magic, ver, ptype, src, ttl, seq, dst, plen = struct.unpack(HEADER_FMT, body[:HEADER_SIZE])
    if magic != FRAME_MAGIC:
        raise ValueError(f"bad frame magic {magic:#x}")
    payload = body[HEADER_SIZE : HEADER_SIZE + plen]
    return {
        "version": ver,
        "ptype": ptype,
        "src_id": src,
        "ttl": ttl,
        "seq": seq,
        "dst": dst,
        "payload": payload,
    }


def frame_wire_size(payload_len: int) -> int:
    return HEADER_SIZE + payload_len + HMAC_SIZE


def node_id_to_int(node_id: str) -> int:
    if node_id.startswith("drone_"):
        try:
            return int(node_id.split("_", 1)[1])
        except ValueError:
            return 0
    if node_id == "operator":
        return 255
    return 0


def int_to_node_id(n: int) -> str:
    if n == 255:
        return "operator"
    return f"drone_{n}"
