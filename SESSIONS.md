# Implementation Sessions — Defense Hackathon

Architectural plan for upgrading the existing detection → triangulation
demo into a full *detect → decide → respond* operational story. Each
session below is a self-contained chunk of work for a focused Sonnet
implementation pass. Sessions are ordered by dependency; within a level
they can run in parallel.

## How to use this document

- **Read the "Common architecture" section first** — it sets vocabulary
  and conventions every session relies on.
- **Each session ships its own acceptance criteria.** Don't move on
  until the listed checks pass.
- **`⚠ HUMAN INPUT`** markers flag points where Sonnet should stop and
  ask before implementing — usually a values/thresholds decision, a
  visual style choice, or a class priority list.
- **`💡 NOTE`** markers flag a non-obvious design choice that Sonnet
  should preserve, not "improve away".

## Dependency graph

```
Session 1 (ROE)  ─┬─→  Session 3 (Respond anim) ──→  Session 4 (Recon UI)
                  ├─→  Session 5 (Multi-threat)
Session 2 (Jam)  ─┴─→  Session 5 (Multi-threat)
Session 6 (Mesh narrative)   — independent, anytime
```

Recommended order if implementing sequentially: 1, 2, 3, 4, 5, 6.

---

## Common architecture

### What already exists (don't recreate)

- **`triangulation/locate.py`** runs the pipeline. Reads
  `detection/output/events.json`, writes
  `detection/output/localizations.json`. Each entry has a `source`,
  `cep50_m`, `gdop`, `zone_area_m2`, `localization_confidence`,
  `cloud_latlon`, etc.
- **`triangulation/core/`** is the algorithm layer. Per-drone σ MC is
  already implemented in `uncertainty.mc_confidence`.
- **`ui/index.html`** is the tactical map. Single-file canvas + DOM
  overlay. Has a four-phase playback engine
  (`transit → listen → localize → hold`) defined by `PHASE_ORDER`,
  `PHASE_MS`, `PHASE_LABEL`. `buildFrames(entries)` turns
  `localizations.json` rows into playable frames.
- **`triangulation/viewer.py`** is the engineering Dash viewer. **Do
  not touch it for demo work** — it's for validating the JSON, not
  pitching.

### Conventions

- **Backend writes JSON; frontend reads JSON.** No new IPC. The
  contract `localizations.json` already exists; sessions extend the
  schema by adding fields, never by removing or renaming.
- **All new pipeline fields are additive.** A consumer that ignores the
  new field still works.
- **Phases of the demo timeline are first-class.** Adding a new step
  to the kill chain means adding to `PHASE_ORDER`, `PHASE_MS`,
  `PHASE_LABEL` in `ui/index.html` and a branch in `tickPlayback(dt)`.
  This is the canonical extension point.
- **Animation reads, doesn't compute.** The frontend must not re-derive
  CEP50, confidence, or any policy decision. It reads them from the JSON.
- **One canonical localizations.json.** If we need pre-baked variants
  (clean vs jammed), they live under different filenames in the same
  directory; the UI gets a button to swap. Never two files of the same
  name at different paths.
- **Coordinate system in the UI is normalized 0–1.** The
  `latLonToNorm(lat, lon, bounds)` helper does the conversion; never
  hand-roll it.

### Visual / styling conventions (already established in CSS vars)

| Token | Use |
|---|---|
| `--accent` (`#4fd87a` green) | friendly UAV, OK status, sonar pings |
| `--warn` (`#e8a838` amber) | degraded mode, jamming, low confidence |
| `--hostile` (`#e85c4a` red) | classified hostile, cloud, target pin |
| `--text-dim` (`#6a9a78`) | secondary text, log non-events |

Reuse these. Do not introduce new palette colours unless an entirely
new entity class is added (and even then, prefer to reuse + opacity).

---

## Session 1 — ROE Policy Engine (Backend)

### Goal

Every entry in `localizations.json` carries a `recommended_action` and
the policy that produced it. Adds MGRS grid coords for operator
realism. Pure Python, no UI changes.

### Files touched

- New: `triangulation/policy.py`
- Modified: `triangulation/locate.py` (call `policy.decide`, emit new
  fields)
- Modified: `requirements.txt` if needed (`mgrs` optional, see below)
- Tests: re-run pipeline on existing `events.json`, schema check

### Architecture

```
locate.py::localize_scenario()
        │
        ├── (existing) compute estimate, MC cloud, CEP50, GDOP
        │
        ├── NEW: policy.decide(cep50_m, gdop, label,
        │                       localization_confidence)
        │            → {action, reason, severity, weapons_release_required}
        │
        ├── NEW: mgrs_from_latlon(source.lat, source.lon)
        │            → "35VML123456789" (or None if mgrs not installed)
        │
        └── (existing) write JSON entry, now with three new fields
```

`policy.py` is a pure module — no I/O, no random, just a `decide()`
function. This makes it unit-testable and trivially swappable.

### New JSON fields per entry

```json
{
  "recommended_action": "STRIKE",          // STRIKE | RECON | HOLD
  "recommended_action_reason": "CEP50 4.2m within strike envelope",
  "recommended_action_severity": "high",   // high | medium | low
  "weapons_release_required": true,        // STRIKE always true; RECON false
  "source_mgrs": "35VML123456789"          // null if mgrs missing
}
```

### Tasks

1. **Create `triangulation/policy.py`**
   - Define `Action = Literal["STRIKE", "RECON", "HOLD"]`
   - Define `@dataclass class Decision: action, reason, severity, weapons_release_required`
   - Implement `decide(cep50_m, gdop, label, confidence) -> Decision`
   - Logic skeleton (see thresholds below):
     - `HOLD` if `confidence < HOLD_CONFIDENCE_FLOOR` (truly unusable fix)
     - `STRIKE` if `cep50_m < STRIKE_CEP_MAX` AND `gdop < STRIKE_GDOP_MAX`
       AND `label in STRIKE_ELIGIBLE_LABELS`
     - `RECON` otherwise

2. **Wire into `locate.py`**
   - Import `policy.decide`
   - In `localize_scenario`, after MC, call it and add four fields to
     the output dict
   - Add `_mgrs_or_none(lat, lon)` helper that tries `import mgrs`,
     falls back to `None` gracefully

3. **Update `triangulation/__init__.py`** to export `policy`

4. **Update `AGENTS.md`** schema reference with the four new fields

5. **Regenerate `detection/output/localizations.json`** and verify

### Considerations

- **💡 NOTE: thresholds belong in `policy.py` as module-level
  constants**, not buried in `decide()`. The pitch may need to live-tune
  them.
- **💡 NOTE: `decide()` must remain a pure function.** No randomness, no
  I/O. Unit tests will rely on determinism.
- **💡 NOTE: don't gate on `confidence` alone.** Confidence is derived
  from CEP50, so gating on both is double-counting. Use CEP50 + GDOP +
  label class.
- mgrs library: optional dep. Don't crash if missing.

### ⚠ HUMAN INPUT NEEDED

1. **Threshold values** — Sonnet must ask before hardcoding:
   - `STRIKE_CEP_MAX` (suggested: 10 m)
   - `STRIKE_GDOP_MAX` (suggested: 3.0)
   - `HOLD_CONFIDENCE_FLOOR` (suggested: 0.10)
   - `STRIKE_ELIGIBLE_LABELS` (suggested: `["gunshot", "missile_launch", "tank"]`)
2. **Label severity mapping** — what counts as "high" vs "medium"
   severity? Suggested: `missile_launch / tank` = high; `gunshot` =
   medium; `drone` = low. Confirm.
3. **MGRS precision** — 10 m or 1 m grid square? Suggested: 10 m.

### Acceptance criteria

- `python -m triangulation.locate --pretty` runs without error.
- Every entry has `recommended_action`, `recommended_action_reason`,
  `recommended_action_severity`, `weapons_release_required`.
- `source_mgrs` present (string or null).
- `pytest triangulation/tests/test_policy.py` passes (test the
  threshold edges; create the test file).
- AGENTS.md updated to list new fields.

---

## Session 2 — Jamming Mode Support (Backend)

### Goal

The pipeline can emit a **paired pre-baked dataset** for the same
events: a clean variant and a jammed variant where one drone's
`position_error_m` is amplified. The UI later toggles between them.

### Files touched

- New: `triangulation/jam.py`
- Modified: `triangulation/locate.py` (CLI flags)
- Modified: `detection/output/` (new file: `localizations_jammed.json`)
- Tests: schema and value comparison between clean & jammed outputs

### Architecture

```
CLI: python -m triangulation.locate \
       --in detection/output/events.json \
       --out detection/output/localizations.json
     python -m triangulation.locate \
       --in detection/output/events.json \
       --out detection/output/localizations_jammed.json \
       --jam-drone drone_2 \
       --jam-position-mult 5.0 \
       --jam-time-mult 2.0
```

`triangulation/jam.py` is a tiny module: `apply_jamming(events, target_drone_id,
pos_mult, time_mult, label)` returns a new event list with that drone's
error fields scaled and a `jam_status` field added per row for UI display.

### New JSON fields (per scenario when --jam-* used)

```json
{
  "scenario_variant": "jammed-drone_2",      // null or "clean" when not jammed
  "jam_status_per_drone": {                  // present only in jammed variants
    "drone_1": "clean",
    "drone_2": "gps_jammed",
    "drone_3": "clean"
  }
}
```

### Tasks

1. **Create `triangulation/jam.py`**
   - `apply_jamming(events, target_drone_id, *, pos_mult, time_mult, jam_label)`
   - Walks events; for any row matching `target_drone_id`, multiplies
     its `position_error_m` and `time_prediction_error_ms` by the given
     factors
   - Returns the new event list (does not mutate input)

2. **Add CLI flags to `locate.py`**
   - `--jam-drone <id>` — drone to "jam"
   - `--jam-position-mult <float>` — default 5.0
   - `--jam-time-mult <float>` — default 1.0
   - `--jam-label <str>` — default `"gps_jammed"`

3. **Per-scenario `jam_status_per_drone`** in the output
   - Add to `localize_scenario` signature: `jammed_drone_ids: set[str]`
   - Build the per-drone dict from that set

4. **`scenario_variant` field** on each entry
   - Set from a CLI flag: `--variant-tag <str>` (default null)
   - Lets the UI know it's looking at a "clean" vs "jammed-drone_2" dataset

5. **Convenience script** `scripts/generate_demo_datasets.sh`:
   ```sh
   python -m triangulation.locate --out detection/output/localizations.json --variant-tag clean
   python -m triangulation.locate --out detection/output/localizations_jammed.json \
       --jam-drone drone_2 --jam-position-mult 5.0 --variant-tag jammed-drone_2
   ```

### Considerations

- **💡 NOTE: do not implement "live" jamming as a UI toggle that
  re-runs the pipeline.** Pre-bake the variants and serve them as
  static files. Live re-runs add latency and a Python dependency in
  the browser path.
- **💡 NOTE: jamming amplifies σ but the math still runs.** A jammed
  fix is not a *failed* fix; it's a *low-confidence* fix. The ROE
  engine downstream will pick that up via the larger CEP50.
- **💡 NOTE: jam ONE drone at a time for the demo.** Multi-drone
  jamming is a "future work" remark.

### ⚠ HUMAN INPUT NEEDED

1. **Which drone to jam in the demo?** Suggested: `drone_2` (middle of
   the formation, has biggest TDOA impact). Confirm.
2. **Jamming factor** — 5× position σ feels right. Confirm — or pick a
   value that makes CEP50 cross the STRIKE threshold cleanly (i.e.
   demonstrates the policy switch).
3. **Should the time error also be amplified?** Suggested: no (1.0×).
   GPS jamming primarily corrupts position. Time error is more about
   clock sync. Confirm to keep things conceptually clean.

### Acceptance criteria

- Two output files exist: `localizations.json` and
  `localizations_jammed.json`.
- The jammed variant has visibly larger `cep50_m` on every scenario.
- ROE recommendation flips from STRIKE → RECON for at least one
  scenario when jamming is applied (this is the demo moment).
- `scenario_variant` and `jam_status_per_drone` present on jammed
  entries, absent (or null) on clean entries.
- The convenience script produces both files in one invocation.

---

## Session 3 — Response Animation Phase (Frontend)

### Goal

After the existing `localize → hold` phases, add a `respond` phase that
animates a "response drone" arcing from the nearest sensor drone toward
the target pin. Visual differs by `recommended_action`: STRIKE = red
trail + impact flash; RECON = amber trail + circling pattern.

### Files touched

- Modified: `ui/index.html` only (single-file UI is the convention)

### Architecture

The existing phase engine in `index.html` is the right extension point:

```js
PHASE_ORDER = ["transit", "listen", "localize", "hold"]
PHASE_MS    = { transit: 4200, listen: 2200, localize: 2800, hold: 5200 }
PHASE_LABEL = { transit: "...", listen: "...", localize: "...", hold: "..." }
```

Add a new phase between `localize` and the (existing) `hold`:

```js
PHASE_ORDER = ["transit", "listen", "localize", "respond", "hold"]
PHASE_MS    = { ..., respond: 4500, hold: 3500 }   // shorten hold
PHASE_LABEL = { ..., respond: "WEAPONS / RECON" }
```

Then a new branch in `tickPlayback(dt)`:

```js
} else if (pb.phase === "respond") {
   // 1. find nearest sensor drone (already on map)
   // 2. interpolate a "responder" entity along an arc from drone → target
   // 3. render with action-specific style
   // 4. emit pulses; on action="STRIKE" final frame -> impact flash
}
```

The responder is a single new entity (id `responder-<scenario>`) drawn
via the same `upsertEntity()` mechanism — new icon in `ICONS` table.

### Tasks

1. **Add new icons to `ICONS` table**
   - `responder_strike` (red FPV / kamikaze drone silhouette)
   - `responder_recon` (amber sensor drone silhouette)
   - Reuse existing SVG style — small (28×28), match existing palette

2. **Extend phase machinery**
   - Append `"respond"` to `PHASE_ORDER` before `"hold"`
   - Add to `PHASE_MS` (suggest 4500 ms) and `PHASE_LABEL`
     ("WEAPONS / RECON")

3. **Implement `tickPlayback`'s `respond` branch**
   - Read `recommended_action` from `cur.entry`
   - Identify nearest sensor drone to the target (distance in
     normalized coords)
   - Compute arc waypoints: start at nearest drone, midpoint offset
     perpendicular by ~10% of map width, end at target
   - Interpolate position along arc by `t = phaseT / PHASE_MS.respond`
   - Render via `state.targets.push({id: "responder-...", ...})` OR a
     new state slot `state.responders[]` (preferred — see below)

4. **Add `state.responders[]` slot**
   - Why a new slot: responders are not targets. They have separate
     icons, separate styling, and shouldn't show up in legends as
     hostile.
   - Rendered in `renderEntities()` analogously to drones/targets

5. **STRIKE-specific effects** (when `recommended_action === "STRIKE"`)
   - On arrival (last 15% of phase): emit a red impact pulse
   - Briefly enlarge the target pin (scale 1.3× for 250ms)
   - Add log line: `"STRIKE · target engaged · ..."` at impact moment
   - On final 5% of phase: replace target icon with "neutralized"
     marker (faded out, grey)

6. **RECON-specific effects** (when `recommended_action === "RECON"`)
   - On arrival: orbit around the target pin (2-3 small loops)
   - Show a 'CAMERA ON' marker on the responder
   - Add log line: `"RECON · imagery acquired · target verified"`
   - Target stays visible, gets a yellow border (positive ID hint)

7. **HOLD effects** (when `recommended_action === "HOLD"`)
   - No responder dispatched. Phase still plays for symmetry but just
     shows a "STANDBY — INSUFFICIENT CONFIDENCE" banner
   - Shorter duration acceptable (skip to next scenario sooner)

8. **Action banner** above the map
   - A new overlay div in `.map-wrap` showing
     `ROE: STRIKE AUTHORIZED — RAVEN-1 → 62.41001, 25.75004`
   - Appears at the start of `respond`, fades out at the end of `hold`
   - Styled with action colour: STRIKE=red, RECON=amber, HOLD=grey

9. **Update the timeline UI**
   - `updateTimelineUI()` already shows phase + event progress —
     extend the readout so the operator sees the ROE outcome:
     `"FIX 4.2m → STRIKE"` next to the existing CEP readout

### Considerations

- **💡 NOTE: the responder is purely visual.** The math (decision,
  CEP, etc.) is already baked into `localizations.json`. Don't
  re-derive anything in the browser.
- **💡 NOTE: arc, not straight line.** Real drones don't fly in
  straight lines and the curve reads better visually. Use a quadratic
  Bezier with perpendicular offset.
- **💡 NOTE: prefer additive state.** Don't repurpose
  `state.targets`/`state.drones`. Add `state.responders` for clarity.
- The "neutralized" target swap (STRIKE) is what makes the scene
  feel like it concluded. Don't skip it.

### ⚠ HUMAN INPUT NEEDED

1. **Visual style of the responder** — Sonnet should generate a
   responder icon, then ask the user to confirm or paste a preferred
   SVG. (FPV-drone-with-warhead vs reconnaissance-quadcopter — your
   call.)
2. **Phase duration** — 4500 ms feels right for one-scenario demos but
   may be too slow for multi-scenario chains. Confirm.
3. **STRIKE iconography** — a literal "X over target" or a fade-to-grey
   "neutralized" treatment? Suggested: fade-to-grey. Confirm.
4. **Should the action banner be persistent (full hold + respond) or
   only during respond?** Suggested: appears at respond start, persists
   through hold.

### Acceptance criteria

- The five-phase playback runs end-to-end without flicker.
- For a STRIKE scenario: responder arcs from drone to target,
  impact flash, target neutralized icon, log line written.
- For a RECON scenario: responder arcs to target, orbits, target
  gets positive-ID border, log line written.
- For a HOLD scenario: no responder; banner says "STANDBY".
- Action banner shows the right colour/text per ROE action.
- 60 fps maintained (check `statFps` in footer).

---

## Session 4 — Recon Imagery + Telemetry Log (Frontend)

### Goal

When RECON is dispatched, a "camera feed" thumbnail pops in (placeholder
image with HUD chrome). At the same time, a structured telemetry log
streams synchronised with the phase: `ENGAGING → IMAGING → POSITIVE ID
→ STRIKE AUTHORIZED → IMPACT`.

### Files touched

- Modified: `ui/index.html`
- New: `ui/assets/recon-placeholder-1.jpg` and 2-3 more
- The placeholder JPGs can be sourced from public-domain aerial /
  thermal imagery, or hand-drawn schematics — anything that reads as
  "from a drone camera".

### Architecture

```
respond phase begins
   │
   ├── if action == STRIKE:
   │       telemetry: ENGAGING → ARMED → IMPACT
   │
   └── if action == RECON:
           telemetry: APPROACHING → IMAGING (popup) → ID CONFIRMED → REPORT
           imagery popup shown at t = 0.4 .. 0.95 of phase
```

The telemetry stream is just a scheduled list of log lines emitted via
`addLog()` at specific phase progress fractions:

```js
const TELEMETRY = {
  STRIKE: [
    { at: 0.05, msg: "Responder dispatched · weapons hot",   lvl: "warn" },
    { at: 0.50, msg: "Final approach · target locked",        lvl: "warn" },
    { at: 0.90, msg: "IMPACT · target neutralized",           lvl: "hostile" }
  ],
  RECON: [
    { at: 0.05, msg: "Recon dispatched · approach inbound",   lvl: "warn" },
    { at: 0.40, msg: "On-target · imaging now",               lvl: "warn" },
    { at: 0.70, msg: "POSITIVE ID · hostile combatant",       lvl: "hostile" },
    { at: 0.92, msg: "Report sent · awaiting authority",      lvl: "ok" }
  ],
  HOLD: [
    { at: 0.10, msg: "STANDBY · insufficient confidence",     lvl: "warn" },
    { at: 0.50, msg: "Repositioning swarm for next fix",      lvl: "ok" }
  ]
};
```

The imagery popup is a fixed-position `<div>` that animates in from
the right; container has HUD chrome (crosshair, "CAM 1", recording dot)
overlaid on the image.

### Tasks

1. **Add imagery popup DOM** to `index.html`
   - A `.recon-feed` container, hidden by default
   - Inside: `<img>` for the placeholder, plus overlay divs for
     crosshair, top-right "REC ●", bottom timestamp
   - CSS animation: slide in from right with a 200ms ease-out

2. **Add `TELEMETRY` schedule constant** as above

3. **Implement scheduler in `tickPlayback`'s respond branch**
   - Track which telemetry messages have been fired (`pb.telemetryFired:
     Set<int>`)
   - At each tick, check if `t > entry.at` and that index not yet fired

4. **Wire imagery popup show/hide**
   - On RECON respond start: pick an image from
     `ui/assets/recon-*.jpg` (round-robin by scenario index)
   - Show at `t = 0.4`, hide at end of `hold` phase
   - For STRIKE: do not show (the strike doesn't need recon imagery)

5. **Add `ui/assets/recon-*.jpg`** — 3-4 small (~600×450) placeholder
   images. Could be:
   - A satellite-style top-down green forest with a small red square
   - A thermal blob with crosshairs
   - A grainy aerial view

6. **Style the popup**
   - 320×240 px, positioned bottom-right of the map, above the footer
   - Border in `--accent` with HUD chrome
   - Subtle scan-line CSS overlay for "video feed" feel

### Considerations

- **💡 NOTE: imagery is decoration, not data.** Don't try to actually
  retrieve a real image based on coordinates. A fixed pool is fine.
- **💡 NOTE: telemetry timing is relative to phase, not wall clock.**
  Use `phaseT / PHASE_MS.respond` as the progress value.
- **💡 NOTE: don't fire the same telemetry twice.** Track fired indices.
- The popup must not block clicks anywhere on the map (use
  `pointer-events: none` on the wrapper, `auto` on a close button if
  added).

### ⚠ HUMAN INPUT NEEDED

1. **Imagery source.** Sonnet cannot ship real surveillance imagery.
   Either: user provides 3-4 placeholder images, OR Sonnet generates
   procedural SVG "fake camera views" inline. Suggested: ask for user
   to dump 3 images into `ui/assets/`, fall back to inline SVG if not.
2. **Telemetry copy/wording.** The strings above are first drafts —
   confirm tone and whether to use ALL-CAPS military style or normal
   sentence case. Suggested: ALL-CAPS short phrases for status, normal
   case for descriptive log lines.
3. **Sound effects?** Optional — out of scope unless the user pushes.

### Acceptance criteria

- During a RECON respond phase, the imagery popup slides in at
  `t ≈ 0.4` and closes when scenario advances.
- Telemetry log lines stream in at the right phase fractions, with
  correct severity colours.
- No telemetry line repeats within one phase.
- STRIKE scenarios never show the imagery popup.
- HOLD scenarios show only "STANDBY" telemetry.

---

## Session 5 — Multi-Threat Priority Stack (Backend + Frontend)

### Goal

When multiple scenarios are localised, the UI shows a ranked target
list (highest priority first). The swarm allocates response to the top
threat. Pipeline emits a numeric priority per scenario.

### Files touched

- Modified: `triangulation/policy.py` (add `priority(...)` function)
- Modified: `triangulation/locate.py` (emit `threat_priority` field)
- Modified: `ui/index.html` (add target stack panel + selection logic)

### Architecture

```
Backend
─────
policy.py::priority(label, recommended_action, cep50_m, severity)
   → integer (higher = more urgent)

   Default formula:
   base = SEVERITY_BASE[severity]              // high=100, med=50, low=20
   bonus = ACTION_BONUS[recommended_action]    // STRIKE=20, RECON=10, HOLD=0
   penalty = max(0, cep50_m - 10) * 0.3        // less confident → lower prio
   priority = base + bonus - penalty

Frontend
─────
A new left-rail panel: "TARGET STACK" listing scenarios sorted by
threat_priority descending, with current highlight on the one
currently in `pb.index`.

Each row shows: label, MGRS, CEP50, recommended action chip.
```

### Tasks

1. **Backend: `policy.py::priority()`**
   - Pure function as defined above
   - Constants at module top: `SEVERITY_BASE`, `ACTION_BONUS`

2. **Backend: emit `threat_priority`** in each `localizations.json`
   entry

3. **Backend: emit a sort hint** — `priority_rank` (0 = top) computed
   over the whole list before writing JSON. Trivial to compute in
   `run()`.

4. **Frontend: replace `Legend` panel with `Target stack` panel** OR
   add it as a new section above legend.
   - Read `state.frames`, sort by `entry.threat_priority` descending
   - Render compact rows, click to jump playback to that scenario

5. **Frontend: visual highlight of current scenario**
   - The row matching `state.playback.index` gets `--accent` border

6. **Frontend: action chip colours** in each row
   - STRIKE = red bg, RECON = amber bg, HOLD = grey bg

### Considerations

- **💡 NOTE: priority is computed once at pipeline time, not in the
  browser.** The browser must not re-rank scenarios — that would mean
  the math lives in two places.
- **💡 NOTE: priority_rank is for the UI's convenience.** A consumer
  that ignores rank can still re-sort by threat_priority.
- The target stack panel is what makes the demo feel like an
  *operator's* console rather than a single-event toy.

### ⚠ HUMAN INPUT NEEDED

1. **Severity-to-base mapping** — suggested `high=100, medium=50,
   low=20`. Confirm or override.
2. **Action bonus values** — confirm `STRIKE=20, RECON=10, HOLD=0`. The
   numbers don't matter individually, only their relative order; but
   they need to come from somewhere.
3. **What scenarios to demo simultaneously?** The current
   `events.json` has multiple scenarios at different timestamps. The
   target stack only makes sense if they're treated as "all active at
   once". Decide whether to:
   - (a) treat them as simultaneous (forced for demo)
   - (b) only show in the stack those within a sliding time window
     (more realistic but more complex)
   Suggested: (a). Confirm.

### Acceptance criteria

- Every entry has `threat_priority` (float) and `priority_rank` (int).
- Frontend renders a target-stack panel sorted by priority.
- Clicking a row jumps playback to that scenario.
- The current scenario is visually highlighted in the list.
- Action chips colour-coded correctly.

---

## Session 6 — Mesh Network Narrative (Docs)

### Goal

A one-page architecture diagram + page of prose explaining what
depends on the Kova mesh layer for this system to work end-to-end. No
code. Goes on a pitch slide.

### Files touched

- New: `docs/MESH_ARCHITECTURE.md`
- New: `docs/assets/mesh-dependencies.svg` (or mermaid in markdown)

### Architecture

The document has three sections:

1. **What this system does.** One paragraph plus a flow diagram.
2. **What it depends on the mesh for.** Three callouts, each with a
   data-rate / latency / criticality estimate:
   - Time-synced timestamps between drones (low data, low latency, high criticality)
   - Target coordinates + confidence (low data, low latency, medium criticality)
   - Recon imagery on the return path (high data, medium latency, low criticality)
3. **Graceful degradation matrix.** A 2D table: mesh-loss × GPS-loss →
   what the system can still do.

### Tasks

1. **Write the prose.** ~300-400 words. Honest about scope:
   "Our system is the application that needs a mesh; we did not build
   the mesh, but our design assumes the kind of resilience Kova's
   tactical mesh promises."

2. **Build the diagram.** Either:
   - Mermaid flowchart inline in markdown (preferred, version-controllable)
   - OR a hand-built SVG in `docs/assets/`

3. **Add the dependency table** — bandwidth/latency/criticality
   estimates with order-of-magnitude numbers (no precision).

4. **Add the degradation matrix.**

5. **Link from main README.md** to MESH_ARCHITECTURE.md.

### Considerations

- **💡 NOTE: don't oversell.** The point is to show this team
  understands what the mesh layer is for, not to claim mesh
  capability we didn't build.
- **💡 NOTE: mention multi-hop relay explicitly.** Drone_3 reaching
  the operator via drone_2 as a relay is what mesh *is*; that
  scenario should appear in the prose.

### ⚠ HUMAN INPUT NEEDED

1. **Tone.** Pitch-y or sober? Suggested: sober, technical, three
   pages max.
2. **Should this be its own slide deck (PDF)?** Suggested: no, just a
   markdown doc; the team can screenshot from it for slides.

### Acceptance criteria

- `docs/MESH_ARCHITECTURE.md` exists, ~300-400 words.
- Includes a system flow diagram (mermaid or SVG).
- Includes the dependency table with bandwidth/latency/criticality.
- Includes the degradation matrix.
- README.md links to it.

---

## Out of scope (for the avoidance of doubt)

These come up naturally in discussion but are deliberately excluded
from these sessions:

- **ML-based audio classifier.** The hardcoded frequency filters
  already work for the demo. Replacing them is high-effort,
  low-visible-payoff. List as "future work".
- **Moving / tracked target reconstruction.** Bursts from the same
  location compound nicely, but a Kalman tracker is a multi-day
  build. Skip.
- **Actual Kova mesh integration.** Documentation only (Session 6).
  Implementing the mesh is its own multi-day track and not what this
  team is doing.
- **3D localisation.** Altitude is read from `position.alt_m` but the
  pipeline is 2D. Skip.
- **Real surveillance imagery.** Session 4 uses placeholders.

## Cross-session conventions checklist

For Sonnet to keep consistent across all sessions:

- Use the existing CSS custom-properties palette (`--accent`,
  `--warn`, `--hostile`, etc.). Don't introduce new top-level
  colours.
- New JSON fields go in by adding, not renaming. Old consumers must
  keep working.
- New phase additions to `PHASE_ORDER` go in the natural place in the
  kill chain (transit → listen → localize → respond → hold).
- All new modules in `triangulation/` follow the
  `from __future__ import annotations` + type-hints style already in
  `core/`.
- Update `AGENTS.md` whenever the schema or module map changes.
- All new pipeline knobs are surfaced as CLI flags AND module-level
  constants. Two places to find them is one too few.
