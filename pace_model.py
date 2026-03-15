"""
pace_model.py — Hydration pace scoring and alert logic.

Two-phase daily target:
  Phase 1  07:00 → 12:00   0 → 750 ml   (~150 ml/hr)
  Phase 2  12:00 → 21:00   750 → 1500 ml (~83 ml/hr)

Alerts are pace-based, not absolute — a patient with 200 ml at 10 am
is critically behind even though 200 ml sounds fine in isolation.
"""

from datetime import datetime, time


DAILY_TARGET_ML  = 1500.0
MIDDAY_TARGET_ML = 750.0          # 50% must be hit by 12:00
PHASE1_START     = 7.0            # hours (float)
PHASE1_END       = 12.0
PHASE2_END       = 21.0

# Alert thresholds
THRESH_GREEN     = 0.80           # pace ≥ 80% → GREEN
THRESH_AMBER     = 0.50           # pace ≥ 50% → AMBER, else RED
THRESH_AKI_AMBER = 0.60           # tighter threshold for AKI-risk patients

CACTUS_PACE_TRIGGER   = 0.50      # pace below this AND ...
CACTUS_TIME_TRIGGER_M = 90        # ... no drink for this many minutes → cactus ON
NIGHT_CRITICAL_ML     = 800.0     # overnight: only alert if below this
NIGHT_CRITICAL_MINS   = 360       # and no drink for 6 hours


def _hour_float(dt: datetime) -> float:
    """Convert datetime to fractional hour, e.g. 10:30 → 10.5"""
    return dt.hour + dt.minute / 60 + dt.second / 3600


def expected_intake_ml(now: datetime) -> float | None:
    """
    Returns the expected cumulative intake at `now`.
    Returns None during night hours (21:00–07:00) — model is paused.
    """
    h = _hour_float(now)

    if h < PHASE1_START or h > PHASE2_END:
        return None                           # night — no expectation

    if h <= PHASE1_END:
        # Linear: 0 → 750 ml over 5 hours
        progress = (h - PHASE1_START) / (PHASE1_END - PHASE1_START)
        return MIDDAY_TARGET_ML * progress

    # Linear: 750 → 1500 ml over 9 hours
    progress = (h - PHASE1_END) / (PHASE2_END - PHASE1_END)
    return MIDDAY_TARGET_ML + MIDDAY_TARGET_ML * progress


def pace_score(cumulative_ml: float, now: datetime) -> float | None:
    """
    Returns a score in [0, ∞) where 1.0 = exactly on target.
    Returns None during night hours.
    """
    target = expected_intake_ml(now)
    if target is None or target == 0:
        return None
    return cumulative_ml / target


def get_status(score: float | None, aki_risk: bool = False) -> str:
    """Map pace score to GREEN / AMBER / RED."""
    if score is None:
        return "NIGHT"
    amber_thresh = THRESH_AKI_AMBER if aki_risk else THRESH_AMBER
    if score >= THRESH_GREEN:
        return "GREEN"
    if score >= amber_thresh:
        return "AMBER"
    return "RED"


def cactus_should_be_on(
    score: float | None,
    mins_since_last_drink: int,
    night_mode: bool,
    critical_overnight: bool = False,
) -> bool:
    """
    Returns True if the cactus light should illuminate.
    
    Daytime rule:  pace < 50% AND no drink for 90+ minutes
    Overnight:     only if cumulative < 800 ml AND no drink for 6+ hours
                   (fires to nurse dashboard only — cactus stays dark)
    """
    if night_mode:
        # Cactus always dark overnight — only a dashboard alert fires
        return False

    if score is None:
        return False

    return score < CACTUS_PACE_TRIGGER and mins_since_last_drink >= CACTUS_TIME_TRIGGER_M


def overnight_critical(cumulative_ml: float, mins_since_last_drink: int) -> bool:
    """
    True if patient needs a quiet overnight nurse alert
    (cactus stays dark but dashboard flags the bed).
    """
    return (
        cumulative_ml < NIGHT_CRITICAL_ML
        and mins_since_last_drink >= NIGHT_CRITICAL_MINS
    )


def missed_morning_flag(cumulative_ml: float, now: datetime) -> bool:
    """
    True at 12:00 if patient has drunk less than 50% of morning target.
    This flag persists into the afternoon — the model compounds, not resets.
    """
    h = _hour_float(now)
    return h >= PHASE1_END and cumulative_ml < MIDDAY_TARGET_ML
