#!/usr/bin/env bash
# Generate both demo dataset variants (clean + jammed) in one invocation.
# Run from the repo root:
#   bash scripts/generate_demo_datasets.sh

set -euo pipefail

EVENTS="detection/output/events.json"
OUT_CLEAN="detection/output/localizations.json"
OUT_JAMMED="detection/output/localizations_jammed.json"

echo "── Generating clean dataset ────────────────────────────────"
python -m triangulation.locate \
    --in  "$EVENTS" \
    --out "$OUT_CLEAN" \
    --variant-tag clean \
    --pretty

echo ""
echo "── Generating jammed dataset (drone_2 @ 5× position σ) ────"
python -m triangulation.locate \
    --in  "$EVENTS" \
    --out "$OUT_JAMMED" \
    --jam-drone drone_2 \
    --jam-position-mult 5.0 \
    --jam-time-mult 1.0 \
    --variant-tag jammed-drone_2 \
    --pretty

echo ""
echo "Done. Files written:"
echo "  $OUT_CLEAN"
echo "  $OUT_JAMMED"
