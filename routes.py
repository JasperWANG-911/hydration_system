"""
routes.py — FastAPI REST + WebSocket endpoints.

GET  /ward/{ward_id}/state         → current state of all beds (snapshot)
GET  /ward/{ward_id}/bed/{bed_id}  → events + state for one bed today
WS   /ws/ward/{ward_id}            → real-time push on every bed state change
POST /simulate/event               → inject a test event (dev only)
"""

import time
import json
from datetime import date, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from database import get_all_bed_states, get_bed_events_today, insert_event
from state import ward_state, register_ws, deregister_ws
from classifier import classify, EventType
from pace_model import pace_score, get_status, cactus_should_be_on
import mqtt_client as mqtt

router = APIRouter()


# ── REST ────────────────────────────────────────────────────────────────────

@router.get("/ward/{ward_id}/state")
async def get_ward_state(ward_id: str):
    """
    Snapshot of all bed states for this ward.
    Returns in-memory state (fast) with DB fallback.
    """
    mem = ward_state.get(ward_id)
    if mem:
        return {"ward_id": ward_id, "beds": list(mem.values())}
    # DB fallback on cold start
    db_states = get_all_bed_states(ward_id)
    return {"ward_id": ward_id, "beds": db_states}


@router.get("/ward/{ward_id}/bed/{bed_id}")
async def get_bed_detail(ward_id: str, bed_id: str):
    """
    Single bed — current state + today's drink event log.
    Used when a nurse clicks into a bed on the heatmap.
    """
    midnight = int(datetime.combine(date.today(), datetime.min.time()).timestamp())
    events   = get_bed_events_today(bed_id, midnight)
    state    = ward_state.get(ward_id, {}).get(bed_id, {})

    return {
        "ward_id": ward_id,
        "bed_id":  bed_id,
        "state":   state,
        "events":  events,
    }


# ── WebSocket ───────────────────────────────────────────────────────────────

@router.websocket("/ws/ward/{ward_id}")
async def ward_websocket(websocket: WebSocket, ward_id: str):
    """
    Real-time WebSocket feed for a ward's heatmap.

    On connect: immediately sends the full current ward state.
    Then streams individual bed updates as they arrive (event-driven,
    not polling) — each message is a single bed_update dict.
    """
    await websocket.accept()
    q = register_ws(ward_id)

    try:
        # Send full snapshot on connect so the UI renders immediately
        snapshot = ward_state.get(ward_id, {})
        await websocket.send_json({
            "type": "snapshot",
            "beds": list(snapshot.values()),
        })

        # Stream updates
        while True:
            update = await q.get()
            await websocket.send_json({
                "type":   "update",
                "bed":    update,
            })

    except WebSocketDisconnect:
        deregister_ws(ward_id, q)


# ── Simulation endpoint (dev only) ─────────────────────────────────────────

class SimEvent(BaseModel):
    ward_id:    str = "ward-A"
    bed_id:     str = "A01"
    delta_ml:   float = 150.0
    duration_s: float = 12.0


@router.post("/simulate/event")
async def simulate_event(ev: SimEvent):
    """
    Inject a fake drink event — useful for testing without hardware.
    Mimics exactly what the ESP32 would publish to MQTT.
    """
    classified = classify(-ev.delta_ml, ev.duration_s)

    if classified.event_type == EventType.NOISE:
        return {"result": "ignored", "reason": "below noise floor"}

    ts = int(time.time())
    insert_event(
        ev.bed_id, ts, ev.delta_ml, ev.duration_s,
        classified.event_type.value, classified.confidence
    )

    # Trigger the same post-event logic the MQTT handler uses
    payload = json.dumps({
        "bed":        ev.bed_id,
        "ts":         ts,
        "delta_ml":   ev.delta_ml,
        "duration_s": ev.duration_s,
        "event_type": classified.event_type.value,
        "confidence": classified.confidence,
    }).encode()

    await mqtt.handle_event(
        f"hydration/{ev.ward_id}/{ev.bed_id}/events", payload
    )

    return {
        "result":     "ok",
        "event_type": classified.event_type.value,
        "confidence": classified.confidence,
        "delta_ml":   ev.delta_ml,
    }
