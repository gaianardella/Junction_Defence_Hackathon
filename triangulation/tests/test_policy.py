"""Unit tests for triangulation.policy — threshold edges and core logic."""

from __future__ import annotations

import pytest

from triangulation.policy import (
    HOLD_CONFIDENCE_FLOOR,
    STRIKE_CEP_MAX,
    STRIKE_GDOP_MAX,
    STRIKE_ELIGIBLE_LABELS,
    decide,
    priority,
)


# ── decide() — HOLD floor ────────────────────────────────────────────────────

def test_hold_when_confidence_below_floor():
    d = decide(cep50_m=2.0, gdop=1.5, label="tank",
               confidence=HOLD_CONFIDENCE_FLOOR - 0.001)
    assert d.action == "HOLD"
    assert d.weapons_release_required is False


def test_not_hold_at_exactly_floor():
    """Exactly at the floor is not held — the check is strictly less-than."""
    d = decide(cep50_m=2.0, gdop=1.5, label="tank",
               confidence=HOLD_CONFIDENCE_FLOOR)
    assert d.action != "HOLD"


# ── decide() — STRIKE path ───────────────────────────────────────────────────

@pytest.mark.parametrize("label", list(STRIKE_ELIGIBLE_LABELS))
def test_strike_when_all_conditions_met(label):
    d = decide(
        cep50_m=STRIKE_CEP_MAX - 0.1,
        gdop=STRIKE_GDOP_MAX - 0.1,
        label=label,
        confidence=0.9,
    )
    assert d.action == "STRIKE"
    assert d.weapons_release_required is True


def test_strike_boundary_cep_exactly_at_limit_is_recon():
    """CEP50 == limit is NOT within the strike envelope (strict <)."""
    d = decide(cep50_m=STRIKE_CEP_MAX, gdop=1.5, label="tank", confidence=0.9)
    assert d.action == "RECON"


def test_strike_boundary_gdop_exactly_at_limit_is_recon():
    d = decide(cep50_m=5.0, gdop=STRIKE_GDOP_MAX, label="tank", confidence=0.9)
    assert d.action == "RECON"


def test_strike_cep_too_large():
    d = decide(cep50_m=STRIKE_CEP_MAX + 1.0, gdop=1.5, label="tank", confidence=0.9)
    assert d.action == "RECON"
    assert "CEP50" in d.reason


def test_strike_gdop_too_large():
    d = decide(cep50_m=5.0, gdop=STRIKE_GDOP_MAX + 0.1, label="tank", confidence=0.9)
    assert d.action == "RECON"
    assert "GDOP" in d.reason


def test_strike_ineligible_label():
    d = decide(cep50_m=2.0, gdop=1.5, label="drone", confidence=0.9)
    assert d.action == "RECON"
    assert "not strike-eligible" in d.reason


def test_strike_null_label_is_recon():
    d = decide(cep50_m=2.0, gdop=1.5, label=None, confidence=0.9)
    assert d.action == "RECON"


# ── decide() — severity mapping ──────────────────────────────────────────────

def test_severity_high_for_missile():
    d = decide(cep50_m=50.0, gdop=5.0, label="missile_launch", confidence=0.5)
    assert d.severity == "high"


def test_severity_high_for_tank():
    d = decide(cep50_m=50.0, gdop=5.0, label="tank", confidence=0.5)
    assert d.severity == "high"


def test_severity_medium_for_gunshot():
    d = decide(cep50_m=50.0, gdop=5.0, label="gunshot", confidence=0.5)
    assert d.severity == "medium"


def test_severity_low_for_drone():
    d = decide(cep50_m=50.0, gdop=5.0, label="drone", confidence=0.5)
    assert d.severity == "low"


# ── decide() — determinism ───────────────────────────────────────────────────

def test_decide_is_deterministic():
    kwargs = dict(cep50_m=8.0, gdop=2.5, label="tank", confidence=0.7)
    assert decide(**kwargs) == decide(**kwargs)


# ── priority() ───────────────────────────────────────────────────────────────

def test_priority_strike_outranks_recon_same_cep():
    p_strike = priority("tank", "STRIKE", cep50_m=5.0, severity="high")
    p_recon  = priority("tank", "RECON",  cep50_m=5.0, severity="high")
    assert p_strike > p_recon


def test_priority_high_severity_outranks_low():
    p_high = priority("tank",  "RECON", cep50_m=5.0, severity="high")
    p_low  = priority("drone", "RECON", cep50_m=5.0, severity="low")
    assert p_high > p_low


def test_priority_penalty_reduces_score_for_large_cep():
    p_tight = priority("tank", "STRIKE", cep50_m=5.0,  severity="high")
    p_loose = priority("tank", "STRIKE", cep50_m=50.0, severity="high")
    assert p_tight > p_loose


def test_priority_no_penalty_below_floor():
    """CEP50 below 10 m incurs zero penalty — score is flat."""
    p1 = priority("tank", "STRIKE", cep50_m=1.0,  severity="high")
    p2 = priority("tank", "STRIKE", cep50_m=9.99, severity="high")
    assert p1 == p2
