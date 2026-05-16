"""Triangulation package — TDOA acoustic source localisation.

Consumes the per-drone detection JSON produced by ``detection/`` and
writes a sibling ``localizations.json`` containing source coordinates,
a Monte-Carlo confidence cloud, and CEP statistics. Designed to slot
into the production data pipeline; a standalone Dash viewer is provided
for sanity-checking the output on a real map.

Public entry points:

    python -m triangulation.locate \\
        --in  detection/output/events.json \\
        --out detection/output/localizations.json

    python -m triangulation.viewer detection/output/localizations.json
"""

__all__ = ["locate", "policy", "viewer"]
