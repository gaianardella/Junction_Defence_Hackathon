"""Compare naive JSON vs compact mesh payloads (for jury demo)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .frame import frame_wire_size
from .payload import (
    LOC_SUMMARY_SIZE,
    TACTICAL_EVENT_SIZE,
    compare_row_bandwidth,
    event_row_to_tactical,
    pack_loc_summary,
)


def bench_events(path: Path) -> None:
    rows = json.loads(path.read_text(encoding="utf-8"))
    relevant = [r for r in rows if r.get("relevant")]
    json_bytes = sum(compare_row_bandwidth(r)["json_bytes"] for r in relevant)
    mesh_payload = len(relevant) * TACTICAL_EVENT_SIZE
    mesh_wire = sum(frame_wire_size(TACTICAL_EVENT_SIZE) for _ in relevant)

    print("=== Detection events (relevant rows only) ===")
    print(f"  Rows:              {len(relevant)}")
    print(f"  Naive JSON total:  {json_bytes} B  (~{json_bytes // max(len(relevant),1)} B/row)")
    print(f"  Mesh payload only: {mesh_payload} B  ({TACTICAL_EVENT_SIZE} B/row)")
    print(f"  Mesh on-wire:      {mesh_wire} B  (incl. header+HMAC)")
    print(f"  Savings vs JSON:   {json_bytes - mesh_wire} B ({100*(json_bytes-mesh_wire)/max(json_bytes,1):.0f}%)")
    if relevant:
        r0 = relevant[0]
        pkt = event_row_to_tactical(r0)
        print(f"\n  Example row '{Path(r0.get('path','')).name}':")
        print(f"    JSON: {compare_row_bandwidth(r0)['json_bytes']} B")
        print(f"    Mesh: {len(pkt)} B payload + {frame_wire_size(len(pkt)) - len(pkt)} B frame overhead")


def bench_localizations(path: Path) -> None:
    entries = json.loads(path.read_text(encoding="utf-8"))
    json_bytes = sum(len(json.dumps(e, separators=(",", ":")).encode()) for e in entries)
    mesh_payload = len(entries) * LOC_SUMMARY_SIZE
    mesh_wire = sum(frame_wire_size(LOC_SUMMARY_SIZE) for _ in entries)

    print("\n=== Localizations (full file vs mesh summary) ===")
    print(f"  Scenarios:         {len(entries)}")
    print(f"  Full JSON file:    {path.stat().st_size} B on disk")
    print(f"  Per-entry JSON:    {json_bytes} B serialized")
    print(f"  Mesh summary only: {mesh_payload} B  ({LOC_SUMMARY_SIZE} B/scenario)")
    print(f"  Mesh on-wire:      {mesh_wire} B")
    print(f"  Savings vs JSON:   {json_bytes - mesh_wire} B ({100*(json_bytes-mesh_wire)/max(json_bytes,1):.0f}%)")
    if entries:
        p = pack_loc_summary(entries[0])
        print(f"\n  Example '{entries[0].get('scenario')}': mesh {len(p)}B vs JSON entry ~"
              f"{len(json.dumps(entries[0], separators=(',',':')).encode())}B")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Bandwidth benchmark: JSON vs mesh")
    p.add_argument("--events", type=Path, default=Path("detection/output/events.json"))
    p.add_argument("--localizations", type=Path, default=Path("detection/output/localizations.json"))
    args = p.parse_args(argv)

    if args.events.is_file():
        bench_events(args.events)
    else:
        print(f"Skip events: {args.events} not found")

    if args.localizations.is_file():
        bench_localizations(args.localizations)
    else:
        print(f"Skip localizations: {args.localizations} not found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
