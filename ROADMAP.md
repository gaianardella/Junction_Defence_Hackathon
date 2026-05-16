# ROADMAP — Single Coherent Build Sequence

One ordered list of sessions, essential first, mesh nice-to-haves
last. Each entry is short — full implementation specs live in the
companion docs:

- `SESSIONS.md` — Sessions 1–6 (foundation)
- `SESSIONS_INTERACTIVE.md` — Sessions 7–9 (interactive UI)
- `MESH_PLAN.md` — Mesh code modules (C1–C10)

This file says **what to do next, in what order**. The companion docs
say **how to do each one**. Where a session is fully new (not in the
companion docs), its full spec lives at the bottom of this file under
"New session specifications".

## Current state

✅ Sessions 1, 2, 3 complete.
🛠 Session 4 in progress (recon imagery + telemetry log).
⏳ Everything else below.

## How to read this list

Sessions are grouped into three tiers:

- **TIER 1 — ESSENTIAL.** Without these the demo is incomplete.
  Build in order; don't skip.
- **TIER 2 — STRONG.** Big force-multiplier additions. Most of the
  mesh story lives here. Do these if you have 18+ hours after Tier 1.
- **TIER 3 — NICE TO HAVE.** Genuinely optional. Cut first if time
  disappears.

Each entry follows the same shape:

```
N. SESSION TITLE                                    (≈X h, spec: <doc>)
   One-sentence goal.
   Key tasks: …
   Why it matters: …
```

## Architectural invariants (apply to every session)

These don't change as you build. Treat as hard rules:

1. **`triangulation/` never imports from `mesh/`.** Use indirection
   modules (`triangulation/clock.py`) at integration points.
2. **`mesh/` never imports from `triangulation/`.** Data flows the
   other way only.
3. **Flask backend (`triangulation/server.py`) is the only place
   that touches both packages.**
4. **All new JSON fields are additive.** Existing consumers must keep
   working.
5. **The UI never recomputes math.** Sliders fire HTTP; Python answers.
6. **All mesh code is sim-runnable.** Real hardware optional; demo
   must run on `SimTransport` alone.

---

# TIER 1 — ESSENTIAL (the irreducible demo)

The first thirteen items in order. After these, the demo is operator-paced,
live-tunable, tells a complete kill chain with a graceful-degradation
story, includes a free-play sandbox for the judge to touch, lets
the presenter kill any drone live on audience cue, makes every phase
visually self-explanatory, shows the system handling non-threats
correctly too, surfaces the mesh bandwidth-efficiency numbers
in a permanent always-on side panel, AND has a fully reactive
"Live Ops" tab where events are dropped on the map and the system
responds in real time. Skip nothing.

## 1. Finish Session 4 — Recon imagery + telemetry log     (≈1 h, spec: `SESSIONS.md` §4)

Complete the in-progress work: the placeholder camera-feed popup on
RECON, plus the streaming telemetry lines `ENGAGING → IMAGING →
POSITIVE ID → REPORT` keyed to phase progress.

**Don't leave half-done.** Even one missing telemetry line breaks the
"system is talking back" feeling. Once this lands, the auto-rotating
playback flow is fully built — the next sessions replace that flow
with operator control.

## 2. Session 7 — Tab bar + phase stepper                  (≈4 h, spec: `SESSIONS_INTERACTIVE.md` §7)

Replace auto-advancing playback with operator control. Six tabs at
the top: five preset scenarios (`① Gunshot · arc`, `② Degraded`,
etc.) plus a `🧪 Sandbox` placeholder (gets filled in at step 4).
Bottom controls: `⏪ PREV ▶ NEXT ⏵ AUTO ⟲ RESET`.

**Key tasks:**

- Add tab bar + phase-control bar to `ui/index.html`.
- Replace `tickPlayback`'s transit/listen/localize/hold logic with
  phase-step state (`state.step`, `state.stepProgress`,
  `state.autoplay`).
- Each tab card shows: label, CEP50, action chip, priority dot.
- Keyboard shortcuts: `→ / ←` step, `space` toggle autoplay,
  `1-6` tab switch.

**Why it matters:** the presenter is now in control of pacing. A
judge can ask a question and the demo waits.

**Important addendum for items 6–7:** the tab framework needs one
small bit of foresight — a single tab can host **multiple scenes**
(a scene sequence) rather than just one scenario. Build that into
the state shape now (`state.tabs[i].scenes[]` with a current scene
index) so item 7 doesn't require a rework. Single-scene tabs just
have one entry in `scenes[]`.

## 3. Session 14 — Source icon + acoustic emission visuals (≈3 h, spec: "New session specifications" below)

The big legibility upgrade. At DETECT phase start, a small icon
appears at the source's *true* position, blinking, classifier-coloured
(red for threats, green for ambient, amber for unknown). Concentric
rings emanate from the icon — every ~200 ms a new ring expands and
fades, exactly like sound radiating outward. Drone lights tie to
ring-arrival timing instead of firing all at once. At LOCALIZE, rings
stop; cloud fades in. The judge now sees a clear cause→effect chain
(world emits sound → system detects → system computes location →
visible error between icon and cloud center).

Includes a phase-narration subtitle bar at the bottom of the map —
one line of plain English per phase ("Acoustic signature detected by
3 sensors", "Triangulating — CEP50 reducing", "ROE: STRIKE authorized").
Presenter doesn't have to narrate every beat; the UI does.

**Why it matters:** directly fixes the "messy and hard to follow"
complaint. Every subsequent demo benefits because every tab uses
this rendering. Spend the 3 hours here before Session 8 so live
slider drags drive the new visuals, not the old ones.

## 4. Session 8 — Live error sliders + Flask backend       (≈4 h, spec: `SESSIONS_INTERACTIVE.md` §8)

Two sliders in the right rail: σ_t (log-scaled, 0.1 µs → 20 ms) and
σ_pos (linear, 0–50 m). Dragging them re-runs the localiser in real
time. Math runs in Python via a new `triangulation/server.py` Flask
app so there's a single source of truth.

**Key tasks:**

- New `triangulation/server.py` with endpoints
  `/api/scenarios`, `/api/scenarios/<id>`,
  `/api/scenarios/<id>/sweep`, plus static-file serving for
  `ui/index.html`.
- Extend `localize_scenario` with `sigma_t_override_ms` and
  `sigma_pos_override_m` kwargs.
- Frontend: debounced fetch on slider change (120 ms), MC=120 for
  live recompute (down from 400).
- Money-curve mini-chart below the sliders (log-log error vs σ,
  red dot tracks slider).
- Reference-regime tick marks under sliders.

**Why it matters:** the judge says "what if timing were 3× worse?"
and the cloud blooms in real time. Reads as immediate technical
credibility.

## 5. Session 10 — Sandbox tab                             (≈4 h, spec: `SESSIONS_INTERACTIVE.md` §10)

The sixth tab `🧪 Sandbox`: drag drones and source anywhere, tune σ
with the same sliders, watch the cloud + estimate update in real
time. Truth (user-placed source) is visible; estimate is computed;
the distance between them is the actual error, drawn as a dashed
line with a metres label.

**Key tasks:**

- New `triangulation/sandbox.py`: `build_events(drones, source,
  sigma_t_ms, sigma_pos_m) -> events_list` synthesises a JSON event
  group from a geometry config.
- New `POST /api/sandbox` endpoint that calls `build_events` then
  `localize_scenario`.
- Pointer-drag handlers on the entity DOM layer; throttled fetch
  during drag.
- "OPEN IN SANDBOX" button on scenario tabs to copy their geometry.

**Why it matters:** hand the laptop to a judge. Hackathons are won by
the team whose demo the judge *plays with* rather than just *watches*.

## 6. Session 9 — SEARCH action + multi-drone sweep        (≈3 h, spec: `SESSIONS_INTERACTIVE.md` §9)

Extend the ROE policy with a fourth action: when CEP50 > 50 m, emit
`SEARCH`. In the respond phase, all three drones spread out to sweep
points aligned with the ellipse's major axis. Visual is three bodies
moving instead of one — much richer.

**Key tasks:**

- Extend `policy.decide()` with the SEARCH branch + threshold
  constants (`SEARCH_FLOOR`).
- New helper `policy.search_points(center, cov, n=3)` → 3 sweep
  positions along the major axis.
- Output JSON gains `search_pattern_xy_local` and
  `search_pattern_latlon` when action is SEARCH.
- Frontend: in `respond` phase with SEARCH, spawn 3 responders
  arcing to their sweep points.
- New action chip colour (`--search: #1e9af0` blue).
- SEARCH-specific telemetry strings.

**Why it matters:** geometry-aware response. The "what if the drones
are in a line" judge question becomes an animated answer. Also: this
is the action that the 2-drone fallback (item 6) will fire in the
narrative arc.

## 7. Session 11 — 2-drone bearing-only localization        (≈3 h, spec: "New session specifications" below)

Real math, not a fake. With only two drones, TDOA gives a hyperbola,
not a point. Implement that as a first-class fix type alongside the
existing 3-drone ellipse fix. The output is a curve (the hyperbola
locus) plus a wedge (the hyperbola swept across the input
uncertainty). ROE policy automatically downgrades 2-drone fixes to
SEARCH — you can't STRIKE on a curve.

**Key tasks:** see §"New session specifications" below.

**Why it matters:** graceful degradation is a defense judge magnet.
The honest answer to "what if you lose a sensor?" is more impressive
than any single 3-drone demo could be. This session is the technical
backbone of item 7.

## 8. Session 13 — Kill-drone button (live resilience)      (≈3 h, spec: "New session specifications" below)

A persistent "💀 KILL drone_X" pill row in the right rail. Press it
anytime, in any tab, on any scene. The killed drone gets a red ☓
overlay + dimmed icon and is dropped from the local roster. The
backend immediately re-localises with the reduced roster: 3 → 2
drones flips the fix from ellipse to hyperbola+wedge (uses
Session 11), 2 → 1 produces an "INSUFFICIENT SENSORS" banner, 1 → 0
goes pure-patrol. ROE chip flips live as the action downgrades. A
"🔄 RESET KILLS" button restores defaults; switching tabs auto-resets.

**Key tasks:** see §"New session specifications" below.

**Why it matters:** the audience-cue demo. Presenter says "any of
you call out which drone dies?" — judge yells "drone_2" — KILL
button pressed — system gracefully degrades on screen. Beats any
scripted scene because it's visibly reactive, not pre-baked. Also
the infrastructure that Session 12's narrative scene-2 drone-loss
beat reuses (no duplicate code path).

## 9. Session 15 — Ambient (wildlife) triangulation tab    (≈3 h, spec: "New session specifications" below)

A dedicated tab — `🐺 Wildlife · ambient` — that runs a bird/dog/
crickets scenario through the full pipeline. Everything is green:
source icon, emitted rings, confidence cloud, action chip. ROE
returns a new `MONITOR` action: high-confidence non-threat
classification, deliberate non-engagement. No responder dispatched.
The bird WAV plays during DETECT (audio addon wiring). Tells the
"smart classifier" story in 6 seconds: hear the bird, see the
system localize it, see the system *choose not to engage*.

**Why it matters:** demonstrates discriminative classification
without requiring an ML refactor. Differentiates ambient from
HOLD (low confidence) and INSUFFICIENT_SENSORS (missing drones) —
introduces the fourth action class. Reuses Session 14's visual
machinery; just swaps the color path.

## 10. Session 12 — Multi-scene narrative tab               (≈4 h, spec: "New session specifications" below)

Replace the boring `① Gunshot · clean` single-scene tab with a
4-scene operational arc that uses everything you've built (scene 2's
drone loss is implemented as a scripted call to Session 13's kill
mechanism):

```
Scene 1 (PATROL → STRIKE)        Clean gunshot fix → STRIKE authorized.
Scene 2 (STRIKE OUTCOME)         Strike runs; recon drone is "lost" in
                                  the engagement; roster shrinks to 2.
Scene 3 (DEGRADED DETECTION)     Second gunshot. Only 2 drones receive.
                                  Bearing-only fix (item 6); hyperbola
                                  + wedge appear. CEP undefined.
Scene 4 (TARGETED SEARCH)        ROE auto-downgrades to SEARCH. The two
                                  remaining drones execute a targeted
                                  sweep along the hyperbola wedge.
```

Operator clicks ▶ NEXT to walk through scenes. Each scene preserves
its own PATROL → DETECT → LOCALIZE → DECIDE → RESPOND → COMPLETE
phase machinery.

**Key tasks:** see §"New session specifications" below.

**Why it matters:** this single tab tells the whole pitch. Detection
→ decision → action → cost → degradation → adaptive response. It
demonstrates every piece of the system in 90 seconds while telling
a coherent operational story instead of disconnected vignettes.

## 11. Session 6 — Mesh narrative docs + bandwidth budget  (≈1.5 h, spec: `SESSIONS.md` §6, with addendum)

One markdown page + diagram explaining what depends on the mesh.
This is a pitch slide, not code. Three callouts: time-synced
timestamps, target coords + confidence, recon imagery return path.
Plus a graceful-degradation matrix.

**Addendum: bandwidth budget table.** Add a table that shows the
engineering math behind the "compressed images when RF allows"
claim. Sample numbers:

| Traffic class | Size | Rate | Throughput | Time on a 150 KB/s mesh link |
|---|---|---|---|---|
| Telemetry JSON (status) | 200 B | 10 Hz | 2 KB/s | ~13 ms per frame |
| Target coords + cloud   | 1.5 KB | 1 Hz | 1.5 KB/s | ~10 ms per fix |
| Compressed recon JPEG (320×240, q40) | 15 KB | on-demand | — | ~0.1 s per image |
| Raw RGB equivalent | 230 KB | on-demand | — | ~1.5 s per image (cut by 15×) |
| HMAC overhead | 16 B/frame | every frame | ~10% | negligible |

This makes the bandwidth-efficiency story credible at a glance
instead of hand-wavy.

**Why it matters:** even before any mesh code exists, this page
defends the team against "you're submitting to a mesh challenge but
where's the mesh?" The doc says: we built the application that needs
the mesh; here's exactly what crosses it, how big it is, and how
long it takes.

## 12. Session 16 — Mesh bandwidth side panel              (≈2 h, spec: "New session specifications" below)

The Kova-points moment. A permanent strip in the top bar showing live
mesh bandwidth telemetry sourced from `mesh/metrics.py`:

```
MESH 64 B   /   JSON would be 392 B   /   saved 84%   |   TOTAL 2.4 KB sent · 28 KB saved
```

Updates on every scenario activation. Click any number → side-by-side
popover with the actual 32-byte hex dump next to the equivalent JSON
row, taken straight from `mesh/payload.py`. Bullet-proofs against the
"but this is just packing some bytes" reaction — judges see the real
wire format vs the real JSON it replaced.

**Why it matters:** Kova weights bandwidth efficiency at 33% of
judging. The mesh code already does the compression (`mesh/payload.py`,
84% on tactical events, 99% on loc summaries). Without this panel
those numbers stay buried in a benchmark CLI. With it, the bandwidth
story is permanently visible during the pitch — judges absorb it
passively while you narrate other things.

## 13. Session 18 — Live Ops tab (live event injection)    (≈8 h, spec: `SESSIONS.md` §18)

The reactive demo. New tab `🎮 LIVE OPS`. N drones (default 5) patrol
the map. Sidebar has drop-event buttons (`🔫 GUNSHOT`, `🚜 TANK`,
`🚀 MISSILE`, `🦌 WILDLIFE`). Click a button → click the map →
event drops at real lat/lon. Backend computes per-drone detection
times from real geometry, picks the 3 closest alive drones, runs
`localize_scenario` or `solver_2drone` based on alive count, returns
the result. UI animates the response in real time. Kill drones live
on audience cue → 3 → 2 alive → ellipse collapses to hyperbola+wedge,
ROE downgrades to SEARCH live. Classifier swap-in slot for the ML
team (`PerfectClassifier` default; `MLClassifier` stub).

**Key tasks:** see `SESSIONS.md` §18 for the full 23-item subtask list.

**Why it matters:** the "hand-the-laptop" tab. Scripted tabs are
rehearsed pitch content; this is the proof the system actually runs
live. Reuses every prior Tier 1 piece (sandbox, sliders, 2-drone
math, kill button, source icons) and weaves them into one coherent
reactive simulation. Also the natural home for the ML
misclassification narrative when the classifier ships.

---

# TIER 2 — STRONG (mesh story, integrated)

The mesh stack, built top-to-bottom in the order that keeps the demo
running after every session. Each session ends with the demo strictly
better than it started, never half-broken. Stop here if you've only
got 8–15 hours after Tier 1.

## 14. Mesh C1 — Transport interface + SimTransport        (≈4 h, spec: `MESH_PLAN.md` §C1)

The mesh foundation. Defines `Transport` (a Protocol class) with
`send`, `register_receiver`, `local_id`, `neighbours`, `rssi_to`,
`set_channel`. Ships an in-process `SimTransport` that satisfies it
with configurable per-link loss, delay, and RSSI.

**Why it matters:** the swap-in/swap-out boundary that lets the
entire demo run without USB adapters.

## 15. Mesh C2 — Frame format + HMAC + replay window       (≈3 h, spec: `MESH_PLAN.md` §C2)

The protocol's spine. HMAC-SHA256 (truncated to 16 B) with a
pre-shared key. Per-source sliding replay window of 64 sequences.

**Why it matters:** "your mesh is secure" is a one-line claim that
needs a one-line answer. HMAC is that answer.

## 16. Mesh C3 — Routing: flood + dedup + TTL              (≈2 h, spec: `MESH_PLAN.md` §C3)

`MeshNode` runtime that wraps a Transport + frame layer. Flood
forward, dedup by `(src, seq)`, decrement TTL.

**Why it matters:** now the mesh actually *does* something.

## 17. Bridge — Demo orchestrator                          (≈1 h, spec: bottom of file)

A single command brings the whole demo up: 3 mesh node processes +
Flask backend + browser. Ctrl-C clean shutdown.

**Why it matters:** demo-day startup goes from a juggling act to one
command.

## 18. Mesh C5 — Priority queue                            (≈1 h, spec: `MESH_PLAN.md` §C5)

Two-class send priority on `MeshNode`. HIGH (coords, status, NTP,
control) preempts BULK (imagery, telemetry).

**Why it matters:** explains why the operator gets a target
coordinate to act on *before* the recon image finishes loading.

## 19. Mesh C7 — UI mesh panel (topology + RSSI)           (≈3 h, spec: `MESH_PLAN.md` §C7 + bridge below)

## 20. Session 17 — Packet flight FX (toggleable)          (≈2.5 h, spec: "New session specifications" below)

Atmospheric polish that rides on top of the mesh topology panel from
item 18. When `BANDWIDTH FX: on` in the top bar, every mesh
transmission spawns a small coloured capsule that travels along the
relevant edge over ~400 ms. Capsule colour by payload kind (green =
tactical, blue = loc summary, purple fringe = HMAC overhead), width
∝ byte count, hover shows packet details + small hex preview. Default
**off** so it doesn't compete for attention during non-mesh narration.

**Why it matters:** the mesh feels alive when the toggle is on. Lets
the presenter say "watch — every dot you see is 32 bytes" then turn
it off to focus the audience back on triangulation or the kill button.
The side panel from item 12 keeps the running numbers visible
regardless. This session is *atmosphere*, not credibility — the
numbers came from item 12.

The single moment where mesh meets UI. New sidebar panel showing
live topology, per-link RSSI, frame counters. Per-node "BLOCK /
UNBLOCK" toggle triggers the foil-reroute scene in sim. Mesh events
flow into the existing event log with a distinct (cyan) class.

**Why it matters:** judges *see* the mesh working. The BLOCK button
is the signature mesh demo moment.

## 21. Mesh C4 — Progressive image transport               (≈4 h, spec: `MESH_PLAN.md` §C4)

JPEG q20 thumbnail (80×60, ~1.5 KB) first; JPEG q40 full
(160×120, ~10 KB) refinement second. Chunked into 512-byte
fragments.

**Why it matters:** bandwidth story backed by real traffic.

## 22. Bridge — Recon imagery actually traverses the mesh  (≈1 h, spec: bottom of file)

Replace Session 4's "show popup immediately" with "open SSE,
fill popup as chunks arrive". Add a "via mesh" badge to the popup.

**Why it matters:** unifies Session 4 with item 15's transport.

## 23. Mesh C6 — Mesh-NTP                                  (≈4 h, spec: `MESH_PLAN.md` §C6)

Drone-to-drone clock sync over the mesh. 4-timestamp exchange at
2 Hz; per-pair EWMA; swarm-consensus offset is the median.

**Why it matters:** the innovation headline.

## 24. Bridge — Mesh-NTP corrects acoustic timestamps      (≈1 h, spec: bottom of file)

Triangulation pipeline learns to consult the mesh's clock offsets.
With drift injected, mesh-on keeps CEP tight; mesh-off blows it up.

**Why it matters:** the headline pitch line becomes demonstrable
on screen.

---

# TIER 3 — NICE TO HAVE (cut first if time disappears)

These don't break the demo if cut. Build them only after Tier 2 is
solid.

## 25. Mesh C8 — Jammer triangulation                      (≈5 h, spec: `MESH_PLAN.md` §C8)

Reuse the TDOA localiser with RSSI in place of timing. Three drones
report `{rssi, channel, time}` for an unknown emitter; system
triangulates the jammer with a CEP cloud (`1/d²` path-loss model).

**Why it matters:** "we turned the jammer into a target." But a full
evening of work and the demo is complete without it.

## 26. Session 5 — Multi-threat priority stack             (≈2 h, spec: `SESSIONS.md` §5)

When multiple scenarios are simultaneously active, UI shows them
ranked by threat priority. Top of the stack gets the swarm's
attention.

**Why it matters:** operator-console realism. Skip if the curated
5-tab pitch flow doesn't actually need it.

## 27. Bridge B5 — ROE aware of mesh health                (≈2 h, spec: bottom of file)

When mesh health degrades, ROE policy applies a penalty: action
chip drops one tier (STRIKE → RECON → SEARCH).

**Why it matters:** narratively impressive but the existing beats
already convey this story.

## 28. Mesh hardware bring-up (H1–H4)                      (≈8 h, spec: `MESH_PLAN.md` Group A)

Three USB WiFi adapters. Real RealTransport. Live foil-the-antenna
reroute demo. Range/RSSI measurement.

**Why it matters:** if you can pull off the live foil-reroute, it's
the single most memorable moment of the entire pitch. But all of
this can be faked on `SimTransport` with the BLOCK toggle from
item 19. Real hardware is high-risk, high-reward.

(Note: the kill-drone button from item 7 is the *acoustic-pipeline*
equivalent — same audience-cue moment, but for a vanished sensor
rather than a blocked link. Both can coexist in the demo.)

---

## New session specifications

These specs are inline because they're not in the companion docs.

### Session 11 — 2-drone bearing-only localization

**Goal:** When only 2 drones detect an event, produce an honest fix
— a hyperbola curve + an uncertainty wedge — and surface it through
the same JSON contract as 3-drone fixes.

**Files touched:**

- New: `triangulation/core/solver_2drone.py`
- Modified: `triangulation/locate.py` (route 2-drone groups here)
- Modified: `triangulation/policy.py` (auto-downgrade 2-drone → SEARCH)
- Modified: `triangulation/AGENTS.md` (schema update)
- New: `triangulation/tests/test_2drone.py`

**Architecture:**

A 2-drone fix is fundamentally different from a 3-drone fix. The
JSON output stays the same shape (`source`, `cloud_*`, `cep50_m`,
`recommended_action`, etc.) but the semantics shift:

```
3-drone fix:
   source         = point estimate (lat, lon)
   cloud_latlon   = closed 95% ellipse polygon (~72 points)
   cep50_m        = radius
   fix_kind       = "point"          ← NEW field

2-drone fix:
   source         = midpoint of hyperbola arc (still lat, lon —
                    a representative point on the curve)
   hyperbola_latlon = list of (lat, lon) along the curve     ← NEW
   cloud_latlon   = wedge polygon — outer boundary of the
                    swept-uncertainty band on each side
   cep50_m        = null (undefined for a curve)
   cep50_perp_m   = perpendicular-to-curve half-width        ← NEW
   fix_kind       = "bearing"        ← NEW field
   bearing_axis_deg = orientation of the curve at midpoint   ← NEW
```

The hyperbola is parameterised: given drones at `p1, p2` and
`Δd = c · (t2 - t1)`, the locus is the set of points where
`||x - p1|| - ||x - p2|| = Δd`. Closed-form parameterisation in
canonical coordinates (origin at midpoint, major axis along p1-p2
direction): `x(t) = a · cosh(t)`, `y(t) = b · sinh(t)` with
`a = Δd/2`, `b = sqrt(c² - a²)` where `c` is half the inter-drone
distance. Then rotate and translate into the local plane.

The wedge is computed by Monte-Carlo: for each (σ_t, σ_pos) draw,
recompute the hyperbola; take the convex hull of all sampled
hyperbola points to get the swept boundary; output the boundary as
a closed polygon.

**Subtasks:**

- 11.1 `solver_2drone.hyperbola(p1, p2, dd, n_pts=64)` — return
       N points along the hyperbola arc, clipped to a reasonable
       extent (±2× inter-drone distance).
- 11.2 `solver_2drone.mc_wedge(events, drone_positions,
       clock_sigma_s, pos_sigma_m, n=400)` — MC sweep returning
       a list of hyperbola polylines; the wedge boundary is the
       convex hull of all points.
- 11.3 Route in `locate.py`: when a group has exactly 2 distinct
       drones, call `solver_2drone` instead of skipping; emit the
       new schema fields.
- 11.4 `policy.decide()`: when `fix_kind == "bearing"`, action is
       always SEARCH (never STRIKE or RECON). Add a reason string:
       "2-sensor bearing fix; insufficient for point engagement".
- 11.5 UI rendering: in `localize` phase, when `fix_kind ==
       "bearing"`, draw the hyperbola as a solid red curve and the
       wedge as a translucent red band. Skip the cross marker (no
       point estimate).
- 11.6 Tests: synthetic 2-drone event → hyperbola passes through
       the true source; wedge width scales with σ.

**⚠ HUMAN INPUT NEEDED:**

1. Hyperbola clipping extent. Suggested ±2× inter-drone distance
   so the curve stays on-screen for typical drone separations.
2. Should the UI label the curve "bearing locus" or "hyperbola"?
   Suggested "bearing locus" — non-specialists understand.

**Acceptance criteria:**

- A 2-drone group in `events.json` produces a `localizations.json`
  entry with `fix_kind == "bearing"`, a `hyperbola_latlon` polyline,
  a `cloud_latlon` wedge polygon, and `recommended_action ==
  "SEARCH"`.
- UI renders the curve + band correctly when this entry plays.
- 3-drone groups continue to produce `fix_kind == "point"` and
  ellipse clouds (no regression).

### Session 12 — Multi-scene narrative tab

**Goal:** Replace `① Gunshot · clean` with a 4-scene operational arc
that walks PATROL → STRIKE → drone-lost → DEGRADED DETECTION →
2-drone SEARCH. Tells the whole defense story in one tab.

**Files touched:**

- Modified: `ui/index.html` (tab state model, scene transition logic)
- New: `detection/output/narrative_gunfire.json` (scene-sequence data)
- Modified: `triangulation/server.py` (endpoint to load narratives)
- Modified: `triangulation/locate.py` (optional: a CLI flag to
  generate narrative scene data from synthetic events)

**Architecture:**

Each tab in the UI is now `{id, label, scenes: Scene[]}` where a
plain single-scenario tab has `scenes.length == 1` and a narrative
tab has `scenes.length > 1`. A `Scene` is an extended scenario:

```json
{
  "scene_index": 0,
  "title": "Initial detection — clean geometry",
  "narrative_text": "Three sensor drones holding patrol. Acoustic
                     event detected. Triangulation produces a tight
                     fix. ROE: STRIKE.",
  "drone_roster": ["drone_1", "drone_2", "drone_3"],
  "drones_lost_before_scene": [],
  "drones_lost_during_scene": [],
  "scenario": { ... full localization entry ... },
  "outcome": {
    "drone_lost": null,                 // or e.g. "drone_3"
    "next_scene_intro": "Drone 3 lost during engagement."
  }
}
```

The phase machinery from Session 7 applies WITHIN a scene. When the
last phase (`complete`) finishes, ▶ NEXT advances to the next scene
and restarts at `patrol`. ⏪ PREV at scene start jumps to the prior
scene's `complete`.

Drone-loss is **scripted**, not computed. The narrative file says
"after scene 2's strike, drone_3 is lost". The UI honours this by:
- Drawing drone_3 with a red ☓ overlay and dimmed fill from scene 3
  onwards.
- Leaving drone_3's icon at its scene-2 final position.
- Excluding drone_3 from any TDOA calculations in scenes 3+.

The four scenes:

```
Scene 1 — PATROL + DETECT + LOCALIZE + DECIDE + RESPOND + COMPLETE
  Drones: all 3.
  Fix: 3-drone ellipse, low CEP. Action: STRIKE.
  Outcome: drone_3 lost during strike (scripted).

Scene 2 — DRONE LOST (a single phase: COMPLETE)
  Visual: drone_3 ☓-marked. Banner: "ASSET LOST · roster reduced 3→2".
  No new detection. Operator clicks NEXT to continue.

Scene 3 — DETECT + LOCALIZE + DECIDE
  Drones: 2 (drone_1, drone_2). drone_3 dimmed and ignored.
  Fix: bearing-only hyperbola + wedge (item 6 math).
  Action: SEARCH (forced — can't STRIKE a curve).

Scene 4 — RESPOND + COMPLETE
  Two responders break formation and sweep along the hyperbola wedge.
  Each takes one half (use ellipse-aware sweep math adapted to a
  curve: 2 sweep points spaced along the wedge centreline).
  Outcome: "SEARCH PATTERN ACTIVE — awaiting next event".
```

Scene transitions don't need elaborate animation; a 500 ms cross-fade
of the banner is enough. The novelty is the narrative arc itself,
not the transition graphics.

**Subtasks:**

- 12.1 Tab state shape: `state.tabs[i].scenes[]` instead of a single
       scenario per tab. Update Session 7's NEXT/PREV logic to bridge
       scene boundaries.
- 12.2 Narrative file generator: `triangulation/locate.py
       --narrative gunfire --out detection/output/narrative_
       gunfire.json` produces a 4-scene JSON from a hand-crafted
       events sub-set. (Or hand-write the JSON for the demo.)
- 12.3 Scene-aware loader: `/api/narratives/<id>` returns the full
       scene list; the UI loads it once and stores in
       `state.tabs[NARRATIVE_TAB_ID].scenes`.
- 12.4 Drone roster rendering: dim drone_3 in scenes 3+ with a ☓
       overlay; exclude from `state.drones` for phase math; show in
       legend as "LOST".
- 12.5 Scene-boundary UI: banner during the inter-scene transition
       shows `narrative_text` of the next scene. Operator must click
       NEXT to enter.
- 12.6 Scene 4 sweep math: for a bearing fix, sweep points are
       (centre of wedge) ± 0.5 × wedge half-length along the
       hyperbola tangent. Adapt `policy.search_points` to accept
       either an ellipse or a wedge.
- 12.7 Replace tab ① with the narrative tab in the default tab list.
       Tabs ② – ⑤ remain single-scene presets so the team can still
       contrast.

**⚠ HUMAN INPUT NEEDED:**

1. Tab label. Suggested `① Gunshot · operational arc` to signal
   it's the storied one. Confirm.
2. Drone-loss visualisation. Suggested ☓ overlay + dimmed icon at
   last-known position. Alternative: full removal from map. Confirm.
3. Scene-2 duration. With no detection, it's just a banner + log
   line. Suggested ~3 s auto-advance OR wait-for-NEXT. Probably the
   latter to let the presenter dwell.
4. Should drones_used for scene 3 actually start the scene already
   missing one, or should there be a "drone reposition" phase first?
   Suggested: start already missing one — keeps the focus on the
   degradation result, not the bookkeeping.

**Acceptance criteria:**

- Tab `①` shows "scene 1 of 4" in the title strip.
- ▶ NEXT walks through every phase of every scene and ends after
  scene 4's `complete`.
- ⏪ PREV walks back across scene boundaries.
- Scene 2 visualises drone_3 as LOST.
- Scene 3 renders a hyperbola + wedge (no ellipse).
- Scene 3's action chip is SEARCH (blue).
- Scene 4's responder count is 2, not 3.
- Other tabs (② – ⑤, sandbox) are unaffected.

### Session 14 — Source icon + acoustic emission visuals

**Goal:** Replace the current "drones spontaneously light up from
nothing" visual with a coherent cause→effect chain. At DETECT phase
start, a small classifier-coloured icon (rifle / tank / missile /
bird) appears at the true source position, blinks, and emits
concentric "sound wave" rings outward. Drone-light-up timing ties to
ring-arrival timing. At LOCALIZE, rings stop; cloud fades in *around*
where the system thinks the source is — the gap between the visible
icon position and the cloud center is the visible localization
error. Includes a phase-narration subtitle bar at the bottom of the
map so the presenter doesn't have to narrate every beat.

**Files touched:**

- Modified: `ui/index.html` only

**Architecture:**

Three new visual layers stack on top of the existing entity layer:

```
existing render path (top → bottom):
   entity-layer (DOM)  : drones, target dots
   pulse layer (canvas): existing emitPulse() rings
   cloud layer (canvas): 95% confidence cloud
   terrain layer       : forest, grid

new additions:
   source-icon (DOM, entity-layer): classifier-coloured icon at true
                                     source position; spawned on
                                     DETECT, persists thereafter.
                                     Blink animation during DETECT.
   acoustic emission (canvas)     : concentric rings emanating from
                                     source position; emitted every
                                     ~200 ms during DETECT; expand
                                     to ~viewport radius over 1.5 s
                                     while stroke fades to 0.
   phase subtitle (DOM, footer)   : one line of plain English
                                     describing what's happening now.
```

Classification colour map (single source of truth):

```js
const CLASS_COLOR = {
  // threat
  gunshot:       '#e85c4a',   // existing --hostile red
  tank:          '#e85c4a',
  missile_launch:'#e85c4a',
  drone_hostile: '#e8a838',   // amber — hostile but lower severity
  // ambient (Session 15)
  bird:          '#4fd87a',   // existing --accent green
  dog:           '#4fd87a',
  crickets:      '#4fd87a',
  deer:          '#4fd87a',
  // unknown
  unknown:       '#e8a838',   // amber
};
```

Phase-by-phase responsibilities:

| Phase | Source icon | Rings | Cloud | Subtitle |
|---|---|---|---|---|
| PATROL | hidden | none | none | "Drones holding formation" |
| DETECT | spawn, blink | emit every 200 ms | none | "Acoustic signature detected by N sensors" |
| LOCALIZE | steady, no blink | stop, fade | fade in | "Triangulating source — CEP50 reducing" |
| DECIDE | pulse with action colour | none | held | "ROE evaluated — STRIKE / RECON / SEARCH / MONITOR" |
| RESPOND | held | none | held | "Responder dispatched / Sweep underway / …" |
| COMPLETE | held (or "neutralized" for STRIKE) | none | held | "Target neutralized / Recon complete / Sector cleared" |

**Subtasks:**

- 14.1 Icon library additions in the existing `ICONS` map for the
       new labels needed by Session 15: `bird` (small avian
       silhouette), `dog`, `crickets` (small dotted glyph), `deer`
       (antlers silhouette). Reuse existing styling.
- 14.2 New entity type `source` rendered through the existing
       `upsertEntity()` path. Position from
       `entry.source.{lat,lon}` (production tabs) or true source
       (sandbox / narrative scene with scripted truth).
- 14.3 CSS `@keyframes blink-source { 0%, 100% { opacity: 1.0;
       transform: scale(1.0) } 50% { opacity: 0.7; transform:
       scale(1.08) } }` — 0.5 s period, applied via `.source.blink`
       class. Removed at LOCALIZE start.
- 14.4 Phase hook in `tickPlayback`'s DETECT branch: at progress = 0,
       spawn source entity + start blink. Every ~200 ms thereafter
       (track via `pb.lastRingEmit`), call `emitPulse(sourceX,
       sourceY, color)` using the existing canvas pulse machinery
       — just call it from the source instead of from drones.
- 14.5 Tune ring expansion in `drawPulses` so a ring reaches the
       furthest drone at roughly DETECT-end. (Current animation
       constants probably need a small tweak — verify with the
       triangle preset.)
- 14.6 Tie drone-light-up to ring-arrival: instead of lighting all
       drones simultaneously at DETECT start, light each drone the
       moment its distance from source matches the leading-ring
       radius. Smooth fade-up over ~120 ms.
- 14.7 Phase subtitle DOM: new `<div class="phase-subtitle">` inside
       the existing `.map-wrap`, bottom-centred. Updated by a
       `PHASE_SUBTITLE` lookup keyed on `(phase, action)`.
- 14.8 Action-classification pulse on the source icon during DECIDE:
       brief colour flash matching the recommended action.
- 14.9 RESPOND outcome handling on the source icon:
       - STRIKE: at impact (RESPOND progress ≈ 0.9), source icon
         gets a "neutralized" overlay (red ☓ + 50 % opacity)
       - RECON: small camera-icon badge appears next to source
       - SEARCH: source dims slightly to suggest "still under
         investigation"
       - MONITOR (Session 15): no change; icon stays as-is
       - HOLD: no responder, no change
- 14.10 Z-order: source icon ABOVE drones ABOVE cloud ABOVE rings
        ABOVE terrain. Verify rendering order in `renderEntities()`.

**Considerations:**

- **💡 NOTE: source icon shows the DETECTED label, not true type.**
  Even when the system misclassifies (a deer flagged as "gunshot"),
  the icon shows the *classifier's* output. In sandbox, the icon
  shows the true type the user selected. In narrative tab scenes,
  the icon shows the scripted label.
- **💡 NOTE: rings emit from source, not from each drone.** Sound
  physically radiates from the source. Existing
  `emitPulse(droneX, droneY)` calls in the DETECT path can be
  removed or kept as "drone hears" secondary visuals — your call.
  Cleaner to remove and let the source-emitted rings be the only
  rings during DETECT.
- **💡 NOTE: cloud center vs icon position is the *visible
  error*.** This is the educational moment: judges see exactly how
  off the system is. Don't try to "snap" the cloud to the icon —
  the gap is the point.
- **💡 NOTE: subtitle bar is content-driven, not narration.** Use
  data from the scenario (drone count, action, CEP50) to fill in
  blanks: `"Acoustic signature detected by {N} sensors"` where N
  is the current alive count. Reads as a real system console.
- **⚠ Performance.** Ring emission every 200 ms × 1.5 s lifetime =
  up to ~8 rings concurrent. Plus existing sonar pulses. Should be
  fine on a modern laptop but worth a frame-rate check on the demo
  machine. Cap to 12 concurrent pulses if needed.

**⚠ HUMAN INPUT NEEDED:**

1. Ring emission rate (suggested 200 ms). Faster (100 ms) feels more
   urgent; slower (400 ms) feels more deliberate. Confirm.
2. Ring expansion duration (suggested 1.5 s). Tied to DETECT phase
   length (currently 1500 ms) so they align. Confirm if DETECT
   duration changes.
3. STRIKE outcome visual: red ☓ overlay (suggested) vs fade-to-grey
   vs explosion icon. Confirm.
4. Subtitle styling: monospace JetBrains Mono (existing pitch font)
   at ~14 px, dim accent colour. Confirm or tweak.

**Acceptance criteria:**

- PATROL phase: source icon hidden; no rings; subtitle says "Drones
  holding formation".
- DETECT phase start: source icon spawns at true position with
  classifier-coloured blink; rings begin emitting every 200 ms.
- Drone lights now match ring-arrival timing (visibly sequential,
  not simultaneous).
- LOCALIZE phase start: rings stop expanding (existing ones fade
  out); cloud begins fading in; source icon stops blinking.
- Gap between source icon position and cloud center is visibly
  the localization error.
- DECIDE phase: source icon pulses once in the action colour.
- RESPOND phase:
  - STRIKE → red ☓ overlay on source at progress ≈ 0.9
  - RECON → camera-icon badge appears
  - SEARCH → source dims
- Phase subtitle updates at every phase change with content-driven
  text.
- 60 fps maintained throughout (check `statFps`).

---

### Session 15 — Ambient (wildlife) triangulation tab

**Goal:** A dedicated tab `🐺 Wildlife · ambient` runs a bird /
crickets / dog scenario through the same pipeline as a threat, with
all green visuals and a new `MONITOR` action chip. Demonstrates
discriminative classification: the system localizes everything it
hears but only engages the right things.

**Files touched:**

- Modified: `triangulation/policy.py` (new MONITOR action,
  AMBIENT_LABELS constant)
- Modified: `triangulation/locate.py` (allow ambient via flag)
- Modified: `triangulation/AGENTS.md` (schema additions)
- Modified: `ui/index.html` (new tab, ambient color path)

**Architecture:**

Backend changes:

```
triangulation/policy.py:
  AMBIENT_LABELS = ("bird", "dog", "crickets", "deer")

  decide(cep50, gdop, label, confidence) -> Decision:
      # existing branches: HOLD, STRIKE, RECON, SEARCH
      if label in AMBIENT_LABELS:
          return Decision(action="MONITOR",
                          reason=f"{label} classified as ambient — "
                                 "non-threat",
                          severity="low",
                          weapons_release_required=False)

triangulation/locate.py:
  localize_scenario(..., triangulate_ambient=False):
      if all(e['relevant'] is False) and not triangulate_ambient:
          skip (existing behavior)
      if all(e['relevant'] is False) and triangulate_ambient:
          if label in AMBIENT_LABELS:
              localize as usual; output['classification'] = 'ambient'
          else:
              skip ('relevant=false' but not a recognised ambient)

  CLI flag: --ambient   (when set, processes ambient scenarios too)
```

New JSON field:

```
classification : "threat" | "ambient"      ← NEW
```

`threat_priority` for ambient = 0 (never competes with threats in
the priority stack).

Frontend:

- One of the 6 tabs is repurposed (or a 7th added):
  `🐺 Wildlife · ambient` with a bird/crickets/dog scenario loaded.
- All Session 14 visuals apply with green colour (bird/dog/crickets/
  deer all map to green in `CLASS_COLOR`).
- Action chip shows "MONITOR" in green.
- RESPOND phase is **skipped** (no engagement). After DECIDE, skip
  to COMPLETE. (Or run RESPOND with zero responders, just a
  subtitle "No engagement — logged.")
- Animal icon persists on the map after the scenario completes (a
  logged observation).
- Bird WAV plays during DETECT (already wired by the audio addon
  if `entry.label == "bird"` matches `AUDIO["bird"]`).

**Subtasks:**

- 15.1 `AMBIENT_LABELS` constant and `MONITOR` action in
       `policy.py`. Distinct chip colour:
       `--monitor: #4fd87a` (green; reuses --accent).
- 15.2 `decide()` returns MONITOR for any label in AMBIENT_LABELS,
       regardless of CEP/GDOP (a confident ambient is still
       ambient).
- 15.3 `_localizable()` in `locate.py` accepts a `triangulate_ambient`
       flag. When True, scenarios with `relevant: False` AND
       `label in AMBIENT_LABELS` are localised; others still
       skipped.
- 15.4 New JSON field `classification` ∈ {"threat", "ambient"}.
- 15.5 CLI flag `--ambient` on `python -m triangulation.locate`.
- 15.6 Add wildlife scenario data: pick `scenario_bird_mix.wav`
       from existing `events.json`. (May need to set
       `label: "bird"` on its rows; the input currently has
       `label: null`. One-line edit to events.json.)
- 15.7 Re-run pipeline with `--ambient` to populate
       `localizations.json` with at least one ambient entry.
- 15.8 Frontend tab: `🐺 Wildlife · ambient`. Loads the ambient
       entry. Uses Session 14's render path with green
       `CLASS_COLOR` for `label == "bird"` etc.
- 15.9 Action chip styling: green pill for MONITOR, label
       `"MONITOR · ambient signal"`.
- 15.10 RESPOND phase handling: skip outright or run-with-no-
        responders. Suggested: skip and jump to COMPLETE.
        Subtitle says "No engagement — observation logged."
- 15.11 Icon persistence: animal icon stays visible after COMPLETE
        (same as threat icon, but no neutralized overlay).
- 15.12 Audio: confirm bird WAV plays during DETECT. Tank/missile
        WAVs should NOT fire for ambient scenarios (different
        label).
- 15.13 Document: AGENTS.md schema additions for `classification`
        and the new MONITOR action.

**Considerations:**

- **💡 NOTE: don't auto-show ambient in OTHER tabs' backgrounds.**
  The temptation to "always render ambient detections faintly in
  every tab" is real and wrong. Clutters every other demo. Ambient
  belongs in its own tab so it gets attention when it's the focus
  and gets out of the way when it isn't.
- **💡 NOTE: MONITOR is operationally distinct from HOLD.** HOLD
  means "low confidence, can't act"; MONITOR means "high
  confidence, deliberate non-engagement". Different chip colour,
  different language.
- **💡 NOTE: classifier isn't real.** The "bird" label in the JSON
  comes from a CSV-style hardcoded classifier upstream, not an ML
  model. The pitch should be honest: we *display* the
  classification result; we don't *build* the classifier here.
  Add this caveat to the slide if a judge asks.
- **💡 NOTE: ambient scenarios still produce a green cloud.** It's
  tempting to skip the cloud ("we know it's a bird, why localize
  it?"). Render the cloud anyway — it shows that the system *did*
  the math and chose not to engage. That's the entire point.
- **⚠ The events.json bird scenarios have `relevant: false` and
  `label: null`.** Session 15 needs them to have `label: "bird"`
  (etc.) at minimum. Either patch the events.json directly or
  teach `_localizable` to infer the label from the scenario path
  (`scenario_bird_*` → `bird`). The path-inference approach is
  cleaner (no data edit) but adds magic.

**⚠ HUMAN INPUT NEEDED:**

1. Which animal scenario to feature? Suggested **bird** — most
   distinct from threat sounds aurally. Alternatives: dog
   (richer audio), crickets (more "ambient" feel).
2. Path-inference vs events.json edit for the label? Suggested
   **events.json edit** (one-line change, no hidden magic).
3. RESPOND phase: skip outright (suggested) or play with zero
   responders + "no engagement" subtitle? Both are valid.
4. Should ambient detections also have their own `cloud_format`
   default? Suggested: same as threat (ellipse, 95%).

**Acceptance criteria:**

- `python -m triangulation.locate --ambient` writes
  `localizations.json` with at least one entry where
  `classification == "ambient"` and `recommended_action ==
  "MONITOR"`.
- `🐺 Wildlife · ambient` tab is selectable in the UI.
- All visuals (source icon, rings, cloud, chip) are green.
- Action chip text reads "MONITOR · ambient signal".
- RESPOND phase is either skipped or shows no responder
  animation.
- Bird WAV plays during DETECT (audio addon already wired).
- After COMPLETE, the animal icon stays on the map.
- Switching to a threat tab and back to ambient correctly
  re-renders everything green.

---

### Session 16 — Mesh bandwidth side panel

**Goal:** Permanent top-bar strip showing live mesh bandwidth
telemetry, with click-to-inspect hex dump for the engineer-judge.
Surfaces the compression work in `mesh/` so the bandwidth
efficiency story is visible during the pitch instead of hidden in
a benchmark CLI.

**Files touched:**

- New: `triangulation/server.py` adds `/api/mesh/bandwidth` endpoint
  (wraps `mesh.metrics.get_metrics().summary()` and adds per-event
  hex dumps from `mesh.payload`)
- Modified: `ui/index.html` (top-bar strip + popover)
- Modified: `mesh/publish.py` or new `mesh/live_publisher.py` —
  small helper to fire a single tactical event from a live UI
  trigger and return the metrics delta

**Architecture:**

```
ui/index.html (top bar)
   │
   │ 1 s polling
   ▼
   GET /api/mesh/bandwidth
   │
   ▼
   triangulation/server.py
   │
   ├── on first call: load events.json + localizations.json,
   │   pre-compute per-row tactical and per-entry loc-summary
   │   sizes via mesh.payload.event_row_to_tactical / pack_loc_summary
   │
   ├── on scenario tab activation: bump running totals
   │   (the UI sends a hint when active scenario changes)
   │
   └── return {
         total_mesh_bytes: int,
         total_json_bytes: int,
         saved_bytes: int,
         saved_pct: float,
         last_packet: {
           kind: "tactical" | "loc_summary",
           bytes_mesh: int,
           bytes_json: int,
           hex_mesh: "e0 01 01 02 …",
           hex_json: "{\"label\":\"gunshot\",…}",
         },
         extrapolation: { events_per_hour: 1000, kb_per_day_mesh: 3, kb_per_day_json: 38 }
       }
```

Top-bar layout (matches existing JetBrains Mono tactical style):

```
┌──────────────────────────────────────────────────────────────┐
│ MESH 64 B   /   JSON 392 B   /   SAVED 84%        ⓘ click   │
│ TOTAL 2.4 KB sent · 28 KB saved · est 26 MB/day              │
└──────────────────────────────────────────────────────────────┘
```

Click anywhere on the strip → popover with side-by-side hex/JSON
dump and a small bar-chart of cumulative savings over the pitch.

**Subtasks:**

- 16.1 Backend: `/api/mesh/bandwidth` endpoint. Reads
       `detection/output/events.json` and `localizations.json` once
       at startup, computes per-row tactical sizes and per-entry
       loc-summary sizes via the existing `mesh.payload` helpers.
- 16.2 UI session state tracks "totals so far" — accumulates on each
       scenario tab activation, never resets unless presenter hits
       a "↺ reset bandwidth counters" button.
- 16.3 Frontend top-bar strip: monospace, two lines, click → popover.
- 16.4 Popover: side-by-side hex dump (left = mesh, right = JSON),
       small bar chart underneath showing cumulative bytes over time.
- 16.5 Extrapolation footer text — formula `events/hour × per-event
       saving × 24`, displayed as "est 26 MB/day per swarm at scale".
- 16.6 Reset button (for rehearsals). Bottom-right of the popover.
- 16.7 Performance: poll endpoint at 1 Hz, not faster. The number
       shouldn't update mid-narration.

**Considerations:**

- **💡 NOTE: this panel is read-only.** It only displays what
  `mesh.metrics` and `mesh.payload` already produce. Don't
  re-implement the compression in JS — fetch numbers from Python.
- **💡 NOTE: per-scenario delta vs running total.** Showing both is
  the right call: per-scenario for the immediate event, total for
  cumulative impact. Don't only show one.
- **💡 NOTE: extrapolation is a *talking point*, not a measured
  number.** The "26 MB/day at scale" line is calculated from
  assumed events/hour. Caveat it in the popover footer: "extrapolated
  at 1000 events/hour, your mileage may vary".
- **⚠ Don't update faster than 1 Hz.** Animation noise distracts
  from the main map. Bandwidth numbers are calm and authoritative,
  not flashing.

**⚠ HUMAN INPUT NEEDED:**

1. Extrapolation rate: 1000 events/hour suggested. Confirm or
   override (defense-realistic might be 50–200/hour during active
   engagement).
2. Top-bar strip placement: above the existing header (suggested)
   vs below it. Confirm.
3. Reset button visible always vs only in popover? Suggested
   only in popover (presenter doesn't accidentally reset mid-pitch).

**Acceptance criteria:**

- `/api/mesh/bandwidth` returns correct per-event tactical size
  (32 B + 32 B frame = 64 B on wire) and per-loc summary size
  (24 B + 32 B frame = 56 B on wire).
- Top-bar strip renders the live numbers in the tactical theme.
- Click → popover shows correct side-by-side hex dump from
  `mesh.payload`.
- Reset button zeroes the totals without breaking the page.
- Page still 60 fps with the panel polling every 1 s.

---

### Session 17 — Packet flight FX (toggleable)

**Goal:** Toggleable atmospheric polish on top of Session 18's mesh
topology panel. When `BANDWIDTH FX: on` in the top bar, every mesh
transmission spawns a small coloured capsule that travels along
the relevant edge in the topology view over ~400 ms. Capsule
colour by payload kind, width ∝ byte count, hover → tooltip with
packet details. Default **off** — turn on when narrating the mesh,
off otherwise.

**Files touched:**

- Modified: `ui/index.html` (toggle, animation system, hover tooltip)
- Modified: `triangulation/server.py` (add SSE `/api/mesh/events`
  stream — or extend the existing polling endpoint with a
  recent-events tail)

**Architecture:**

```
state.bandwidthFx : bool        // top-bar toggle
state.flyingCapsules : list     // active animations, each:
  { src_node, dst_node, kind, bytes, t, color, started_ms }

Animation loop:
   each frame:
     for each capsule c:
       c.t += dt / 400ms
       if c.t >= 1:    remove from list
       else:           lerp position along edge(src, dst)
                        draw rect of width ∝ bytes, color ∝ kind

Event source:
  GET /api/mesh/events?since=<ts>   (polled at 200 ms)
  → [{src_id, dst_id, kind, bytes, ts}, ...]

  When received and state.bandwidthFx == true:
    push each event onto state.flyingCapsules
```

Visual style:

| Kind | Colour | Width per byte | Note |
|---|---|---|---|
| tactical (32 B) | green `#4fd87a` | small dot (~2 px/B) | acoustic detection event |
| loc_summary (24 B) | blue `#4faec8` | small dot | localization fix |
| frame overhead (HMAC, 16 B) | purple fringe | thin trailing edge | shown as glow trail |

**Subtasks:**

- 17.1 Top-bar toggle pill `🔁 BANDWIDTH FX: off`. Click toggles
       state.bandwidthFx; pill colour reflects state.
- 17.2 Backend: SSE endpoint `/api/mesh/events` OR polled tail.
       Emits packet-sent events with src/dst/kind/bytes/ts. Easiest:
       reuse Session 18 bridge's `/api/mesh/events` if that exists,
       just filter for `kind in ("tactical","loc_summary")`.
- 17.3 Frontend animation: per-frame update of state.flyingCapsules,
       lerping along edge positions from the topology panel's
       layout.
- 17.4 Capsule rendering: rounded rectangle with a small dot, width
       ∝ bytes, colour ∝ kind. Tooltip on hover.
- 17.5 Cap concurrent animations to 20 — drop oldest if exceeded.
- 17.6 Auto-fade in last 20% of travel for smoother visual end.
- 17.7 Default state: off. Persist toggle state in `localStorage`
       across reloads (presenter sets it once, demo machine
       remembers).

**Considerations:**

- **💡 NOTE: compression happens once at source, not at every hop.**
  Animate the SAME capsule along multiple hops, not a new one at
  each. The capsule label `32 B` stays 32 B for the whole flight —
  it doesn't shrink at relay nodes.
- **💡 NOTE: this is decoration.** Session 16's side panel is the
  credibility. If a judge asks "are those packets real?", point at
  the panel numbers; the capsules are just visualization of what
  the numbers report.
- **💡 NOTE: default off matters.** Most of the demo isn't about
  the mesh. Constant capsule animation during triangulation /
  kill-button / sandbox moments would distract.
- **⚠ Performance.** Cap concurrent capsules. With 20 simultaneous
  rounded-rect renders at 60 fps the GPU is fine; with 200 it isn't.

**⚠ HUMAN INPUT NEEDED:**

1. Default state: off (suggested) vs on. Confirm.
2. Capsule shape: small rounded rect (suggested), pill, or glowing
   dot. Confirm.
3. Where capsules render: only in the mesh topology panel
   (suggested, less clutter) vs also overlaid on the main map.
4. Persist toggle state in localStorage? Suggested yes.

**Acceptance criteria:**

- Toggle pill in top bar; click flips state.
- When on, every mesh send spawns a capsule that lerps along the
  correct edge in the topology panel.
- Capsule colour and width reflect payload kind and byte count.
- Hover shows tooltip with packet details.
- 60 fps maintained with up to 20 concurrent capsules.
- When off, no animation but the side panel (Session 16) keeps
  updating numbers.
- Toggle state persists across page reload.

---

### Session 13 — Kill-drone button (live resilience)

**Goal:** Persistent UI control to drop any drone from the current
scene at any time. Triggers a live re-localization with the reduced
roster. Surfaces the graceful-degradation story as a reactive,
audience-driven moment rather than a scripted scene. Doubles as the
implementation that Session 12's scene-2 drone-loss beat invokes.

**Files touched:**

- Modified: `ui/index.html` (kill pills + reset button, kill state,
  re-render on change)
- Modified: `triangulation/server.py` (accept `killed` query/body
  param on all localize/sandbox endpoints)
- Modified: `triangulation/locate.py` (filter events by killed
  roster before localizing)
- Modified: `triangulation/policy.py` (new `INSUFFICIENT_SENSORS`
  action when < 2 alive drones)
- Modified: `triangulation/AGENTS.md` (schema additions:
  `killed_drone_ids`, action enum extension)

**Architecture:**

```
state.tabs[i].killedDrones : Set<string>     // per-tab kill state
state.tabs[i].defaultDrones : list<string>   // restored on RESET KILLS

UI fires recompute on every kill/revive:

  /api/scenarios/<id>?sigma_t_ms=X&sigma_pos_m=Y
                     &killed=drone_2          ← NEW

Backend (locate.localize_scenario):
  group_filtered = [e for e in group
                    if e['drone_id'] not in killed_set]
  remaining = len({e['drone_id'] for e in group_filtered})
  if remaining >= 3:    use existing 3-drone ellipse fix
  if remaining == 2:    use Session 11 hyperbola+wedge fix
  if remaining == 1:    emit {action: "INSUFFICIENT_SENSORS",
                              fix_kind: "none",
                              reason: "single-sensor fix not
                                       available without RSSI mesh"}
  if remaining == 0:    emit no-fix sentinel; UI shows pure patrol
```

Switching tabs resets the kill set to that tab's defaults (so a
kill on `①` doesn't poison `②`). The narrative tab's scene-2 beat
invokes the kill mechanism programmatically (no separate code path).

**Subtasks:**

- 13.1 Right-rail UI: a row of `💀 drone_<id>` pills (one per drone
       in the current roster) + a `🔄 RESET KILLS` button. Pills
       toggle: pressed = killed (red ☓ on the icon).
- 13.2 Frontend state: `state.tabs[i].killedDrones`. Mirror to the
       drone-render path: killed drones get the `lost` CSS class
       (dimmed icon + red ☓ overlay). Excluded from `state.drones`
       for any phase math.
- 13.3 Wire kill → `recomputeActiveTab(killed=[...])`. Debounce
       the same as σ sliders (~120 ms).
- 13.4 Backend: `localize_scenario` gains a `killed_drone_ids:
       set[str] | None = None` kwarg. Filters the group before
       running the math; routes 3 → 3-drone, 2 → 2-drone (Session
       11), <2 → graceful no-fix.
- 13.5 Flask endpoint changes: parse `killed=a,b,c` from query
       string into a set; pass through.
- 13.6 `policy.decide()`: add `INSUFFICIENT_SENSORS` to the Action
       enum; returns when `fix_kind == "none"`. Severity = "low",
       weapons_release_required = false.
- 13.7 New action chip colour for INSUFFICIENT_SENSORS (suggested
       `--insufficient: #6a737d` slate-grey).
- 13.8 UI banner when `INSUFFICIENT_SENSORS`: "SENSOR LOSS — fix
       unavailable · expanding patrol".
- 13.9 Tab-switch reset: when `setActiveTab(j)` runs, clear
       `state.tabs[j].killedDrones` to defaults. (Don't touch
       OTHER tabs' kill sets — they may be mid-demo too.)
- 13.10 Keyboard shortcut: `k` cycles through drones to kill the
       next live one. Useful for fast presenter input.

**Considerations:**

- **💡 NOTE: kill is pure UI state.** events.json on disk is never
  modified. Each render call passes the killed set explicitly to
  the backend.
- **💡 NOTE: works in every tab, including sandbox.** In sandbox,
  a killed drone stays at its dragged position with ☓ overlay; it
  just doesn't contribute to the math.
- **💡 NOTE: Session 12 reuses this.** Scene 2's drone-loss beat is
  just a programmed kill call at scene start. No parallel code
  path for "scripted" vs "ad-hoc" loss.
- **💡 NOTE: revival is instant.** Click the pill again to revive;
  fix re-tightens within ~120 ms.
- **⚠ Edge case: σ sliders + kill must not race.** Both fire fetches
  on change. Use a single async function `recomputeActiveTab()` that
  reads both states at the moment of fetch and last-fetch-wins.

**⚠ HUMAN INPUT NEEDED:**

1. Button placement. Right-rail pill row (suggested) vs top-bar
   dropdown (more screen real estate). Confirm.
2. Should kill state persist across browser refresh? Suggested
   **no** — each demo starts clean.
3. Audio cue on kill? Suggested **no** — competes with scenario
   sounds.
4. Keyboard shortcut for the kill cycle. Suggested `k` (mnemonic).
   Confirm.

**Acceptance criteria:**

- Kill `drone_2` in a 3-drone scenario → ellipse collapses to
  hyperbola+wedge (Session 11) within ~200 ms; action chip flips
  from STRIKE/RECON to SEARCH live.
- Kill `drone_2` + `drone_3` → action chip becomes
  INSUFFICIENT_SENSORS; banner appears; no fix is drawn.
- `🔄 RESET KILLS` → all drones restored; original fix returns
  within ~200 ms.
- Tab switch resets kills for the target tab to that tab's defaults.
- Works in the sandbox tab (drag remaining drones, see hyperbola
  follow the geometry).
- Session 12 scene 2 transitions invoke this mechanism rather
  than duplicating logic.

### Add audio — atmospheric rotor loop + event sound cues

*Not a numbered session — sprinkled into whatever UI work is happening
that day. Adds ~1.5 h total. Hooks into the phase machine from
Session 7. Can ship at any point after Session 7 lands.*

**Goal:** make the demo feel like a sound-detection system by
actually playing sound. Two layers:

1. **Atmospheric rotor loop.** Drone rotor WAV looping in the
   background while drones are on screen. OFF by default (it's
   annoying after 30 s of pitch); toggle pill in the top bar.
2. **Event audio cues.** When a scenario reaches DETECT phase, the
   classified sound plays — gunshot for `label=="gunshot"`, tank
   engine for `"tank"`, etc. Timed to land **0.5 s before** the
   target dot appears in LOCALIZE, so the audience hears the event
   first, then sees the system register it.

**Files touched:**

- Modified: `ui/index.html` (audio elements, phase-hook trigger,
  rotor toggle pill)
- Modified: `triangulation/server.py` (one new static route to
  serve `data/samples/` so the browser can fetch the WAVs)

**Architecture:**

```
ui/index.html
  AUDIO = { rotor, gunshot, tank, missile_launch, drone }
    each one a new Audio(src)
  AUDIO.rotor.loop = true
  AUDIO.rotor.volume = 0.25
  for each event sound: volume = 0.75

  Phase machine hook (in tickPlayback):
    on DETECT phase, when progress crosses (dur - 500ms) / dur:
       play AUDIO[entry.label] from currentTime = 0
       (fires exactly 500 ms before LOCALIZE phase starts)

  Top bar: <button id="rotor-toggle">🔊 ROTOR · off</button>
    click: AUDIO.rotor.play() / pause(); toggle label

triangulation/server.py
  Add a single Flask route:
    @app.route("/audio/<path:rel>")
    def serve_audio(rel):
        return send_from_directory(REPO_ROOT / "data/samples", rel)
  Browser URLs: /audio/gunshot/demo_gunshot_128293.wav, etc.
```

**Tasks:**

- A.1 In `triangulation/server.py`, add the `/audio/<path:rel>`
      route serving `data/samples/`.
- A.2 In `ui/index.html`, declare an `AUDIO` map keyed by event
      label, each value a `new Audio("/audio/<path>")` preloaded
      with `preload="auto"`. Map labels:
      `gunshot → demo_gunshot_128293.wav`,
      `tank → 169743__qubodup__m1-abrams-tank-engine-and-shots-wombzerncci.flac`
      (or the shorter `dennish18-tank-moving-143104.mp3`),
      `missile_launch → ucas_launch_x47b_qubodup.flac`,
      `drone → uas_drone_pass_dcpoke.wav` (rotor loop).
- A.3 Hook the phase machine: in `tickPlayback`'s DETECT branch,
      track whether the event audio has fired for the current
      phase entry (avoid double-fire). Fire when
      `phaseT >= (PHASE_MS.detect - 500)`. Reset the fired flag on
      phase advance.
- A.4 Top-bar rotor toggle. State stored in
      `state.rotorEnabled: bool`, default `false`. Click handler
      toggles state, plays/pauses `AUDIO.rotor`, updates button
      label `🔊 ROTOR · on` / `🔇 ROTOR · off`.
- A.5 Mute-all keyboard shortcut: `m` toggles a master mute that
      pauses all sounds. Useful for the presenter if a phone rings.
- A.6 Kill-drone interaction (Session 13): when ALL drones killed,
      auto-pause the rotor (no drones → no rotor sound). When any
      drone revived, resume if `rotorEnabled` is true.

**Considerations:**

- **💡 NOTE: browser autoplay policy.** Audio cannot play until the
  user clicks something. The first ▶ NEXT click counts. No special
  handling required; first audio just plays from then on.
- **💡 NOTE: file paths via Flask, not relative.** The UI is served
  by Flask anyway (Session 8); use absolute `/audio/...` URLs.
- **💡 NOTE: scene-2 of the narrative tab (drone lost).** If you
  want a "drone lost" sound effect for the narrative arc, add a
  short static / explosion WAV under a new label like
  `drone_lost`. Optional — silence works fine too.
- **💡 NOTE: rotor loop must be seamless.** Some WAVs have a click
  at the loop boundary. If you hear it, trim the WAV with
  `ffmpeg -i in.wav -t 4 -af afade=t=out:st=3.9:d=0.1 out.wav` to
  fade out the last 100 ms cleanly.
- **⚠ Multi-event overlap.** Clicking NEXT fast can fire two event
  WAVs simultaneously. Acceptable — it actually reads as realistic.
  But if you want to enforce one-at-a-time: pause the previous
  event audio before playing the new one.
- **⚠ Sandbox tab.** Sandbox has no scenarios advancing through
  phases, so it has no DETECT phase to hook into. Skip event audio
  in sandbox. Rotor still works if enabled.

**⚠ HUMAN INPUT NEEDED:**

1. Rotor default: off (suggested) vs on. Confirm off.
2. Volume balance: rotor `0.25`, events `0.75`. Confirm.
3. Lead time before LOCALIZE: 500 ms (suggested). Could be 300 ms
   or 800 ms — confirm what feels right.
4. Tank WAV: short loop (`dennish18-tank-moving-143104.mp3`, ~3 s)
   or longer atmospheric (`169743__qubodup`, ~30 s)? Suggested
   the short one — fires once per scenario, doesn't drag.
5. Mute-all keyboard shortcut on `m`? Confirm.

**Acceptance criteria:**

- Rotor toggle pill in the top bar; clicking it plays/pauses a
  looped drone WAV at `0.25` volume.
- Default state on page load: rotor OFF.
- When a scenario reaches DETECT phase and crosses the
  `(dur - 500ms)` mark, the matching event WAV plays once at
  `0.75` volume.
- LOCALIZE phase starts ~500 ms later; dot appears.
- Mute-all key (`m`) silences everything; press again to restore.
- Sandbox tab: rotor works; no event audio (no phases).
- Kill all drones → rotor auto-pauses (until revival).

---

## Bridge specifications (referenced above)

These are short specs for the bridge sessions referenced in items
17, 22, 24, 27. They're not in any other doc — included here so the
plan is self-contained.

### Bridge: Recon imagery actually traverses the mesh (item 22)

**Files:** `ui/index.html`, `triangulation/server.py`,
`mesh/imagery.py`.

**Change:** in Session 4's telemetry handler, when the RECON action
hits the `IMAGING NOW` beat, instead of `popup.show()`, the UI:

1. `POST /api/recon-imagery` with `{scenario_id}`.
2. Open SSE to `/api/recon-imagery/stream/<id>`.
3. Render the image incrementally as chunks arrive.
4. On SSE close: log "imagery complete via mesh".
5. On 5 s timeout without first chunk: show the static placeholder
   so the demo never appears broken.

**Acceptance:** the recon popup that used to appear instantly now
animates a progress bar from 0% to 100% as the mesh delivers chunks.
First-thumb under 250 ms in sim.

### Bridge: Mesh-NTP corrects acoustic timestamps (item 24)

**Files:** `triangulation/core/io.py`, new
`triangulation/clock.py`, `triangulation/server.py`.

**Change:** `core/io.relative_times` gains an optional
`clock_offsets: dict[drone_id, ns] | None = None` argument. When
provided, it adds the offset to each event's timestamp before
differencing. `triangulation/clock.py` exposes
`register_mesh(node)` and `get_offsets()`. The Flask server, when
mesh-aware mode is enabled (env `MESH_MODE=1`), registers the
mesh node at startup and passes `get_offsets()` to every localize
call.

**Acceptance:** with mesh on, injecting 1 ms drift on a drone
keeps CEP50 within 5% of un-drifted; with mesh off, CEP50 visibly
blows up.

### Bridge: Demo orchestrator (item 17)

**Files:** new `scripts/demo.py`, README update.

**Change:** `scripts/demo.py` reads `mesh/topology.yaml`, spawns
`python -m mesh.node --id <id>` for each drone + `python -m
triangulation.server` for the operator backend, polls the server
port, opens the browser. Ctrl-C SIGTERMs all children and waits.

**Acceptance:** `./scripts/demo.sh` brings up everything, opens
the browser, Ctrl-C cleans up, no zombie processes.

### Bridge: Mesh events in the operator event log (item 19)

**Files:** `ui/index.html`, `mesh/operator.py`,
`triangulation/server.py`.

**Change:** existing `#eventLog` in the UI now also displays
mesh events (route changes, NTP convergence, frame counts) with a
distinct `.entry.mesh` CSS class (cyan tint). Source is a polled
`/api/mesh/events?since=<ts>` endpoint.

**Acceptance:** running the demo, the event log interleaves
acoustic telemetry (red/amber) and mesh telemetry (cyan).
"BLOCK drone_2" in the UI produces a `[ROUTE]` line in the log
within 500 ms.

### Bridge: ROE aware of mesh health (item 27)

**Files:** `triangulation/policy.py`, `triangulation/server.py`.

**Change:** `policy.decide(...)` gains kwargs `mesh_health_score:
float = 1.0`, `clock_sync_quality_us: float = 0`. When the score
drops below 0.9 OR `clock_sync_quality_us > 100`, the action chip
drops one tier. UI shows a "mesh health" pill next to the chip.

**Acceptance:** triggering "BLOCK drone_2" causes the active tab's
ROE action to visibly downgrade (STRIKE → RECON, or RECON →
SEARCH) within one polling tick.

---

## Time budget at a glance

| Tier | Sessions | Hours |
|---|---|---|
| Tier 1 — Essential | 1–13 | ≈ 43 h |
| Tier 2 — Strong (mesh) | 14–24 | ≈ 27 h |
| Tier 3 — Nice to have | 25–28 | ≈ 17 h |

If you have **≤ 43 h**: ship Tier 1, done. Demo is complete,
operator-paced, every phase visually self-explanatory, includes the
narrative arc, has the sandbox, lets you live-kill drones, contrasts
threat vs ambient classification, ships with the bandwidth-budget
slide, has a permanent live bandwidth side panel showing the
mesh compression numbers, AND has a fully reactive Live Ops tab
where events are dropped on the map and the system responds in
real time.

If you have **43–70 h**: Tier 1 + Tier 2. Full integrated demo with
a working mesh underneath everything, including the toggleable
packet-flight FX animation.

If you have **70+ h**: pick from Tier 3, hardware bring-up first if
anyone on the team is signed up for it.

## Repository layout after all of Tier 1 + Tier 2

```
Junction_Defence_Hackathon/
├── triangulation/
│   ├── core/
│   │   ├── io.py, solver.py, uncertainty.py
│   │   └── solver_2drone.py        ← new (item 6)
│   ├── locate.py, policy.py, projection.py
│   ├── viewer.py, sandbox.py       (sandbox: item 4)
│   ├── server.py                   ← new (item 3)
│   ├── clock.py                    ← new (item 18 bridge)
│   ├── jam.py
│   └── tests/
├── mesh/                           ← new (items 9–17)
│   ├── transport/{base.py, sim.py, real.py?}
│   ├── frame.py, security.py
│   ├── routing.py, priority.py
│   ├── ntp.py, imagery.py
│   ├── operator.py, node.py
│   ├── topology.yaml
│   └── tests/
├── ui/index.html                   (tabs + sliders + sandbox + narrative + mesh panel)
├── scripts/demo.py                 ← new (item 12 bridge)
├── docs/MESH_ARCHITECTURE.md       (Session 6, item 8)
├── detection/output/
│   ├── events.json
│   ├── localizations.json
│   ├── localizations_jammed.json
│   └── narrative_gunfire.json      ← new (item 7)
├── SESSIONS.md, SESSIONS_INTERACTIVE.md, MESH_PLAN.md
└── ROADMAP.md                      ← this file
```

## Decision checklist before starting

Before kicking off the next Sonnet session, confirm:

1. **Hours remaining?** Determines which tiers you build.
2. **Sim-only at the venue, or hardware in scope?** If sim-only,
   skip item 22.
3. **Pitch length?** 60 s / 2 min / 5 min — affects how many tabs +
   scenes you can showcase. (The narrative tab alone fills ~90 s.)

Once those are answered, follow the numbered list above. Don't
skip ahead within a tier — each item ends with the demo strictly
better, not half-broken.
