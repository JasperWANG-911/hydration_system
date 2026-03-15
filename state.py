"""
state.py — Shared in-memory ward state + WebSocket connection registry.

ward_state holds the latest bed data for each ward so the WebSocket
can push immediately without a DB round-trip.

notify_ws_update() is called by both the MQTT handler and the scheduler
after any bed state change — it fans out the update to all connected
dashboard clients.
"""

import asyncio
from collections import defaultdict
from typing import Callable

# { ward_id: { bed_id: {...bed_state_dict} } }
ward_state: dict[str, dict] = defaultdict(dict)

# { ward_id: [asyncio.Queue, ...] }  — one queue per connected WebSocket client
_ws_queues: dict[str, list[asyncio.Queue]] = defaultdict(list)


def notify_ws_update(ward_id: str, bed_update: dict):
    """
    Called whenever a bed's state changes.
    Updates in-memory state and enqueues update for all active WS clients.
    """
    bed_id = bed_update["bed_id"]
    ward_state[ward_id][bed_id] = bed_update

    for q in _ws_queues[ward_id]:
        try:
            q.put_nowait(bed_update)
        except asyncio.QueueFull:
            pass   # slow client — skip this update, they'll catch up on next push


def register_ws(ward_id: str) -> asyncio.Queue:
    """Register a new WebSocket client and return its queue."""
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    _ws_queues[ward_id].append(q)
    return q


def deregister_ws(ward_id: str, q: asyncio.Queue):
    """Remove a disconnected WebSocket client's queue."""
    try:
        _ws_queues[ward_id].remove(q)
    except ValueError:
        pass
