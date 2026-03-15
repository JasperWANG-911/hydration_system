"""
classifier.py — Classifies raw load cell weight deltas into events.

Three event types:
  drink   — patient consumed fluid (counts toward intake)
  spill   — rapid large drop (does NOT count)
  refill  — rapid weight increase (resets cup baseline)

Thresholds are conservative — a false negative (missed drink) is
preferable to a false positive (counting a spill as intake).
"""

from dataclasses import dataclass
from enum import Enum


class EventType(str, Enum):
    DRINK   = "drink"
    SPILL   = "spill"
    REFILL  = "refill"
    NOISE   = "noise"           # below minimum threshold — ignore


@dataclass
class WeightEvent:
    event_type: EventType
    delta_ml:   float           # positive = increase, negative = decrease
    duration_s: float
    confidence: float           # 0–1, used by dashboard for data quality


# ── Thresholds ─────────────────────────────────────────────────────────────

MIN_DRINK_ML       = 20.0      # below this → noise, ignore
MAX_DRINK_ML       = 350.0     # above this in one event → suspect
MIN_DRINK_SECS     = 3.0       # genuine sip takes at least 3 seconds
MAX_DRINK_SECS     = 60.0      # longer than 60s → probably multiple sips merged

SPILL_RATE_ML_S    = 30.0      # ml/s rate that indicates a spill (fast drop)
REFILL_MIN_ML      = 50.0      # minimum increase to count as a refill


def classify(delta_g: float, duration_s: float) -> WeightEvent:
    """
    delta_g   : weight change in grams (negative = liquid left the cup)
    duration_s: time in seconds over which this delta was recorded

    Assumes density of water: 1 g ≈ 1 ml.
    """
    delta_ml = -delta_g     # negative delta_g means liquid left → positive ml consumed
    rate = abs(delta_ml) / max(duration_s, 0.1)

    # ── Refill: weight went up significantly ──
    if delta_ml < -REFILL_MIN_ML:
        return WeightEvent(
            event_type=EventType.REFILL,
            delta_ml=abs(delta_ml),
            duration_s=duration_s,
            confidence=0.95,
        )

    # ── Below noise floor ──
    if delta_ml < MIN_DRINK_ML:
        return WeightEvent(EventType.NOISE, delta_ml, duration_s, confidence=0.0)

    # ── Spill: very fast large drop ──
    if rate >= SPILL_RATE_ML_S and delta_ml > MIN_DRINK_ML:
        return WeightEvent(
            event_type=EventType.SPILL,
            delta_ml=delta_ml,
            duration_s=duration_s,
            confidence=0.80,
        )

    # ── Duration checks for drink ──
    if duration_s < MIN_DRINK_SECS:
        # Too fast for a genuine sip — might still be a small spill
        return WeightEvent(
            event_type=EventType.SPILL,
            delta_ml=delta_ml,
            duration_s=duration_s,
            confidence=0.65,
        )

    # ── Suspiciously large single event ──
    confidence = 0.90
    if delta_ml > MAX_DRINK_ML:
        confidence = 0.60   # possible but unusual — flag for review

    if duration_s > MAX_DRINK_SECS:
        confidence = min(confidence, 0.70)

    return WeightEvent(
        event_type=EventType.DRINK,
        delta_ml=delta_ml,
        duration_s=duration_s,
        confidence=confidence,
    )


def smooth_readings(readings: list[float], window: int = 5) -> list[float]:
    """
    Rolling average filter to remove vibration/tremor noise
    before computing deltas.
    readings: list of raw grams from HX711
    """
    if len(readings) < window:
        return readings
    smoothed = []
    for i in range(len(readings)):
        start = max(0, i - window + 1)
        smoothed.append(sum(readings[start:i+1]) / (i - start + 1))
    return smoothed


def compute_delta(before_g: float, after_g: float) -> float:
    """Weight delta in grams (negative means cup got lighter)."""
    return after_g - before_g
