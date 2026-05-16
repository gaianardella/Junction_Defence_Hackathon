"""Bandwidth accounting for mesh demos."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MeshMetrics:
    bytes_sent: int = 0
    bytes_received: int = 0
    frames_sent: int = 0
    frames_received: int = 0
    tactical_sent: int = 0
    loc_summary_sent: int = 0
    json_equivalent_saved: int = 0
    dropped_hmac: int = 0
    dropped_replay: int = 0

    def record_send(self, wire_len: int, payload_kind: str | None = None, json_equiv: int = 0) -> None:
        self.bytes_sent += wire_len
        self.frames_sent += 1
        if payload_kind == "tactical":
            self.tactical_sent += 1
        elif payload_kind == "loc_summary":
            self.loc_summary_sent += 1
        self.json_equivalent_saved += json_equiv

    def record_recv(self, wire_len: int) -> None:
        self.bytes_received += wire_len
        self.frames_received += 1

    def summary(self) -> dict:
        useful = self.tactical_sent * 32 + self.loc_summary_sent * 24
        return {
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "frames_sent": self.frames_sent,
            "frames_received": self.frames_received,
            "tactical_messages": self.tactical_sent,
            "loc_summary_messages": self.loc_summary_sent,
            "payload_bytes_useful_estimate": useful,
            "json_equivalent_saved_bytes": self.json_equivalent_saved,
            "overhead_bytes": max(0, self.bytes_sent - useful),
        }


_metrics = MeshMetrics()


def get_metrics() -> MeshMetrics:
    return _metrics


def reset_metrics() -> MeshMetrics:
    global _metrics
    _metrics = MeshMetrics()
    return _metrics
