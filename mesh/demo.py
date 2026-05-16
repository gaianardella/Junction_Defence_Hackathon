"""One-shot demo: start operator + drones in-process, publish pipeline output."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from .node import MeshNode
from .publish import publish_events_file, publish_localizations_file
from .transport.sim import SimTransport


def run_demo(
    events: Path | None,
    localizations: Path | None,
    *,
    hub: str = "default",
    hold_s: float = 0.5,
) -> None:
    SimTransport.reset_hub(hub)
    # Register all nodes before publish (same process = shared sim bus).
    nodes = [
        MeshNode("drone_1", hub=hub),
        MeshNode("drone_2", hub=hub),
        MeshNode("drone_3", hub=hub),
        MeshNode("operator", role="operator", hub=hub),
    ]

    print("=== Tactical mesh demo (simulated radio) ===\n", flush=True)
    time.sleep(0.1)

    if events and events.is_file():
        print("--- Publishing detection events ---", flush=True)
        publish_events_file(events, hub=hub)
        time.sleep(hold_s)

    if localizations and localizations.is_file():
        print("\n--- Publishing localization summaries ---", flush=True)
        publish_localizations_file(localizations, hub=hub)
        time.sleep(hold_s)

    op = nodes[-1]
    print("\n--- Operator metrics ---", flush=True)
    for k, v in op.metrics.summary().items():
        print(f"  {k}: {v}", flush=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run full mesh bandwidth demo in one terminal")
    p.add_argument("--events", type=Path, default=Path("detection/output/events.json"))
    p.add_argument("--localizations", type=Path, default=Path("detection/output/localizations.json"))
    p.add_argument("--hub", default="default")
    args = p.parse_args(argv)
    run_demo(
        args.events if args.events.is_file() else None,
        args.localizations if args.localizations.is_file() else None,
        hub=args.hub,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
