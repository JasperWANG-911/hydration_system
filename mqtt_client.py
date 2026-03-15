"""
mqtt_client.py — Async MQTT subscriber using aiomqtt.

Subscribes to:  hydration/+/+/events   (all wards, all beds)
Publishes to:   hydration/<ward>/<bed>/commands   (cactus ON/OFF)

On each incoming drink event:
  1. Classify (already done on ESP32, but we re-validate server-side)
  2. Write to database
  3. Recalculate pace score for this bed
  4. Decide cactus state → publish command back
  5. Notify WebSocket broadcaster so dashboard updates immediately
"""

import asyncio
import json
import time
from datetime import datetime, date

import aiomqtt

from classifier import classify, EventType
from pace_model import pace_score, get_status, cactus_should_be_on, overnight_critical
from database import insert_event, upsert_bed_state, get_cumulative, get_last_drink_ts
from state import ward_state, notify_ws_update

BROKER_HOST = "localhost"
BROKER_PORT = 1883
TOPIC_SUB   = "hydration/+/+/events"
TOPIC_CMD   = "hydration/{ward}/{bed}/commands"

# In-memory night mode flag (set by scheduler at 22:00 and 07:00)
night_mode: bool = False

_mqtt_client = None   # module-level handle so scheduler can publish too


async def publish_cactus(ward: str, bed: str, on: bool):
    """Publish ON or OFF to the cactus command topic for a specific bed."""
    if _mqtt_client is None:
        return
    topic = TOPIC_CMD.format(ward=ward, bed=bed)
    payload = "ON" if on else "OFF"
    await _mqtt_client.publish(topic, payload)


async def handle_event(topic: str, payload: bytes):
    """Process a single incoming MQTT message."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        print(f"[MQTT] Bad JSON on {topic}: {payload}")
        return

    # Parse topic: hydration/<ward>/<bed>/events
    parts = topic.split("/")
    if len(parts) != 4:
        return
    _, ward, bed_id, _ = parts

    ts          = data.get("ts", int(time.time()))
    delta_ml    = data.get("delta_ml", 0)
    duration_s  = data.get("duration_s", 1)
    event_type  = data.get("event_type", "drink")   # pre-classified by ESP32
    confidence  = data.get("confidence", 0.9)

    # Server-side re-validation of the event type
    # (ESP32 classification is trusted but we sanity-check)
    validated = classify(-delta_ml, duration_s)   # classifier expects delta_g
    if validated.event_type == EventType.NOISE:
        return  # discard noise events

    # Use the server-side classification for storage (more conservative)
    final_type = validated.event_type.value
    final_conf = min(confidence, validated.confidence)

    # Write event to DB
    insert_event(bed_id, ts, delta_ml, duration_s, final_type, final_conf)

    # Recalculate bed state
    now       = datetime.now()
    today     = date.today().isoformat()
    midnight  = int(datetime.combine(date.today(), datetime.min.time()).timestamp())

    cumulative      = get_cumulative(bed_id, midnight)
    last_drink_ts   = get_last_drink_ts(bed_id, midnight)

    mins_since = (
        int((time.time() - last_drink_ts) / 60)
        if last_drink_ts else 9999
    )

    score   = pace_score(cumulative, now)
    status  = get_status(score)
    cactus  = cactus_should_be_on(score, mins_since, night_mode)

    # Overnight critical check (quiet dashboard alert only)
    oc = overnight_critical(cumulative, mins_since) if night_mode else False
    if oc:
        status = "CRITICAL_OVERNIGHT"

    # Persist state
    upsert_bed_state(
        bed_id, today, cumulative, score,
        last_drink_ts, status, cactus, night_mode
    )

    # Push cactus command back to the coaster immediately
    await publish_cactus(ward, bed_id, cactus)

    # Notify WebSocket broadcaster
    notify_ws_update(ward, {
        "bed_id":       bed_id,
        "cumulative_ml": cumulative,
        "pace_score":   score,
        "status":       status,
        "cactus_on":    cactus,
        "last_drink_ts": last_drink_ts,
        "mins_since_drink": mins_since,
    })

    print(f"[MQTT] {bed_id} | {final_type} {delta_ml:.0f}ml "
          f"| cumul={cumulative:.0f}ml | pace={score:.2f if score else 'N/A'} "
          f"| {status} | cactus={'ON' if cactus else 'OFF'}")


async def start_mqtt():
    """Start async MQTT loop in the background."""
    global _mqtt_client

    async def _run():
        global _mqtt_client
        async with aiomqtt.Client(BROKER_HOST, BROKER_PORT) as client:
            _mqtt_client = client
            await client.subscribe(TOPIC_SUB)
            print(f"[MQTT] Subscribed to {TOPIC_SUB}")
            async for message in client.messages:
                await handle_event(str(message.topic), message.payload)

    asyncio.create_task(_run())
