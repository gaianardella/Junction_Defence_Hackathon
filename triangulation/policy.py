"""ROE policy engine — pure, deterministic, no I/O.

Maps localization quality metrics + threat label onto a recommended
action (STRIKE / RECON / HOLD) and a numeric priority score.

All thresholds are module-level constants so they can be tuned for a
live demo without touching the logic.

Usage
-----
    from triangulation.policy import decide, priority

    decision = decide(cep50_m=4.2, gdop=1.8, label="tank", confidence=0.88)
    # Decision(action='STRIKE', reason='...', severity='high',
    #           weapons_release_required=True)

    score = priority(label="tank", recommended_action="STRIKE",
                     cep50_m=4.2, severity="high")
    # e.g. 118.64
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# ── Thresholds ───────────────────────────────────────────────────────────────

# A fix with CEP50 below this (metres) AND GDOP below STRIKE_GDOP_MAX
# is tight enough to authorise a strike.
STRIKE_CEP_MAX: float = 10.0

# Above this GDOP the geometry is too poor for a strike even if CEP50 is small.
STRIKE_GDOP_MAX: float = 3.0

# Below this localisation_confidence the fix is considered unusable — HOLD
# regardless of any other metric.
HOLD_CONFIDENCE_FLOOR: float = 0.10

# Only these labels are eligible for a STRIKE recommendation.
STRIKE_ELIGIBLE_LABELS: tuple[str, ...] = ("gunshot", "missile_launch", "tank")

# ── Severity mapping ─────────────────────────────────────────────────────────

LABEL_SEVERITY: dict[str | None, str] = {
    "missile_launch": "high",
    "tank":           "high",
    "gunshot":        "medium",
    "drone":          "low",
    None:             "low",
}

# ── Priority scoring constants ────────────────────────────────────────────────

SEVERITY_BASE: dict[str, float] = {
    "high":   100.0,
    "medium":  50.0,
    "low":     20.0,
}

ACTION_BONUS: dict[str, float] = {
    "STRIKE": 20.0,
    "RECON":  10.0,
    "HOLD":    0.0,
}

# Each metre of CEP50 beyond 10 m subtracts this from the priority score.
PRIORITY_CEP_PENALTY_PER_M: float = 0.3
PRIORITY_CEP_PENALTY_FLOOR: float = 10.0

# ── Types ────────────────────────────────────────────────────────────────────

Action = Literal["STRIKE", "RECON", "HOLD"]


@dataclass(frozen=True)
class Decision:
    """Output of :func:`decide`."""

    action: Action
    reason: str
    severity: str
    weapons_release_required: bool


# ── Public API ────────────────────────────────────────────────────────────────

def decide(
    cep50_m: float,
    gdop: float,
    label: str | None,
    confidence: float,
) -> Decision:
    """Return a :class:`Decision` for the given localization quality + label.

    Parameters
    ----------
    cep50_m:
        50th-percentile circular error in metres.
    gdop:
        Geometric dilution of precision (≥ 1.0).
    label:
        Threat class from the audio classifier, e.g. ``"tank"``.  ``None``
        means not relevant (should never reach this function in practice, but
        handled gracefully).
    confidence:
        ``localization_confidence`` score (0–1).

    Notes
    -----
    ``confidence`` is derived from ``cep50_m`` so gating on *both* would
    double-count the same signal.  ``confidence`` is only used for the
    absolute HOLD floor; all other decisions use ``cep50_m`` + ``gdop``
    + ``label`` directly.
    """
    severity = LABEL_SEVERITY.get(label, "low")

    # 1. Unusable fix — HOLD regardless.
    if confidence < HOLD_CONFIDENCE_FLOOR:
        return Decision(
            action="HOLD",
            reason=f"localisation_confidence {confidence:.3f} below floor "
                   f"{HOLD_CONFIDENCE_FLOOR}",
            severity=severity,
            weapons_release_required=False,
        )

    # 2. Strike envelope check.
    strike_eligible = label in STRIKE_ELIGIBLE_LABELS
    cep_ok = cep50_m < STRIKE_CEP_MAX
    gdop_ok = gdop < STRIKE_GDOP_MAX

    if strike_eligible and cep_ok and gdop_ok:
        return Decision(
            action="STRIKE",
            reason=(
                f"CEP50 {cep50_m:.1f}m within strike envelope "
                f"(<{STRIKE_CEP_MAX}m), GDOP {gdop:.2f} (<{STRIKE_GDOP_MAX}), "
                f"label '{label}' is strike-eligible"
            ),
            severity=severity,
            weapons_release_required=True,
        )

    # 3. Build a human-readable reason for RECON.
    reasons: list[str] = []
    if not strike_eligible:
        reasons.append(f"label '{label}' not strike-eligible")
    if not cep_ok:
        reasons.append(f"CEP50 {cep50_m:.1f}m exceeds limit {STRIKE_CEP_MAX}m")
    if not gdop_ok:
        reasons.append(f"GDOP {gdop:.2f} exceeds limit {STRIKE_GDOP_MAX}")

    return Decision(
        action="RECON",
        reason="; ".join(reasons) or "RECON by default",
        severity=severity,
        weapons_release_required=False,
    )


def priority(
    label: str | None,
    recommended_action: Action,
    cep50_m: float,
    severity: str,
) -> float:
    """Numeric threat priority score (higher = more urgent).

    Formula::

        base    = SEVERITY_BASE[severity]
        bonus   = ACTION_BONUS[recommended_action]
        penalty = max(0, cep50_m - PRIORITY_CEP_PENALTY_FLOOR)
                  * PRIORITY_CEP_PENALTY_PER_M
        score   = base + bonus - penalty

    The absolute values don't matter, only relative order across scenarios.
    """
    base = SEVERITY_BASE.get(severity, SEVERITY_BASE["low"])
    bonus = ACTION_BONUS.get(recommended_action, 0.0)
    penalty = max(0.0, cep50_m - PRIORITY_CEP_PENALTY_FLOOR) * PRIORITY_CEP_PENALTY_PER_M
    return base + bonus - penalty
