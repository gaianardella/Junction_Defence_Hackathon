"""Publish detection / localization results onto the mesh (compact binary only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .frame import frame_wire_size
from .metrics import get_metrics, reset_metrics
from .node import MeshNode
from .payload import (
    LOC_SUMMARY_SIZE,
    TACTICAL_EVENT_SIZE,
    event_row_to_tactical,
    json_row_wire_size,
    pack_loc_summary,
)
def publish_events_file(
    path: Path,
    *,
    hub: str = "default",
    transport: str = "sim",
    verbose: bool = True,
) -> dict:
    """Send only relevant detection rows as 32-byte tactical payloads (+ frame header)."""
    reset_metrics()
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("events file must be a JSON array")

    sent = 0
    skipped = 0
    json_total = 0
    mesh_total = 0

    for row in rows:
        if not row.get("relevant"):
            skipped += 1
            continue
        payload = event_row_to_tactical(row)
        if payload is None:
            skipped += 1
            continue
        drone_id = row.get("drone_id", "drone_1")
        node = MeshNode(
            drone_id, role="relay", hub=hub, transport=transport, udp_listen=False,
        )
        jb = json_row_wire_size(row)
        json_total += jb
        wire = frame_wire_size(len(payload))
        mesh_total += wire
        node.publish_payload(payload, kind="tactical", json_equiv=jb - wire)
        sent += 1
        if verbose:
            print(
                f"  mesh {drone_id}: tactical {len(payload)}B "
                f"(JSON row {jb}B → wire {wire}B, saved {jb - wire}B)",
                flush=True,
            )

    m = get_metrics().summary()
    if verbose:
        print(f"\nPublished {sent} tactical events, skipped {skipped} non-relevant rows.")
        print(f"  JSON total (if sent naively): {json_total} B")
        print(f"  Mesh wire total:             {mesh_total} B")
        print(f"  Savings:                     {json_total - mesh_total} B ({100*(json_total-mesh_total)/max(json_total,1):.0f}%)")
    return {"sent": sent, "skipped": skipped, "json_total": json_total, "mesh_total": mesh_total, **m}


def publish_localizations_file(
    path: Path,
    *,
    hub: str = "default",
    transport: str = "sim",
    verbose: bool = True,
) -> dict:
    """Send 24-byte loc summaries — never the full cloud_latlon JSON."""
    reset_metrics()
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("localizations file must be a JSON array")

    sent = 0
    json_total = 0
    mesh_total = 0

    for entry in entries:
        payload = pack_loc_summary(entry)
        full_json = len(json.dumps(entry, separators=(",", ":")).encode())
        json_total += full_json
        wire = frame_wire_size(len(payload))
        mesh_total += wire
        node = MeshNode(
            "drone_1", role="relay", hub=hub, transport=transport, udp_listen=False,
        )
        node.publish_payload(payload, kind="loc_summary", json_equiv=full_json - wire)
        sent += 1
        if verbose:
            print(
                f"  mesh: loc_summary {len(payload)}B for {entry.get('scenario')} "
                f"(full JSON {full_json}B → wire {wire}B)"
            )

    m = get_metrics().summary()
    if verbose:
        print(f"\nPublished {sent} localization summaries (not full clouds).")
        print(f"  Full JSON total: {json_total} B")
        print(f"  Mesh wire total: {mesh_total} B")
        print(f"  Savings:         {json_total - mesh_total} B ({100*(json_total-mesh_total)/max(json_total,1):.0f}%)")
    return {"sent": sent, "json_total": json_total, "mesh_total": mesh_total, **m}


def _cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Publish pipeline JSON onto tactical mesh")
    p.add_argument("--events", type=Path, help="detection/output/events.json")
    p.add_argument("--localizations", type=Path, help="detection/output/localizations.json")
    p.add_argument("--hub", default="default")
    p.add_argument(
        "--transport",
        default="sim",
        choices=("sim", "udp"),
        help="use udp when operator runs in another terminal",
    )
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    if not args.events and not args.localizations:
        p.error("pass --events and/or --localizations")

    if args.events:
        publish_events_file(
            args.events, hub=args.hub, transport=args.transport, verbose=not args.quiet,
        )
    if args.localizations:
        publish_localizations_file(
            args.localizations, hub=args.hub, transport=args.transport, verbose=not args.quiet,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
