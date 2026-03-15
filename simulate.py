"""
simulate.py — Injects realistic template events into the running backend
without needing any hardware or MQTT broker.

Run alongside the FastAPI server:
  python simulate.py

Scenarios map to the same ones used in the React frontend simulator.
"""

import time
import requests
from datetime import datetime

BASE_URL = "http://localhost:8000"

# (ward, bed, scenario_name, events: list of (hour_float, ml))
SCENARIOS = [
    ("ward-A", "A01", "Good morning drinker", [
        (7.5, 180), (8.5, 150), (9.5, 160), (10.5, 140), (11.5, 130),
        (13.0, 90), (14.5, 80), (16.0, 70), (17.5, 75),
    ]),
    ("ward-A", "A02", "Missed morning, recovered", [
        (8.0, 60), (10.0, 80), (12.5, 200), (13.5, 180), (15.0, 150), (17.0, 120),
    ]),
    ("ward-A", "A03", "Barely drinking", [
        (8.5, 60), (11.0, 80), (14.0, 70), (17.0, 60),
    ]),
    ("ward-A", "A04", "Strong all day", [
        (7.2, 200), (8.0, 180), (9.0, 160), (10.0, 150), (11.0, 140),
        (12.5, 120), (13.5, 110), (15.0, 100), (16.5, 90), (18.0, 80),
    ]),
    ("ward-B", "B01", "Nothing so far", []),
    ("ward-B", "B02", "Barely drinking", [
        (9.0, 50), (13.0, 60),
    ]),
]


def hour_to_seconds_from_midnight(h: float) -> float:
    """Convert fractional hour to seconds since midnight."""
    return h * 3600


def inject_event(ward: str, bed: str, delta_ml: float, duration_s: float = 12.0):
    """POST a single drink event to the simulate endpoint."""
    resp = requests.post(f"{BASE_URL}/simulate/event", json={
        "ward_id":    ward,
        "bed_id":     bed,
        "delta_ml":   delta_ml,
        "duration_s": duration_s,
    })
    data = resp.json()
    print(f"  → {bed}: {data['event_type']} {delta_ml:.0f}ml "
          f"(conf={data.get('confidence', 0):.2f})")
    return data


def run_all_scenarios():
    """
    Injects all template events immediately (replaying today's data).
    Only injects events whose 'hour' has already passed today.
    """
    now_hour = datetime.now().hour + datetime.now().minute / 60
    total = 0

    print(f"\n[Sim] Current time: {datetime.now().strftime('%H:%M')} "
          f"(hour {now_hour:.2f})\n")

    for ward, bed, name, events in SCENARIOS:
        print(f"[Sim] {ward}/{bed} — {name}")
        past_events = [(h, ml) for h, ml in events if h <= now_hour]
        if not past_events:
            print("  (no events due yet)")
            continue
        for h, ml in past_events:
            inject_event(ward, bed, ml)
            time.sleep(0.1)   # small delay to avoid hammering the server
        total += len(past_events)

    print(f"\n[Sim] Done. {total} events injected.")


def run_live_stream(speed_factor: float = 60.0):
    """
    Stream events in 'real time' sped up by speed_factor.
    speed_factor=60 means 1 simulated hour passes every real minute.
    Useful for watching the heatmap update live.
    """
    now_hour = 7.0
    all_events = sorted(
        [(ward, bed, h, ml) for ward, bed, _, events in SCENARIOS for h, ml in events],
        key=lambda x: x[2]
    )

    print(f"\n[Sim] Live stream at {speed_factor}x speed. Ctrl+C to stop.\n")
    for ward, bed, h, ml in all_events:
        wait_real_s = (h - now_hour) * 3600 / speed_factor
        if wait_real_s > 0:
            print(f"  [Sim] Waiting {wait_real_s:.1f}s for {h:.2f}h event...")
            time.sleep(wait_real_s)
        now_hour = h
        inject_event(ward, bed, ml)


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "live":
        run_live_stream(speed_factor=float(sys.argv[2]) if len(sys.argv) > 2 else 60.0)
    else:
        run_all_scenarios()
