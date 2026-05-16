"""Mesh node: receive, deduplicate, flood-forward, optional operator console."""

from __future__ import annotations

import argparse
import sys
import time
from collections import deque

from .frame import (
    PTYPE_DATA,
    frame_wire_size,
    int_to_node_id,
    node_id_to_int,
    pack_frame,
    unpack_frame,
)
from .metrics import get_metrics
from .payload import (
    LOC_SUMMARY_SIZE,
    LOC_SUMMARY_MAGIC,
    TACTICAL_EVENT_SIZE,
    TACTICAL_MAGIC,
    unpack_loc_summary,
    unpack_tactical_event,
)
from .transport import get_transport


class MeshNode:
  def __init__(
    self,
    node_id: str,
    *,
    role: str = "relay",
    hub: str = "default",
    transport: str = "sim",
    udp_listen: bool | None = None,
  ) -> None:
    self.node_id = node_id
    self.role = role
    if udp_listen is None:
      udp_listen = transport == "udp" and role == "operator"
    self.transport = get_transport(
      node_id, kind=transport, hub=hub, udp_listen=udp_listen,
    )
    self.metrics = get_metrics()
    self._seen: set[tuple[int, int]] = set()
    self._seen_order: deque[tuple[int, int]] = deque(maxlen=4096)
    self._seq = 0
    self.transport.set_receiver(self._on_wire)

  def _remember(self, src: int, seq: int) -> bool:
    key = (src, seq)
    if key in self._seen:
      return False
    self._seen.add(key)
    self._seen_order.append(key)
    if len(self._seen) > 4096:
      old = self._seen_order.popleft()
      self._seen.discard(old)
    return True

  def _on_wire(self, data: bytes, from_node: str) -> None:
    try:
      frame = unpack_frame(data)
    except ValueError as exc:
      self.metrics.dropped_hmac += 1
      if self.role == "operator":
        print(f"[{self.node_id}] drop: {exc}", file=sys.stderr)
      return

    src, seq = frame["src_id"], frame["seq"]
    if not self._remember(src, seq):
      self.metrics.dropped_replay += 1
      return

    self.metrics.record_recv(len(data))
    payload = frame["payload"]
    from_node = int_to_node_id(src)
    self._handle_payload(payload, from_node)

    ttl = frame["ttl"]
    if ttl <= 1:
      return
    rebroadcast = pack_frame(
      payload=payload,
      src_id=src,
      seq=seq,
      ttl=ttl - 1,
      ptype=frame["ptype"],
    )
    self.transport.send(rebroadcast, broadcast=True)

  def _handle_payload(self, payload: bytes, from_node: str) -> None:
    if len(payload) < 2:
      return
    magic = int.from_bytes(payload[:2], "little")
    if magic == TACTICAL_MAGIC and len(payload) == TACTICAL_EVENT_SIZE:
      ev = unpack_tactical_event(payload)
      if self.role == "operator":
        print(
          f"[operator] TACTICAL from {from_node}: "
          f"{ev.get('label')} @ ({ev['lat']:.5f}, {ev['lon']:.5f}) "
          f"conf={ev['confidence']:.0%}",
          flush=True,
        )
    elif magic == LOC_SUMMARY_MAGIC and len(payload) == LOC_SUMMARY_SIZE:
      loc = unpack_loc_summary(payload)
      if self.role == "operator":
        print(
          f"[operator] LOC_SUMMARY from {from_node}: "
          f"{loc.get('label')} @ ({loc['lat']:.5f}, {loc['lon']:.5f}) "
          f"CEP50≈{loc['cep50_m']:.1f}m",
          flush=True,
        )

  def publish_payload(self, payload: bytes, *, kind: str, json_equiv: int = 0) -> int:
    self._seq += 1
    src = node_id_to_int(self.node_id)
    self._remember(src, self._seq)
    wire = pack_frame(
      payload=payload,
      src_id=src,
      seq=self._seq,
      ptype=PTYPE_DATA,
    )
    self.metrics.record_send(len(wire), payload_kind=kind, json_equiv=json_equiv)
    return self.transport.send(wire, broadcast=True)


def run_node(argv: list[str] | None = None) -> int:
  p = argparse.ArgumentParser(description="Tactical mesh node (simulated radio)")
  p.add_argument("--id", required=True, help="drone_1 | drone_2 | drone_3 | operator")
  p.add_argument("--role", default="relay", choices=("relay", "operator"))
  p.add_argument("--hub", default="default")
  p.add_argument(
    "--transport",
    default="sim",
    choices=("sim", "udp"),
    help="sim = same terminal only; udp = multi-terminal on this machine (port 19987)",
  )
  args = p.parse_args(argv)

  role = args.role
  if args.id == "operator":
    role = "operator"

  mode = "UDP localhost" if args.transport == "udp" else "in-process sim"
  print(f"Starting mesh node {args.id} ({role}) transport={args.transport} …", flush=True)
  node = MeshNode(
    args.id, role=role, hub=args.hub, transport=args.transport,
    udp_listen=(args.transport == "udp"),
  )
  print(
    f"Mesh node {args.id} ({role}) listening [{mode}] — "
    f"neighbours: {node.transport.neighbours()}",
    flush=True,
  )
  if args.transport == "udp":
    print("Waiting for packets on 127.0.0.1:19987 (run publish in another terminal).", flush=True)
  try:
    while True:
      time.sleep(1)
  except KeyboardInterrupt:
    s = node.metrics.summary()
    print("\n--- mesh metrics ---")
    for k, v in s.items():
      print(f"  {k}: {v}")
  return 0


if __name__ == "__main__":
  raise SystemExit(run_node())
