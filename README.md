# Hydration Monitor — Backend

## File Structure

```
backend/
├── main.py          # FastAPI app + startup (MQTT + scheduler)
├── database.py      # SQLite schema + all query functions
├── pace_model.py    # Two-phase hydration pace scoring logic
├── classifier.py    # Weight delta → drink / spill / refill classifier
├── mqtt_client.py   # MQTT subscriber + cactus command publisher
├── scheduler.py     # Minute-by-minute recalc, night mode, calibration
├── state.py         # In-memory ward state + WebSocket broadcaster
├── routes.py        # REST + WebSocket endpoints
├── simulate.py      # Inject template events without hardware
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt

# Start MQTT broker (Raspberry Pi or local for dev)
sudo apt install mosquitto && sudo systemctl start mosquitto

# Start backend
uvicorn main:app --reload --port 8000
```

## Simulate without hardware

```bash
# Inject all past events for the current time of day
python simulate.py

# Stream events in real-time at 60x speed (1 simulated hr per real min)
python simulate.py live 60
```

## API

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/ward/{ward_id}/state`          | Full ward heatmap snapshot |
| GET    | `/ward/{ward_id}/bed/{bed_id}`   | Single bed state + event log |
| WS     | `/ws/ward/{ward_id}`             | Real-time push feed |
| POST   | `/simulate/event`                | Inject test event (dev) |

## WebSocket message format

```json
// On connect — full snapshot
{ "type": "snapshot", "beds": [ {...}, {...} ] }

// On any change — single bed update
{ "type": "update", "bed": {
    "bed_id": "A01",
    "cumulative_ml": 480,
    "pace_score": 0.72,
    "status": "AMBER",
    "cactus_on": false,
    "mins_since_drink": 45,
    "morning_missed": false,
    "aki_risk": true
}}
```

## No PII

The database stores **only bed IDs and drinking events** — no patient
names, NHS numbers, ages, or diagnoses. Bed-to-patient mapping lives
in the hospital EHR and is never written to this system.
