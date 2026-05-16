# Interactive Demo Sessions (Part 2)

Architectural plan for converting the demo from auto-advancing playback
to **operator-driven** with **live error tuning**. Pairs with `SESSIONS.md`
(Sessions 1–6); these are Sessions 7–9.

## Why this matters for the pitch

Auto-playback is fine for a kiosk; it's bad for a hackathon pitch because
the presenter cannot pace narration to a moving target. The judge can't
ask "what happens if the GPS is jammed worse?" because the demo has
already moved on. With operator-driven controls:

- The presenter says one sentence, clicks ▶ NEXT, says the next.
- The judge points at the cloud and says "what if the timing error were
  3× worse?" — slider goes up, cloud blooms in real time, ROE banner
  flips from STRIKE → RECON → SEARCH. Money slide answers itself.
- Three drones spreading out across a 5000 m² ellipse to sweep the area
  is a *more* impressive visual than a single drone hitting a point.

That triad — live tunability, manual pacing, geometry-aware response —
is what closes a defense-savvy judge.

## How this connects to SESSIONS.md (Part 1)

| Part 1 session | Status | Relationship |
|---|---|---|
| 1 — ROE policy engine | required | Session 9 extends `decide()` with a new SEARCH outcome |
| 2 — Jamming mode (pre-baked variants) | optional | Session 8 supersedes this; sliders make pre-baked variants unnecessary |
| 3 — Respond animation phase | required | Session 9 adds a multi-drone variant |
| 4 — Recon imagery + telemetry | required | Session 7 wraps it in the stepper |
| 5 — Multi-threat priority stack | optional | The new sidebar lives where this would have lived |
| 6 — Mesh narrative (docs) | independent | No interaction |

If your team has time for only some Sessions: pick **1 → 3 → 7 → 8 →
9**. That sequence is the highest-impact path.

## The new demo flow (operator-driven)

```
Sidebar holds 5 scenarios:
  ┌───────────────────────────────────┐
  │  ① Gunshot — clean geometry       │  default STRIKE
  │  ② Gunshot — degraded timing      │  high σ_t → RECON
  │  ③ Gunshot — drone GPS jammed     │  high σ_pos → SEARCH (large zone)
  │  ④ Tank — high severity, mid σ    │  STRIKE despite mid CEP
  │  ⑤ Missile launch — fast-moving   │  STRIKE, priority chip pulsing
  └───────────────────────────────────┘

Bottom controls:
  ▶ NEXT PHASE     ⏵ AUTO       ⟲ RESET     ⏪ PREV PHASE

Right rail:
  σ_t timing error     [ slider ]  6.6 ms     [GPS / NTP / unsynced markers]
  σ_pos position drift [ slider ]  11.8 m     [GPS / IMU / drift markers]
  CEP50:               18.7 m
  Zone area:           4200 m²
  Recommended action:  STRIKE  (red chip)

Phases per scenario:
  1. PATROL    → drones in formation, no detection yet
  2. DETECT    → audio event, three drones light up with timestamps
  3. LOCALIZE  → cloud + estimate appear
  4. DECIDE    → ROE banner flashes in, action chip updates
  5. RESPOND   → STRIKE / RECON / SEARCH animation plays
  6. COMPLETE  → final state, log line summary
```

The pitch flow:

1. Presenter clicks ① → ▶ NEXT → "Detection." → ▶ NEXT →
   "Triangulation. CEP50 4 m." → ▶ NEXT → "STRIKE authorized" →
   ▶ NEXT → animation runs → "Target neutralised."
2. Presenter clicks ② → "Same audio event, but timing-error doubled."
   → Slides σ_t to ~12 ms → cloud grows live → ROE flips RECON →
   ▶ NEXT through phases → recon arrives, image streams.
3. ③ — drags σ_pos slider hard right → cloud sprawls → ROE flips
   SEARCH → three drones spread across the ellipse, search pattern
   visualised → "And of course in production the swarm would
   reconverge once one of them finds the source."

This is roughly the same arc as the auto-rotating playback, but the
presenter is in control and the judge can poke at it.

---

## Session 7 — Scenario sidebar + phase stepper

### Goal

Replace `tickPlayback`'s auto-advance with a step-based playback engine
driven by user clicks. Five scenarios live in a left sidebar; the
currently selected one drives the map. Phases advance only on
▶ NEXT (or auto-play toggle).

### Files touched

- Modified: `ui/index.html` only

### Architecture

Rework the state machine around a single source of truth: `state.step`:

```js
state = {
  ...,
  scenarioIndex: 0,        // which of 5 scenarios is active
  step: 0,                 // 0 = PATROL, 1 = DETECT, ..., 5 = COMPLETE
  stepProgress: 0,         // 0..1 within the current step's animation
  autoplay: false,         // if true, steps advance themselves
  scenarios: [...]         // 5 entries; each has frames-like data
}

PHASES = [
  { id: "patrol",    label: "PATROL · standby",         dur: 0 },
  { id: "detect",    label: "DETECT · audio event",     dur: 1500 },
  { id: "localize",  label: "LOCALIZE · TDOA cloud",    dur: 2200 },
  { id: "decide",    label: "DECIDE · ROE evaluation",  dur: 1000 },
  { id: "respond",   label: "RESPOND · action exec",    dur: 4500 },
  { id: "complete",  label: "COMPLETE · contact held",  dur: 0 },
]
```

`tickPlayback(dt)` becomes phase-aware: it animates *within* a phase
(progress 0→1) but **never advances to the next phase on its own**
unless `state.autoplay` is true. The whole transit-blend code goes
away; map view always centres on the current scenario's drone bounds.

### Tasks

1. **HTML scaffolding for the sidebar**
   - 1.1 Add a `<div class="scenarios">` panel inside the existing left
         column, above the legend. Five cards.
   - 1.2 Each card: scenario thumbnail (small SVG of geometry), label,
         live CEP50 readout, action chip.
   - 1.3 Click a card → `setScenario(i)`.

2. **HTML scaffolding for the step controls**
   - 2.1 Add a `<div class="phase-controls">` at the bottom of the map
         wrap, just above the existing `footer`.
   - 2.2 Buttons: `⏪ PREV`, `▶ NEXT`, `⏵ AUTO`, `⟲ RESET`.
   - 2.3 Disable PREV/NEXT at boundaries; AUTO toggles the autoplay
         boolean.

3. **State migration**
   - 3.1 Add `state.scenarios[]`. On `loadLocalizations()`, populate
         from the loaded JSON. Cap to 5 by default (or all if fewer).
   - 3.2 Drop the existing `state.playback` (transit / listen /
         localize / hold logic) and replace with the phase-step state.
   - 3.3 Migrate the existing visuals (cloud, drones, targets) into a
         phase-driven renderer.

4. **Phase renderers**
   - 4.1 `renderPatrol()` — drones in formation, gentle patrol wobble.
   - 4.2 `renderDetect()` — drones light yellow as audio arrives;
         emit pulses at each drone with a small timestamp label
         (`+0 ms`, `+145 ms`, …).
   - 4.3 `renderLocalize()` — cloud fades in (alpha grows 0→1), target
         pin lands.
   - 4.4 `renderDecide()` — ROE banner appears: red/amber/grey by
         action; text from `entry.recommended_action_reason`.
   - 4.5 `renderRespond()` — responder animation (existing Session 3
         work). Multi-drone variant for SEARCH (Session 9).
   - 4.6 `renderComplete()` — frozen final state; log summary.

5. **NEXT / PREV / AUTO logic**
   - 5.1 NEXT: snap to end of current phase (progress = 1) if not yet
         there; if already at 1, advance to next phase.
   - 5.2 PREV: snap to start of current phase if progress > 0;
         otherwise step back.
   - 5.3 AUTO: when on, advance to next phase the moment progress = 1.
   - 5.4 RESET: scenarioIndex unchanged; step = 0; progress = 0; clear
         transient state (cloud alpha, target pins).

6. **Sidebar live updates**
   - 6.1 Each card's CEP50 and action chip update when σ sliders change
         (Session 8 dependency — show defaults until then).
   - 6.2 Active card gets `--accent` border.
   - 6.3 Hovering a card shows a tooltip with the per-drone σ values.

7. **URL state (nice-to-have)**
   - 7.1 `?scenario=2&step=3&sigma_t=12&sigma_pos=20` deep-links a
         specific state. Useful for rehearsing the pitch.

### Considerations

- **💡 NOTE: the existing `transit` phase blend (camera pans between
  scenarios) is being deleted.** This is intentional — operator
  controls the map, not the playback. Don't try to preserve it.
- **💡 NOTE: scenarios array is bounded.** Limit to 5 in the UI; if
  the JSON has more, show the top 5 by `priority_rank`. Anything
  more clutters the sidebar.
- **💡 NOTE: phase durations are *animation* durations, not pacing.**
  The presenter advances at their own speed; durations only matter
  during the animation itself.
- **⚠ Keyboard shortcuts.** Add `→` for NEXT, `←` for PREV, `space`
  for AUTO toggle. Pitch flow uses keyboard, not mouse.

### ⚠ HUMAN INPUT NEEDED

1. **Which 5 scenarios?** The current `events.json` has scenarios like
   `scenario_gunshot_mix`, `scenario_gunshot_preprocessed`,
   `scenario_tank_preprocessed`, `scenario_missile_mix`. Suggested
   curated set:
   - ① clean gunshot (low σ_t, low σ_pos) → STRIKE
   - ② degraded-timing gunshot (mid σ_t, low σ_pos) → borderline
   - ③ GPS-denied gunshot (low σ_t, high σ_pos) → wide ellipse
   - ④ tank (high severity) → STRIKE even at mid CEP
   - ⑤ missile launch (high severity, high priority) → STRIKE
   The team probably needs to either select 5 from the existing
   `events.json` or generate 5 synthetic ones for clarity. Confirm.
2. **Card thumbnail style.** Mini topdown of drones + dot? Just a
   geometric symbol per geometry class? Suggested: a 60×60 SVG
   showing three drone dots + a marker dot at the source.
3. **Keyboard shortcuts.** Confirm `→ / ←` for NEXT/PREV.

### Acceptance criteria

- 5 scenario cards render in the sidebar.
- Clicking a card switches the map to that scenario at phase 0.
- ▶ NEXT advances one phase at a time; PREV steps back.
- ⏵ AUTO advances phases automatically with the dialled-in durations.
- ⟲ RESET returns the current scenario to phase 0.
- Each card's CEP50 + action chip reflect the scenario's defaults.

---

## Session 8 — Live error sliders + backend recompute

### Goal

Two sliders (σ_t, σ_pos) in the right rail. Dragging them re-runs the
TDOA localisation in real time and updates the cloud, CEP50, action
chip, and ROE banner. The math runs in Python via a small Flask backend
so there's a single source of truth.

### Files touched

- New: `triangulation/server.py` (Flask app)
- Modified: `ui/index.html` (sliders + fetch logic)
- Modified: `triangulation/locate.py` (expose `localize_scenario` with
  override sigmas)
- Modified: `triangulation/__init__.py` (export `server`)

### Architecture

```
Browser slider drag
       │ debounce ~120 ms
       ▼
   fetch /api/scenarios/{id}?sigma_t_ms=X&sigma_pos_m=Y
       │
       ▼
   Flask backend (triangulation/server.py)
       │
       ├── reads events.json (cached in memory)
       │
       ├── overrides per-event sigma_t_ms / position_error_m
       │    on every row of the requested scenario
       │
       ├── calls localize_scenario(group, ..., mc_samples=120)
       │    with the modified events (note: mc=120 for live, not 400)
       │
       └── returns the recomputed entry as JSON
       │
       ▼
   Browser updates state.scenarios[i] in place, redraws
```

The backend reuses **the exact same `localize_scenario` function** that
the offline pipeline uses, so there's no risk of the live recompute
disagreeing with the JSON on disk.

### New endpoints

| Endpoint | Returns |
|---|---|
| `GET /api/scenarios` | list of all scenarios with default sigmas |
| `GET /api/scenarios/<id>` | single scenario with default sigmas |
| `GET /api/scenarios/<id>?sigma_t_ms=X&sigma_pos_m=Y` | live recompute |
| `GET /api/events?scenario=<id>` | raw events for that scenario (debug) |
| `GET /` | serves `ui/index.html` directly (no separate http server) |
| `GET /<file>` | serves `ui/<file>` (CSS, JS, images, etc.) |

### Right-rail slider visuals

```
┌─ Timing error σ_t ────────────────────────────────────┐
│  ●─────────●─────────────────●─────────────● 20 ms   │
│  0.1 µs   1 µs    100 µs   1 ms          20 ms      │
│  GPS/PTP  good    NTP      cheap         unsynced   │
│  ┃                ┃         ┃              ┃        │
│  └─ current: 6.6 ms ────────────────┘               │
└──────────────────────────────────────────────────────┘

┌─ Position error σ_pos ────────────────────────────────┐
│  ●─────●──────────●──────────●─────────────● 50 m    │
│  0 m   1 m       5 m        15 m            50 m    │
│  GPS   RTK       IMU/30s    IMU/2min   sustained    │
└──────────────────────────────────────────────────────┘
```

Each slider is **log-scaled** for σ_t (sub-µs to ms span isn't useful
linearly) and **linear** for σ_pos (0 to 50 m is fine linear). Marker
positions correspond to operational regimes — these are pitch-bait
because a defense judge knows immediately what they mean.

A tiny inline SVG chart below the sliders shows the **error vs σ
curve** for the current scenario — the "money curve" from the
defensehackathon prototype, scaled down. A red dot marks the current
operating point. As the slider moves, the dot moves; as σ goes
inside/outside the STRIKE zone, a coloured band lights up.

### Tasks

1. **Backend: `triangulation/server.py`**
   - 1.1 Flask app with the endpoints above.
   - 1.2 Load `events.json` once at startup; cache `_group_by_scenario`
         result in memory.
   - 1.3 `_apply_sigma_overrides(events, sigma_t_ms, sigma_pos_m)`
         helper: returns a new list where every row in the scenario
         has the σ values overridden (if not 0/null).
   - 1.4 Endpoint handler calls `localize_scenario(modified_events,
         mc_samples=120)` and returns the resulting dict.
   - 1.5 Cache recent recomputes (LRU, max 50 entries) so the same
         slider value doesn't recompute twice.
   - 1.6 CLI: `python -m triangulation.server --port 5050 [--host
         0.0.0.0]`. Default port 5050 to avoid clashing with the
         existing Dash viewer on 8060.

2. **`localize_scenario` argument additions**
   - 2.1 Add `sigma_t_override_ms: float | None = None` and
         `sigma_pos_override_m: float | None = None` to the function
         signature.
   - 2.2 When non-None, apply to the events before MC. Document the
         interaction with existing per-row σ values: override
         *replaces*, not adds.

3. **Frontend: slider components**
   - 3.1 Two `<input type="range">` inputs in the right rail. Log
         scale for time; linear for position. Show numeric readout.
   - 3.2 Reference-regime markers under each slider (tick marks with
         labels).
   - 3.3 Debounce slider input to ~120 ms before firing fetch.
         Drag-while-fetching is fine; the last fetch wins.

4. **Frontend: fetch + state update**
   - 4.1 `async function recomputeCurrentScenario()` fires
         `/api/scenarios/<id>?...` and patches `state.scenarios[i]`
         with the response.
   - 4.2 The renderer automatically picks up the new cloud, target,
         CEP, action chip on the next animation frame.
   - 4.3 Loading indicator: a 1 px shimmer along the slider track.
   - 4.4 Fetch errors silently revert to the last good value; one
         log line per failure.

5. **Money-curve inline chart**
   - 5.1 100 × 60 SVG below the sliders. Log-log axes (clock σ vs
         error). Pre-baked points: backend has another endpoint
         `/api/scenarios/<id>/sweep` returning ~15 (σ, CEP) pairs at
         the current geometry.
   - 5.2 Red dot at the current operating point updates with the
         slider.
   - 5.3 Coloured background bands for STRIKE / RECON / SEARCH zones
         (using the same thresholds as the policy module).

6. **Reset to defaults**
   - 6.1 A small "↺ default σ" button next to each slider. Clicks
         restore the slider to the scenario's original per-drone
         maximum from the JSON.

### Considerations

- **💡 NOTE: when σ overrides are applied, they're applied to *every
  drone* in the scenario.** Per-drone override is more flexible but
  far worse for UI clarity. The slider is asking "what if all the
  drones had this much error?" not "what if drone_2 specifically did?"
- **💡 NOTE: MC=120 for the live recompute, not 400.** Quality stays
  fine (CEP estimate is stable within a few % at 120). Latency drops
  to ~15–30 ms per call. Saves the demo from feeling sluggish.
- **💡 NOTE: cache recent recomputes** (LRU by `(id, σ_t, σ_pos)`)
  — sliders often retrace the same path during a pitch.
- **⚠ Same backend, same Python process** serves the UI HTML. Don't
  make people start two services. Flask `send_from_directory`
  handles the static files.
- **⚠ CORS isn't an issue** if the static files are served by the
  same Flask app (preferred). If running the UI under a separate
  http.server, add a permissive `Access-Control-Allow-Origin`.

### ⚠ HUMAN INPUT NEEDED

1. **Slider ranges and scale.** Suggested: σ_t **log** from 0.1 µs to
   20 ms; σ_pos **linear** from 0 to 50 m. Confirm.
2. **Regime markers.** Suggested labels:
   - σ_t: `GPS/PTP (1 µs)`, `good NTP (500 µs)`, `cheap NTP (3 ms)`,
     `unsynced (≥ 10 ms)`
   - σ_pos: `GPS (1 m)`, `RTK (0.1 m)`, `IMU 30 s (5 m)`,
     `IMU 2 min (15 m)`, `sustained denial (50 m)`
   Confirm wording (especially for the IMU drift bands).
3. **MC sample count for live.** Suggested 120 (target 30 ms). The
   tradeoff is "ellipse jitters slightly as σ moves vs slider feels
   sluggish". Confirm preference.
4. **Should the money-curve inline chart be in v1?** Adds ~2 hours.
   Suggested: yes — judges read it instantly and it's the single
   most credibility-building element. Confirm.

### Acceptance criteria

- `python -m triangulation.server` starts on port 5050.
- `http://localhost:5050/` serves the existing tactical UI.
- σ_t and σ_pos sliders in the right rail update CEP50, cloud, target
  position, action chip within ~150 ms of slider stop.
- Reset button restores the scenario default.
- Money-curve mini-chart present; red dot tracks slider.
- ROE banner colour and text update live as the action flips.

---

## Session 9 — SEARCH action + multi-drone area sweep

### Goal

When CEP50 is too large for a point-target response, the ROE engine
emits a new `SEARCH` action. The respond phase then dispatches **all
three drones** to spread across the confidence ellipse in a grid /
spoke pattern. Visual: three responders fanning out, each sweeping
their assigned subzone. Telemetry mentions "SEARCH PATTERN initiated ·
sweeping XXX m²".

### Files touched

- Modified: `triangulation/policy.py` (extend `decide()`)
- Modified: `triangulation/locate.py` (no functional change; output
  field values change)
- Modified: `ui/index.html` (multi-responder rendering in `respond`
  phase, telemetry strings)
- Modified: `SESSIONS.md` (mark Session 1 acceptance criteria as
  extended)

### Architecture

```
policy.decide(cep50, gdop, label, conf):
  if conf < HOLD_FLOOR:        return HOLD
  if cep50 < STRIKE_CEP_MAX
     and gdop < STRIKE_GDOP_MAX
     and label in STRIKE_ELIGIBLE:
                                return STRIKE
  if cep50 < SEARCH_FLOOR:     return RECON
                                return SEARCH        ← NEW
```

For the visuals:

```
For SEARCH action, the respond phase animates:

  1. All three drones break formation simultaneously.
  2. Compute a 3-point sweep pattern inside the 95% ellipse:
       - drone_1 → ellipse centre
       - drone_2 → ellipse centre + 0.6·major_axis along +axis
       - drone_3 → ellipse centre + 0.6·major_axis along −axis
     (or a spoke pattern with the three points equiangular around
      the centre — pick the more visually obvious layout)
  3. Animate all three arcing to their sweep points.
  4. On arrival, each drone shows a small "scanning" pulse for ~1 s.
  5. Final state: three responders parked at sweep points, plus an
     overlay polyline tracing the sweep coverage.
```

The existing `state.responders[]` slot already supports multiple
responders — Session 3 designed it as a list. SEARCH just populates
three entries instead of one.

### Tasks

1. **Backend: extend `policy.decide()`**
   - 1.1 Add `SEARCH` to the `Action` literal type.
   - 1.2 Add `SEARCH_FLOOR` constant (suggested: CEP50 > 50 m → SEARCH).
   - 1.3 Add `severity = "low"` for SEARCH (not actionable, just
         searching).
   - 1.4 Add `weapons_release_required = false` for SEARCH.

2. **Backend: expose search pattern in JSON**
   - 2.1 When action is SEARCH, add a `search_pattern` field to the
         output entry: `[{lat, lon, role}, ...]` with 3 sweep points
         derived from the ellipse axes.
   - 2.2 Add `search_pattern_xy_local` for completeness.
   - 2.3 New helper in `policy.py`: `search_points(center_xy,
         major_axis_xy, minor_axis_xy, n=3) -> list[(x, y)]`.

3. **Backend: extend test cases**
   - 3.1 Verify a high-σ scenario triggers SEARCH.
   - 3.2 Verify `search_pattern` has 3 entries within the ellipse.

4. **Frontend: action chip colour**
   - 4.1 Add `--search` colour (suggested: `#1e9af0` blue — distinct
         from STRIKE red and RECON amber).
   - 4.2 Update chip styling switch in `renderDecide()` and the
         sidebar cards.

5. **Frontend: multi-responder rendering**
   - 5.1 In `respond` phase, when action is SEARCH:
         - Read `entry.search_pattern_xy_local`
         - Spawn 3 responders simultaneously (vs 1 for STRIKE/RECON)
         - Animate each on its own arc to its sweep point
   - 5.2 On arrival, each shows a "scanning" pulse (existing
         `emitPulse` helper).
   - 5.3 Optional overlay: a faint dashed polyline drawing the sweep
         coverage between the three points.

6. **Frontend: SEARCH telemetry strings**
   - 6.1 Add to the `TELEMETRY` table (from Session 4):
       ```js
       SEARCH: [
         { at: 0.05, msg: "SEARCH PATTERN initiated · 3 drones deploying",  lvl: "warn" },
         { at: 0.35, msg: "Drones on station · sweep underway",              lvl: "warn" },
         { at: 0.70, msg: "No contact at primary point · expanding search",  lvl: "warn" },
         { at: 0.92, msg: "Search incomplete · requesting more sensors",     lvl: "hostile" }
       ]
       ```
       (Adjust wording with user — see Human Input.)

7. **Frontend: HOLD-vs-SEARCH chip**
   - 7.1 HOLD remains for "no usable fix" (confidence floor).
   - 7.2 SEARCH replaces HOLD for "fix is real but too imprecise".
   - 7.3 Make sure the action chip clearly distinguishes them
         visually so judges don't conflate them.

### Considerations

- **💡 NOTE: 3 drones spreading vs 1 drone arcing is a 3× richer
  visual.** Don't water it down to "one drone moving more slowly".
  The multiple bodies are the point.
- **💡 NOTE: ellipse-aware sweep**, not grid. The sweep points must
  align with the major axis of the ellipse — that's *why* the
  visual is interesting. A square grid in a long thin ellipse looks
  wrong; a spoke pattern aligned to the axis looks right.
- **💡 NOTE: SEARCH is recoverable.** Don't render it as "the
  system failed". The narrative is "the system knew it didn't have
  a confident fix and dispatched proportionate resources to gather
  more information." That's a feature, not a bug.
- **⚠ Backwards compatibility.** Existing consumers of
  `recommended_action` will see a new enum value (`SEARCH`). They
  shouldn't crash — but if any downstream code assumes a closed
  set, it must be updated.

### ⚠ HUMAN INPUT NEEDED

1. **CEP50 threshold for SEARCH.** Suggested: > 50 m → SEARCH; ≤ 50 m
   and > 10 m → RECON; ≤ 10 m → STRIKE. Confirm or override.
2. **Sweep pattern.** Suggested: 3-point spoke aligned with ellipse
   major axis. Alternative: equilateral triangle around centre. Pick
   one.
3. **Number of sweep drones.** Suggested: 3 (every drone). Could be
   more if more drones exist. Confirm "all drones, every time" vs
   "at least 2".
4. **Sweep telemetry copy.** The draft above is generic. Lean more
   military ("SECTOR SEARCH · ZONE BRAVO"), more operational
   ("Drones on station, sweep underway"), or more diagnostic ("Cloud
   area exceeds 5000 m², expanding search radius"). Confirm tone.

### Acceptance criteria

- `policy.decide(cep50=80, gdop=2, label="gunshot", confidence=0.4)`
  returns `Decision(action="SEARCH", ...)`.
- `localizations.json` entries with high CEP50 have
  `recommended_action == "SEARCH"` and a 3-element
  `search_pattern_xy_local`.
- UI in `respond` phase shows three responders spreading to the
  sweep points when action is SEARCH.
- Action chip is distinct from STRIKE/RECON/HOLD in colour and
  label.
- Telemetry log for SEARCH plays the SEARCH-specific strings.

---

## Cross-session conventions (Part 2)

- **All sliders are log-scale where the operational regimes span
  decades.** Linear sliders compress the interesting region. σ_t is
  log; σ_pos is linear (0–50 m is one decade, fine linear).
- **All recomputes go through the existing Python pipeline.** Don't
  port the math to JS. The backend is cheap; latency is fine.
- **Phase advances are operator-driven by default**, autoplay is a
  toggle, never the default. The pitch needs pacing control.
- **Action chips and ROE banner are the same colour-coding everywhere**:
  STRIKE red, RECON amber, SEARCH blue, HOLD grey. Don't deviate
  in any rendering.
- **Telemetry copy stays consistent across actions.** Each action's
  4 lines hit similar beats (dispatch / arrival / progress / closure)
  so the judge's eye learns the pattern.

## What this leaves on the table

- **Hand-drawn sweep paths inside the ellipse.** SEARCH currently
  shows 3 points; a fuller demo would show curves traced by each
  drone. ~2 hours of extra work; nice but not essential.
- **Replay history.** When σ has been moved and recomputed many
  times, there's no way to step back through the trajectory. Could
  add an undo stack — out of scope here.
- **Cross-scenario priority elevation.** With 5 scenarios in the
  sidebar, dragging σ to extreme on scenario 1 doesn't change
  scenario 4's priority. That'd be more realistic but is gold-plating
  beyond the demo budget.
