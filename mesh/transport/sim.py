"""In-process simulated mesh radio (no USB hardware required)."""

from __future__ import annotations

import json
import random
import threading
from pathlib import Path
from typing import Callable

DEFAULT_TOPOLOGY = Path(__file__).resolve().parents[1] / "topology.json"

Receiver = Callable[[bytes, str], None]


class SimTransport:
    """Shared bus: nodes register handlers; send respects topology + loss."""

    _instances: dict[str, SimTransport] = {}
    _lock = threading.RLock()

    def __init__(
        self,
        node_id: str,
        *,
        topology_path: Path | None = None,
        hub: str = "default",
    ) -> None:
        self.node_id = node_id
        self.hub = hub
        self._receiver: Receiver | None = None
        self._seq = 0
        self._all_nodes, self._loss = self._load_topology(topology_path or DEFAULT_TOPOLOGY)

    @classmethod
    def get(cls, node_id: str, **kwargs) -> SimTransport:
        hub = kwargs.pop("hub", "default")
        key = f"{hub}:{node_id}"
        with cls._lock:
            if key not in cls._instances:
                cls._instances[key] = SimTransport(node_id, hub=hub, **kwargs)
            return cls._instances[key]

    @classmethod
    def reset_hub(cls, hub: str = "default") -> None:
        with cls._lock:
            cls._instances = {k: v for k, v in cls._instances.items() if not k.startswith(f"{hub}:")}

    def _load_topology(self, path: Path) -> tuple[set[str], dict[tuple[str, str], float]]:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            nodes = set(data.get("nodes", []))
            loss: dict[tuple[str, str], float] = {}
            for link in data.get("links", []):
                a, b = link["a"], link["b"]
                p = float(link.get("loss", 0.0))
                loss[(a, b)] = p
                loss[(b, a)] = p
            if nodes and loss:
                return nodes, loss
        return self._default_topology()

    @staticmethod
    def _default_topology() -> tuple[set[str], dict[tuple[str, str], float]]:
        nodes = {"drone_1", "drone_2", "drone_3", "operator"}
        loss = {
            ("drone_1", "drone_2"): 0.05,
            ("drone_2", "drone_3"): 0.05,
            ("drone_1", "drone_3"): 0.08,
            ("drone_1", "operator"): 0.02,
            ("drone_2", "operator"): 0.02,
            ("drone_3", "operator"): 0.02,
        }
        return nodes, loss

    def set_receiver(self, fn: Receiver | None) -> None:
        self._receiver = fn

    def neighbours(self) -> list[str]:
        out: list[str] = []
        for (a, b) in self._loss:
            if a == self.node_id and b not in out:
                out.append(b)
            elif b == self.node_id and a not in out:
                out.append(a)
        return sorted(out)

    def send(self, frame: bytes, *, broadcast: bool = True) -> int:
        self._seq += 1
        delivered = 0
        targets = set(self.neighbours()) if broadcast else set(self._all_nodes)
        with self._lock:
            for key, transport in list(self._instances.items()):
                if not key.startswith(f"{self.hub}:"):
                    continue
                dst = transport.node_id
                if dst == self.node_id:
                    continue
                if broadcast and dst not in targets:
                    continue
                p_loss = self._loss.get((self.node_id, dst), 0.0)
                if random.random() < p_loss:
                    continue
                if transport._receiver:
                    transport._receiver(frame, self.node_id)
                    delivered += 1
        return delivered
