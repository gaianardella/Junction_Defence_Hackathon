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
                  └─→  Session 18 (Live Ops tab)
Session 2 (Jam)  ─┴─→  Session 5 (Multi-threat)
Session 6 (Mesh narrative)   — independent, anytime
Session 7 (Audio)            — independent, anytime (frontend only)

Session 18 (Live Ops tab) depends on:
  Session 7  (tab framework — see SESSIONS_INTERACTIVE.md)
  Session 8  (Flask backend — see SESSIONS_INTERACTIVE.md)
  Session 11 (2-drone hyperbola — see ROADMAP.md "New session specifications")
  Session 13 (kill-drone button — see ROADMAP.md "New session specifications")
  Session 14 (source icon + cones — see ROADMAP.md "New session specifications")
```

Recommended order if implementing sequentially: 1, 2, 3, 4, 5, 6, 7, 18.
Session 18 picks up after Sessions 7–14 are integrated (sandbox tab,
sliders, 2-drone math, kill button, source icon all in place).

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

## Session 7 — Ambient & Event Audio (Frontend)

### Goal

Play synchronised audio during the demo. Three layered channels:

1. **Forest ambient** — background crickets, birdsong and forest atmos at
   low volume, running continuously from the first frame.
2. **Drone patrol buzz** — looping UAV sound during `transit` and `listen`
   phases; cross-fades to silence as `localize` begins (acoustic silence
   sells the "we just found the source" moment).
3. **Event detonation** — plays the detected-event sound **once** at the
   moment the target pin appears (`localize`, `t = 0.4`); the specific
   clip is chosen by `entry.label`.

No external libraries. Use the browser **Web Audio API** only
(`AudioContext`, `GainNode`, `AudioBufferSourceNode`).

### Audio files

All paths are relative to the repo root and served by
`python3 -m http.server 8080`. The UI fetches them via relative URLs
(`../data/...` from `ui/index.html`).

| Role | File |
|---|---|
| Drone patrol (loop) | `data/samples/drone/uas_drone_pass_dcpoke.wav` |
| Event — tank | `data/samples/tank/kakaist-tank-moving-sfx-319878.mp3` |
| Event — gunshot | `data/samples/gunshot/demo_gunshot_128293.wav` |
| Event — missile_launch | `data/samples/missile_launch/ucas_launch_x47b_qubodup.flac` |
| Ambient — forest atmos | `data/samples/missile_launch/forest/730223_klankbeeld_forest-in-the-netherlands-320-pm-230328_572.wav` |
| Ambient — birds | `data/ESC-50/audio/1-100038-A-14.wav` |
| Ambient — crickets | `data/ESC-50/audio/1-57316-A-13.wav` |

**Drone clip must loop seamlessly** — set `AudioBufferSourceNode.loop = true`
and optionally set `loopStart`/`loopEnd` to trim any click at the tail.

**FLAC note**: `ucas_launch_x47b_qubodup.flac` plays natively in
Chromium/Chrome and Safari (macOS). Firefox on Windows may not decode it.
If the demo machine is Windows + Chrome, no action needed. If cross-browser
support is required, convert the FLAC to WAV offline before the demo:
```
ffmpeg -i ucas_launch_x47b_qubodup.flac ucas_launch_x47b_qubodup.wav
```

### Architecture

```
AudioEngine (singleton in index.html)
│
├── ctx          AudioContext (lazy-created on first user gesture)
│
├── ambientGain  GainNode  ← birds + crickets + forest atmos play here
│                            target volume: 0.18
│
├── droneGain    GainNode  ← looping drone clip
│                            fade in on transit/listen, out on localize
│                            target volume: 0.55 while active, 0 while silent
│
└── eventGain    GainNode  ← one-shot event sound
                             plays once per scenario at localize t=0.4
                             target volume: 1.0 (no fade — it should punch)
```

All three `GainNode`s connect to `ctx.destination`.

Volume changes use `gain.linearRampToValueAtTime()` with a 0.8 s ramp
so there are no clicks.

### Files touched

- Modified: `ui/index.html` only

### Tasks

1. **`AudioEngine` object** — add as a module-level singleton at the top
   of the `<script>` block:
   ```js
   const AudioEngine = {
     ctx: null,
     buffers: {},         // label → AudioBuffer
     ambientSources: [],  // running ambient source nodes
     droneSource: null,
     ambientGain: null,
     droneGain: null,
     eventGain: null,
   };
   ```

2. **`AudioEngine.init()`** — call once on first user interaction
   (attach to any existing button click; reuse the first `btnPause`,
   `btnDemo`, or `btnLocalize` listener):
   - `AudioEngine.ctx = new AudioContext()`
   - Create the three `GainNode`s and wire to `ctx.destination`
   - Fetch and decode **all** audio files via `fetchBuffer(url)`
   - Start the three ambient clips (birds, crickets, forest atmos) on
     `ambientGain` with `loop = true`
   - Start the drone clip on `droneGain` with `loop = true`,
     initial gain `0` (silent until transit starts)

3. **`fetchBuffer(url)`** helper:
   ```js
   async function fetchBuffer(url) {
     const res = await fetch(url);
     const ab  = await res.arrayBuffer();
     return AudioEngine.ctx.decodeAudioData(ab);
   }
   ```
   Wrap in try/catch; log a warning to the event log if a file 404s —
   don't crash the whole UI.

4. **Phase-linked volume changes** — hook into the existing
   `advancePlaybackPhase()` function (already called on each phase
   transition):
   ```js
   // In advancePlaybackPhase(), after pb.phase is updated:
   AudioEngine.onPhase(pb.phase, cur.entry.label);
   ```

   ```js
   AudioEngine.onPhase = function(phase, label) {
     if (!this.ctx) return;
     const now = this.ctx.currentTime;
     const RAMP = 0.8;   // seconds
     if (phase === "transit" || phase === "listen") {
       this.droneGain.gain.linearRampToValueAtTime(0.55, now + RAMP);
     } else {
       this.droneGain.gain.linearRampToValueAtTime(0.0, now + RAMP);
     }
   };
   ```

5. **Event sound trigger** — in the `localize` branch of
   `tickPlayback(dt)`, at the moment `pb.localizeLogged` transitions
   from false to true (same gate already used for the sonar pulse):
   ```js
   AudioEngine.playEvent(cur.entry.label);
   ```

   ```js
   AudioEngine.playEvent = function(label) {
     if (!this.ctx) return;
     const MAP = {
       gunshot:        "gunshot",
       missile_launch: "missile",
       tank:           "tank",
       drone:          "drone",   // hostile drone — reuse clip
     };
     const key = MAP[label];
     if (!key || !this.buffers[key]) return;
     const src = this.ctx.createBufferSource();
     src.buffer = this.buffers[key];
     src.connect(this.eventGain);
     src.start();
   };
   ```

6. **Demo-mode audio** — when the user hits DEMO:
   - Drone buzz fades in immediately (drone is on screen).
   - No event sounds (demo has no real `entry.label`).

7. **Mute / unmute button** — add a small `🔇 MUTE` button to the
   left panel (below the WebSocket section). Toggling it sets
   `ctx.destination.gain` to 0 / 1, or simply suspends / resumes the
   `AudioContext`. Label it `MUTE` / `UNMUTE`. Keep it minimal.

8. **Graceful degradation** — if `AudioContext` is not available
   (old browser) or any `fetch` fails, the UI must continue working.
   Wrap all audio code in try/catch. Log failures to the event log at
   `warn` level: `"Audio: failed to load <file>"`.

### Considerations

- **💡 NOTE: AudioContext requires a user gesture.** Browsers block
  audio autoplay. Do not call `new AudioContext()` on page load. Call
  it inside an existing button handler (`btnLocalize`, `btnDemo`, or
  `btnPause`) — the first click is enough. After `init()`, subsequent
  phase changes can trigger audio freely.
- **💡 NOTE: loop the drone clip, not the event clips.** The drone
  clip (`uas_drone_pass_dcpoke.wav`) is a short pass-by recording.
  `loop = true` makes it continuous. Event clips (gunshot, missile,
  tank) are one-shot — do not loop them.
- **💡 NOTE: keep the three ambient sources running at all times.**
  Starting and stopping them per-phase causes audible clicks. Instead,
  vary only the gain. The ambient gain can be nudged lower during
  `localize` and `hold` to let the event punch through, then back up
  for `transit`.
- **💡 NOTE: the forest atmos file is long.** Use it as the primary
  ambient layer. Birds and crickets from ESC-50 are short loops (~5 s);
  they provide variation on top.
- **💡 NOTE: the FLAC will decode fine in Chrome.** Don't pre-convert
  unless the demo machine is confirmed non-Chromium.
- Keep total added JS under ~80 lines. This is glue code, not a DAW.

### ⚠ HUMAN INPUT NEEDED

1. **Volume balance** — the suggested levels (ambient 0.18, drone 0.55,
   event 1.0) are starting points. Tune by ear before the pitch.
   Ask the user to confirm after a first listen.
2. **Should the drone buzz play in LOCALIZE mode even when the current
   scenario label is `"drone"` (hostile drone)?** Ambiguous — a hostile
   drone sounds similar to a sensor drone. Suggested: yes, play it
   regardless, since the acoustic scene is "drones are in the air".
   Confirm.
3. **Mute button placement** — suggested: bottom of the left panel.
   If the panel is already crowded, a small icon-only button in the
   header is acceptable.
4. **Should the ambient layer also fade during the event sound?** A
   brief ambient duck (−6 dB for 1 s) makes the event punchier.
   Suggested: yes. Confirm before implementing.

### Acceptance criteria

- Clicking any button for the first time initialises the audio context
  without errors.
- Forest ambient (at least one of the three clips) is audible within
  2 s of the first button press.
- Drone buzz is audible during `transit` and `listen` phases, silent
  during `localize` and `hold`.
- The correct event sound plays once when the target pin appears, with
  no repeats within the same scenario.
- MUTE button silences all audio; pressing it again restores sound.
- A 404 or decode error on any audio file shows a `warn` log line
  but does not crash the UI or block the animation loop.
- `statFps` stays ≥ 55 — audio work is off the main thread via Web
  Audio; it must not drop frames.

---

## Session 18 — Live Ops tab (live event injection)

### Goal

A new tab `🎮 LIVE OPS` where the demo runs as a continuous, live,
reactive simulation. **N drones** patrol the map at all times.
The operator drops events from a sidebar — `🔫 GUNSHOT`, `🚜 TANK`,
`🚀 MISSILE`, `🦌 WILDLIFE` — by clicking a button then clicking
the map. The backend computes per-drone detection times from real
geometry, selects the **3 closest alive drones**, runs the full
pipeline (math → ROE → response), and the UI animates the result
in real time. Kill-drone works in this tab too; when 2 drones are
left, the system gracefully falls back to the 2-drone hyperbola
fix (Session 11) and forces a SEARCH. No scripted scenarios. No
pre-baked JSON. This is the "system is actually live" proof.

### Why this matters

Scripted scenario tabs are rehearsed pitch content. Live Ops is the
"hand-the-laptop-to-the-judge" tab. A judge dropping a gunshot at a
random location and watching the system react in real time is
qualitatively different from a replay. It also lights up three
otherwise abstract stories at once: the **discriminative classifier
story** (drop a wildlife event → green MONITOR action), the
**graceful-degradation story** (kill drones mid-engagement → see
ellipse collapse to hyperbola+wedge → ROE downgrades to SEARCH live),
and the **N-drone scaling story** (the system picks the best 3 of N,
not the only 3 it has).

### Dependencies

Hard prerequisites (this session won't function correctly without):

- **Session 7** — Tab bar + phase stepper (this is a new tab in the
  existing bar; the phase machine drives the live animation too)
- **Session 8** — Live error sliders + Flask backend (this session
  extends the Flask backend; the sliders work in Live Ops too)
- **Session 11** — 2-drone bearing-only localization (this session's
  graceful-degradation depends on the hyperbola fix existing)
- **Session 13** — Kill-drone button (this session reuses the
  killed-drones state machine)
- **Session 14** — Source icon + acoustic cones (this session reuses
  the cone-emission visual machinery)

Soft prerequisites (nice-to-have but Live Ops works without):

- **Session 15** — Ambient (wildlife) triangulation tab (Live Ops
  ships its own wildlife dropper; if Session 15 is in, the colour
  conventions match exactly)
- **Session 12** — Multi-scene narrative tab (independent; both can
  coexist as separate tabs)

### Files touched

- New: `triangulation/live_ops.py` — server-side live state + helpers
- New: `triangulation/classifier.py` — Classifier protocol + impls
- Modified: `triangulation/server.py` — adds `/api/live/*` endpoints
- Modified: `ui/index.html` — new tab, drop sidebar, click handling
- Modified: `triangulation/locate.py` — minor: nothing functional
  changes; `localize_scenario` already handles N-row groups

### Architecture

The live state lives **server-side** in a singleton in
`triangulation/server.py`. The UI is a thin reactive client.

```
┌─ User clicks 🔫 GUNSHOT, then clicks map at (lat, lon) ───────────────┐
│                                                                       │
│ POST /api/live/event { label: "gunshot", lat, lon }                  │
│   │                                                                   │
│   ▼                                                                   │
│ LiveOpsState.handle_event(label, lat, lon)                           │
│   │                                                                   │
│   ├── 1. snapshot drone roster: positions + alive flags              │
│   │                                                                   │
│   ├── 2. for each drone, compute event_time_ns:                      │
│   │        t = base_ns                                                │
│   │          + ||drone_xy - event_xy|| / C       (real geometry)     │
│   │          + N(0, sigma_t_s)                   (jitter)            │
│   │                                                                   │
│   ├── 3. classifier.classify(truth_label, audio?)                    │
│   │        → (predicted_label, confidence)                            │
│   │      [PerfectClassifier returns truth; MLClassifier is a stub]   │
│   │                                                                   │
│   ├── 4. select 3 closest ALIVE drones (or 2, or 1, or 0)            │
│   │                                                                   │
│   ├── 5. branch by alive count:                                      │
│   │     ─ ≥ 3 alive → localize_scenario (existing 3-drone math)      │
│   │     ─ 2 alive  → solver_2drone (Session 11 hyperbola+wedge)      │
│   │     ─ 1 alive  → return INSUFFICIENT_SENSORS                     │
│   │     ─ 0 alive  → return INSUFFICIENT_SENSORS (no drones)         │
│   │                                                                   │
│   └── 6. return localization-shape entry + per-drone arrival times   │
│           + predicted_label + true_label                              │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘

┌─ UI receives the result ──────────────────────────────────────────────┐
│ - immediately play audio for the event (Session 7's AudioEngine)     │
│ - build an in-memory "frame" from the result (same shape as the      │
│   pre-baked frames from buildFrames())                                │
│ - feed the frame to the existing tickPlayback phase machine          │
│ - per-drone "light up" pulses fire at their real computed arrival    │
│   times (so you visibly see the wavefront reach drones sequentially) │
│ - source icon, cloud, action chip, banner — all reuse Session 14    │
└───────────────────────────────────────────────────────────────────────┘
```

### State model (server)

```python
# triangulation/live_ops.py

@dataclass
class Drone:
    id: str                                # "drone_1" .. "drone_N"
    base_lat: float                        # patrol centre
    base_lon: float
    alive: bool = True
    # current patrol position (updated when /api/live/state is polled)

@dataclass
class LiveEvent:
    id: str                                # uuid hex
    label: str                             # "gunshot" | "tank" | "missile_launch" | "wildlife"
    lat: float
    lon: float
    t_drop_ns: int
    result: dict | None = None             # localizations.json-shape entry

@dataclass
class LiveOpsState:
    drones: list[Drone]
    classifier: Classifier
    sigma_t_ms: float = 6.0
    sigma_pos_m: float = 12.0
    events: list[LiveEvent] = field(default_factory=list)
    t_start_ns: int = field(default_factory=lambda: time.time_ns())

    def alive_drones(self) -> list[Drone]:
        return [d for d in self.drones if d.alive]
```

Single in-process singleton. No persistence to disk (live ops is
session-scoped). Reset endpoint zeroes the events list and revives
all drones.

### Classifier abstraction (future-proof for the ML team)

```python
# triangulation/classifier.py

class Classifier(Protocol):
    def classify(self, truth_label: str,
                 audio: bytes | None = None) -> tuple[str, float]:
        """Return (predicted_label, confidence_in_0_to_1)."""
        ...

class PerfectClassifier:
    """v1 default. Always returns the truth with high confidence."""
    def classify(self, truth, audio=None) -> tuple[str, float]:
        return truth, 0.95

class MLClassifier:
    """v2 stub. When the ML team ships a model, plug it in here.

    Should accept a synthesised or real audio sample, run inference,
    return (predicted_label, confidence). The Live Ops backend
    doesn't care what's inside this class — it just calls classify().
    """
    def __init__(self, model_path: str):
        # load ONNX / PyTorch / whatever
        raise NotImplementedError("ML classifier not yet shipped")
    def classify(self, truth, audio) -> tuple[str, float]:
        raise NotImplementedError
```

Switching is via env var or query string:
`?detection_mode=perfect` (default) | `?detection_mode=ml`.

The UI shows a small badge `DETECTION: perfect` (green) or
`DETECTION: ML` (blue). The misclassification narrative — drop a
tank, classifier guesses "drone" → recon dispatched → reclassified
correctly as "tank" → ROE escalates — naturally lights up once
`MLClassifier` is real. v1 ships perfect-only.

### Drone roster + patrol

Default: 5 drones in a loose pentagon centred on
`(62.412, 25.752)`, radius ~150 m. Patrol motion is a slow
sinusoidal drift (~30 m amplitude, ~20 s period) computed
server-side; the UI polls position every 500 ms and lerps for
smoothness.

```python
def patrol_position(drone: Drone, t_now_ns: int) -> tuple[float, float]:
    """Slow sinusoidal drift around base. Visual only."""
    t_s = t_now_ns / 1e9
    seed = int(hashlib.md5(drone.id.encode()).digest()[0])
    dlat = 0.0003 * math.sin(t_s / 5.0 + seed)        # ~30 m
    dlon = 0.0003 * math.cos(t_s / 6.5 + seed * 2)
    return drone.base_lat + dlat, drone.base_lon + dlon
```

Drone count is configurable via `/api/live/config` (3..10 supported).

### N-drone selection: pick best 3

```python
def select_drones_for_event(event_lat, event_lon,
                            alive_drones: list[Drone],
                            max_drones: int = 3) -> list[Drone]:
    """Return the 3 (or fewer) alive drones closest to the event.

    Distance computed in the local plane (equirectangular projection
    around the event point, accurate enough for ~1 km).
    """
    if not alive_drones:
        return []
    def dist(d: Drone) -> float:
        return distance_m(d.last_lat, d.last_lon, event_lat, event_lon)
    return sorted(alive_drones, key=dist)[:max_drones]
```

The existing `localize_scenario(group)` already accepts any list of
event rows; it doesn't hardcode "3 drones". So this selection step
is the only new logic between live drone roster and the math.

### 2-drone fallback

When `len(alive_drones) == 2`:

- The 3-drone solver would crash (or return garbage).
- Instead, call `solver_2drone.hyperbola_fix(events, drone_positions)`
  from Session 11.
- ROE policy automatically forces SEARCH (you can't STRIKE on a
  curve — Session 11 already enforces this).
- UI renders the hyperbola curve + wedge band instead of an ellipse,
  using Session 11's frontend renderer.

### 1-drone or 0-drone fallback

- 1 alive: return an output entry with `fix_kind: "none"`,
  `recommended_action: "INSUFFICIENT_SENSORS"`, `source: null`,
  `cloud_latlon: []`. UI shows a banner: `SENSOR LOSS — fix
  unavailable. Single-sensor bearing requires RSSI mesh.`
- 0 alive: same banner; no detection animation at all.

These are not error states — they're real operational outcomes.
Don't crash; render them honestly.

### Endpoints

| Endpoint | Body | Returns |
|---|---|---|
| `POST /api/live/event` | `{label, lat, lon}` | localization entry + arrival_times_per_drone + predicted_label + true_label |
| `POST /api/live/kill_drone` | `{drone_id}` | `{ok: true, alive_count: N}` |
| `POST /api/live/revive_drone` | `{drone_id}` | `{ok: true, alive_count: N}` |
| `POST /api/live/reset` | `{}` | `{ok: true}` (clears events, revives all drones) |
| `GET /api/live/state` | — | `{drones: [{id, lat, lon, alive}], events_count, classifier_mode}` |
| `POST /api/live/config` | `{sigma_t_ms?, sigma_pos_m?, detection_mode?, drone_count?}` | `{ok: true, config}` |

All endpoints return JSON. All accept JSON bodies (or query strings
for `GET`).

### UI: drop UX

Sidebar **replaces** the scenario list when the LIVE OPS tab is
active. Layout:

```
┌─ DROP EVENT ──────────────────────────┐
│  🔫 GUNSHOT          (threat)         │
│  🚜 TANK             (threat)         │
│  🚀 MISSILE LAUNCH   (threat)         │
│  🦌 WILDLIFE         (ambient)        │
├───────────────────────────────────────┤
│  💀 KILL DRONE       (per-drone pill) │
│  ❤️ REVIVE ALL                         │
│  🔄 RESET ALL                          │
├───────────────────────────────────────┤
│  DETECTION: perfect ⓘ                 │
│  ALIVE: 5/5                            │
│  EVENTS: 3                             │
└───────────────────────────────────────┘
```

Interaction flow:

1. User clicks `🔫 GUNSHOT`. The button enters "armed" state
   (highlighted border, cursor changes to crosshair over the map).
2. User clicks anywhere on the map. The screen → lat/lon
   conversion uses the existing `bounds` projection inverse.
3. `POST /api/live/event` fires. Cursor reverts. Button un-arms.
4. Backend responds. UI plays audio + starts phase animation.
5. Old fix (if any) fades out as the new one starts.

Cancellation:

- `ESC` cancels armed mode.
- Clicking the same button again cancels.
- Right-click on map also cancels.

KILL DRONE works the same way: click `💀 KILL DRONE`, then click
a drone icon. The icon gets the existing red-☓ overlay from
Session 13.

### No concurrent events (v1)

Per user direction: when a new event drops, the previous fix is
cleared (fades out over ~500 ms). Only one active fix at a time.
v2 could add a queue or parallel pipelines; not for v1.

### Audio (fires at drop time)

Per user direction: audio fires the instant the event is dropped,
not when the wavefront reaches each drone. Reuses Session 7's
`AudioEngine.playEvent(label)` directly. No new audio code.

The per-drone wavefront-arrival timing still drives the **visual**
drone-light-up animation (Session 14's acoustic cones radiate from
the drop point at sound speed). The audio just doesn't sync to it —
audio fires now, cones radiate physically. Acceptable tradeoff for
simplicity.

### Tab-switch behaviour

- Switching from LIVE OPS to another tab: **state preserved**
  server-side. Events list, drone roster, kill states all hold.
- Switching back: pick up where you were. No animation replays.
- The kill-drone state from Session 13's other-tabs is **separate**:
  killing a drone in scripted-tab-1 doesn't kill it in LIVE OPS.
  LIVE OPS uses `LiveOpsState.drones`; other tabs use their own.

### Default scene

On first activation of LIVE OPS tab (or after RESET ALL):

- 5 drones spawn in a loose pentagon around `(62.412, 25.752)`.
- Patrol drift starts.
- Events list is empty.
- Classifier is `PerfectClassifier`.
- σ_t = 6.0 ms, σ_pos = 12 m (same as scripted scenario defaults).

### Phase machine reuse

Live Ops doesn't add new phases. It builds a synthetic "frame"
from the backend response and feeds it to the existing phase loop:

```js
// On /api/live/event response:
const fakeFrame = {
  drones: result.drones_used,            // for entity rendering
  source: result.source,                 // for source icon
  cloud_latlon: result.cloud_latlon,     // for cloud rendering
  cep50_m: result.cep50_m,
  recommended_action: result.recommended_action,
  // ... full localizations.json-entry shape ...
  arrival_times_ms: result.arrival_times_per_drone,  // NEW: for cone timing
};
state.activeFrame = fakeFrame;
state.step = 0;       // PATROL — drones in place
state.stepProgress = 0;
state.autoplay = true; // auto-advance through phases for live ops
```

The phase tick driver does the rest. Phases run at their normal
durations.

### Per-drone wavefront arrival visualisation

When the cones radiate from the source (Session 14's renderPhase
`DETECT` branch), each drone lights up when the **leading cone
radius** crosses its position. With Live Ops, the "arrival time"
isn't synthetic — it's the real distance/C computed by the backend.
So the drone-light-up sequence faithfully mirrors physics.

Per-drone label appears: `drone_3   t = +146 ms` (relative to first
detection), reusing the same machinery as scripted tabs.

### Subtasks

Backend (Python):

- 18.1 `triangulation/classifier.py` with `Classifier` Protocol +
       `PerfectClassifier` + `MLClassifier` stub (raises NotImplemented).
- 18.2 `triangulation/live_ops.py` defining `Drone`, `LiveEvent`,
       `LiveOpsState`. Includes `patrol_position()`,
       `select_drones_for_event()`, `compute_event_arrivals()`,
       `handle_event()`.
- 18.3 `LiveOpsState.handle_event()` orchestrates: snapshot, jitter,
       select, branch by alive count, call `localize_scenario()` or
       `solver_2drone.hyperbola_fix()` or return INSUFFICIENT_SENSORS.
- 18.4 Server endpoint `POST /api/live/event` (returns full
       localization entry + arrival_times_per_drone).
- 18.5 Server endpoints `POST /api/live/kill_drone`,
       `POST /api/live/revive_drone`, `POST /api/live/reset`.
- 18.6 Server endpoint `GET /api/live/state` for UI polling
       (drones with patrol positions, event count, alive count).
- 18.7 Server endpoint `POST /api/live/config` for sigma and
       detection-mode tuning.
- 18.8 Singleton instantiation at server startup with 5 drones in
       default pentagon.
- 18.9 Unit tests: pick-best-3 logic, 2-drone fallback, 1-drone
       INSUFFICIENT_SENSORS, classifier swap.

Frontend (`ui/index.html`):

- 18.10 New tab `🎮 LIVE OPS` in the existing tab bar (Session 7's
        tab framework).
- 18.11 Sidebar swap: when LIVE OPS active, render drop-event buttons
        instead of scenario list.
- 18.12 Cursor-crosshair drop mode; map click → backend POST.
- 18.13 ESC / right-click / same-button cancels drop mode.
- 18.14 Poll `GET /api/live/state` at 2 Hz; lerp drone positions
        client-side for smoothness.
- 18.15 Render N drones (no hardcoded `drone_1/2/3`); reuse existing
        drone entity rendering.
- 18.16 On event POST response, build synthetic frame, feed to
        phase machine, start animation.
- 18.17 Previous fix fades out (~500 ms) when new event arrives.
- 18.18 `DETECTION: perfect` badge + alive-count + event-count
        readouts in sidebar.
- 18.19 INSUFFICIENT_SENSORS banner when fix_kind == "none".
- 18.20 Kill-drone integration: kill button works in LIVE OPS tab;
        affects `LiveOpsState.drones[i].alive`.

ML hookup (deferred to when classifier ships):

- 18.21 (FUTURE) Implement `MLClassifier.__init__` to load model.
- 18.22 (FUTURE) Implement `MLClassifier.classify()` with real
        inference. Synthesize audio from truth_label or use
        recorded clip.
- 18.23 (FUTURE) Misclassification narrative: when predicted ≠ truth
        AND confidence is low, ROE downgrades to RECON; recon drone
        captures imagery; "reclassification" event upgrades back to
        STRIKE. UI shows a badge: `RECLASSIFIED: drone → tank`.

### Considerations

- **💡 NOTE: Backend is the source of truth for drone positions
  during Live Ops.** The UI just renders. Don't compute patrol
  positions client-side — they'd drift out of sync with what the
  backend uses for arrival-time computation.
- **💡 NOTE: `localize_scenario()` doesn't change.** It already
  takes a list of N event rows. The N-drone change happens
  upstream in `select_drones_for_event()`.
- **💡 NOTE: ML classifier is FUTURE-PROOF, not built.** v1 ships
  `PerfectClassifier` only. The abstraction exists so the ML team
  can drop in their model later without touching `live_ops.py`.
- **💡 NOTE: audio fires at drop time, not per-drone arrival.**
  Per user direction. Simpler. Visual cone radiation still uses
  real arrival times.
- **💡 NOTE: tab switching preserves backend state.** The
  `LiveOpsState` singleton lives across tab switches. Reset is
  explicit (button).
- **💡 NOTE: pick-best-3 uses Euclidean distance in local
  metres.** Project the event lat/lon to local plane around the
  event, project each drone too, sort by distance. Existing
  `projection.py` helpers do this.
- **💡 NOTE: 2-drone fallback is automatic.** Don't add a "switch
  to 2-drone mode" toggle. The system picks the math by alive
  count. That's the demo: kill a drone, watch the math change
  itself.
- **⚠ Concurrency: out of scope for v1.** New event clears the
  previous fix. If the user clicks two events in rapid succession,
  only the second is rendered. v2 could add a queue.
- **⚠ Patrol rate cap.** UI polls at 2 Hz, backend computes patrol
  on each poll. If many concurrent UI clients connect, scale via
  caching (one position snapshot per 500 ms). v1 is single-client
  so this doesn't matter.

### ⚠ HUMAN INPUT NEEDED

1. **Default drone count.** Suggested 5 (loose pentagon). Confirm
   or override (3 / 5 / 7).
2. **Patrol radius / drift speed.** Suggested ~30 m amplitude
   over ~20 s period (slow, atmospheric). Confirm.
3. **Drop UX.** Suggested click-button-then-click-map. Alternative
   is drag-drop (icon from sidebar onto map). Click-then-click is
   simpler; drag-drop is sexier. Confirm.
4. **Audio at drop vs at first-arrival.** Confirmed by user: at
   drop. Locked in.
5. **Default detection mode.** Suggested `perfect`. Confirm.
6. **Should the source icon at drop position remain visible
   indefinitely (as a "logged contact")?** Suggested: fade out
   after the COMPLETE phase ends, ~10 s post-drop. Confirm.
7. **Wildlife event label.** Suggested `"bird"` (uses Session 15's
   green styling). Alternative: a generic `"wildlife"` label that
   the policy maps to AMBIENT. Confirm.
8. **N-drone upper limit.** Suggested 10 (sidebar pills get crowded
   beyond that). Confirm.

### Acceptance criteria

- New tab `🎮 LIVE OPS` is selectable; sidebar swaps to drop-events
  panel.
- Default scene: 5 drones drift in a pentagon. UI updates positions
  at ~2 Hz, animation smooth (no jitter).
- Click `🔫 GUNSHOT`, click map → event drops, audio plays
  immediately, source icon appears, cones radiate, 3 closest drones
  light up at real wavefront-arrival times, cloud fades in, action
  chip + banner appear, responder animation plays.
- Click `🦌 WILDLIFE` → all visuals green, MONITOR action, no
  responder dispatch.
- Kill 1 drone → next event still triangulates with the closest 3
  of the remaining 4 (uses ellipse fix).
- Kill 2 drones (down to 3 alive) → still uses 3-drone math.
- Kill 3 drones (down to 2 alive) → next event renders a hyperbola
  + wedge (Session 11), action chip SEARCH (Session 9).
- Kill 4 drones (down to 1) → next event shows
  INSUFFICIENT_SENSORS banner; no fix drawn.
- RESET ALL → all drones revived, events cleared.
- Switching tabs and back → state preserved.
- `DETECTION: perfect` badge always visible.
- `PerfectClassifier` returns the dropped label with confidence
  0.95; UI's classifier-mode hook is wired and ready for ML swap.

---

## Out of scope (for the avoidance of doubt)

These come up naturally in discussion but are deliberately excluded
from these sessions:

- **ML-based audio classifier ON THE CRITICAL PATH.** Session 18
  ships the abstraction (`Classifier` protocol) so the ML team can
  drop in `MLClassifier` later, but v1 always uses `PerfectClassifier`.
  No demo timeline depends on ML existing.
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
