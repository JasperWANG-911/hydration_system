"""
scheduler.py — APScheduler jobs that run continuously in the background.

Jobs:
  every_minute  — recalculate pace score for ALL beds, update cactus states
  night_on      — 22:00 daily, sets night mode flag, turns all cactuses OFF
  night_off     — 07:00 daily, clears night mode flag
  calibration   — 03:00 daily, checks for load cell tare drift
"""

import time
import asyncio
from datetime import datetime, date

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import mqtt_client as mqtt       # import module, not function (avoids circular)
from pace_model import (
    pace_score, get_status, cactus_should_be_on,
    overnight_critical, missed_morning_flag,
)
from database import (
    get_cumulative, get_last_drink_ts,
    upsert_bed_state, get_all_bed_states,
)
from state import ward_state, notify_ws_update

# Known beds — in production this comes from a beds config table or EHR
KNOWN_BEDS: dict[str, list[str]] = {
    "ward-A": ["A01", "A02", "A03", "A04", "A05", "A06"],
    "ward-B": ["B01", "B02", "B03", "B04"],
}

AKI_RISK_BEDS: set[str] = {"A01", "A04", "B02"}   # flagged on admission


async def recalculate_all_beds():
    """
    Runs every minute. For each bed:
      - Pull cumulative intake from DB
      - Compute pace score
      - Decide cactus state
      - Persist updated state
      - Publish cactus command via MQTT
      - Notify WebSocket
    """
    now      = datetime.now()
    today    = date.today().isoformat()
    midnight = int(datetime.combine(date.today(), datetime.min.time()).timestamp())
    night    = mqtt.night_mode

    for ward, beds in KNOWN_BEDS.items():
        for bed_id in beds:
            cumulative    = get_cumulative(bed_id, midnight)
            last_drink_ts = get_last_drink_ts(bed_id, midnight)
            mins_since    = (
                int((time.time() - last_drink_ts) / 60)
                if last_drink_ts else 9999
            )

            score  = pace_score(cumulative, now)
            aki    = bed_id in AKI_RISK_BEDS
            status = get_status(score, aki_risk=aki)
            cactus = cactus_should_be_on(score, mins_since, night)

            # Overnight critical check
            if night and overnight_critical(cumulative, mins_since):
                status = "CRITICAL_OVERNIGHT"

            # Missed morning flag (afternoon only)
            morning_missed = missed_morning_flag(cumulative, now)

            upsert_bed_state(
                bed_id, today, cumulative, score,
                last_drink_ts, status, cactus, night
            )

            await mqtt.publish_cactus(ward, bed_id, cactus)

            notify_ws_update(ward, {
                "bed_id":           bed_id,
                "cumulative_ml":    cumulative,
                "pace_score":       score,
                "status":           status,
                "cactus_on":        cactus,
                "last_drink_ts":    last_drink_ts,
                "mins_since_drink": mins_since,
                "morning_missed":   morning_missed,
                "aki_risk":         aki,
            })


async def activate_night_mode():
    print("[Scheduler] Night mode ON (22:00)")
    mqtt.night_mode = True
    # Turn ALL cactuses OFF
    for ward, beds in KNOWN_BEDS.items():
        for bed_id in beds:
            await mqtt.publish_cactus(ward, bed_id, False)


async def deactivate_night_mode():
    print("[Scheduler] Night mode OFF (07:00)")
    mqtt.night_mode = False


async def run_calibration_check():
    """
    Nightly calibration check at 03:00.
    Placeholder — in production this would read tare weights
    from the DB and compare against baseline, flagging drift > 5g.
    """
    print("[Scheduler] Running calibration check...")
    # TODO: query calibration table, compare tare_g vs baseline
    # Flag beds where drift > 5g to the dashboard


def start_scheduler():
    scheduler = AsyncIOScheduler()

    scheduler.add_job(recalculate_all_beds, "interval", minutes=1, id="pace_recalc")
    scheduler.add_job(activate_night_mode,  "cron",     hour=22, minute=0)
    scheduler.add_job(deactivate_night_mode,"cron",     hour=7,  minute=0)
    scheduler.add_job(run_calibration_check,"cron",     hour=3,  minute=0)

    scheduler.start()
    print("[Scheduler] Started — pace recalc every 60s, night mode at 22:00/07:00")
