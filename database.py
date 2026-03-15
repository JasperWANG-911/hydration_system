"""
database.py — SQLite schema + all query functions.
Swap sqlite3 for psycopg2 + connection pool for PostgreSQL in production.
No patient PII stored — bed_id only.
"""

import sqlite3
from datetime import date
from contextlib import contextmanager

DB_PATH = "hydration.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS drink_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                bed_id      TEXT    NOT NULL,
                timestamp   INTEGER NOT NULL,   -- unix epoch (seconds)
                delta_ml    REAL,
                duration_s  REAL,
                event_type  TEXT,               -- 'drink' | 'spill' | 'refill'
                confidence  REAL
            );
            CREATE INDEX IF NOT EXISTS idx_bed_ts
                ON drink_events(bed_id, timestamp);

            CREATE TABLE IF NOT EXISTS bed_daily_state (
                bed_id          TEXT    NOT NULL,
                date            TEXT    NOT NULL,   -- 'YYYY-MM-DD'
                cumulative_ml   REAL    DEFAULT 0,
                pace_score      REAL,
                last_drink_ts   INTEGER,
                status          TEXT,               -- GREEN | AMBER | RED | GAP
                cactus_on       INTEGER DEFAULT 0,
                night_mode      INTEGER DEFAULT 0,
                PRIMARY KEY (bed_id, date)
            );

            CREATE TABLE IF NOT EXISTS calibration (
                bed_id      TEXT PRIMARY KEY,
                tare_g      REAL DEFAULT 0,
                last_cal_ts INTEGER
            );
        """)
    print("[DB] Schema initialised.")


# ── Write ──────────────────────────────────────────────────────────────────

def insert_event(bed_id: str, ts: int, delta_ml: float,
                 duration_s: float, event_type: str, confidence: float):
    with db() as conn:
        conn.execute("""
            INSERT INTO drink_events
              (bed_id, timestamp, delta_ml, duration_s, event_type, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (bed_id, ts, delta_ml, duration_s, event_type, confidence))


def upsert_bed_state(bed_id: str, today: str, cumulative_ml: float,
                     pace_score: float | None, last_drink_ts: int | None,
                     status: str, cactus_on: bool, night_mode: bool):
    with db() as conn:
        conn.execute("""
            INSERT INTO bed_daily_state
              (bed_id, date, cumulative_ml, pace_score, last_drink_ts,
               status, cactus_on, night_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bed_id, date) DO UPDATE SET
              cumulative_ml = excluded.cumulative_ml,
              pace_score    = excluded.pace_score,
              last_drink_ts = excluded.last_drink_ts,
              status        = excluded.status,
              cactus_on     = excluded.cactus_on,
              night_mode    = excluded.night_mode
        """, (bed_id, today, cumulative_ml, pace_score, last_drink_ts,
              int(cactus_on), int(night_mode)))


# ── Read ───────────────────────────────────────────────────────────────────

def get_cumulative(bed_id: str, since_ts: int) -> float:
    """Total ml of confirmed drink events for this bed since midnight."""
    with db() as conn:
        row = conn.execute("""
            SELECT COALESCE(SUM(delta_ml), 0) AS total
            FROM drink_events
            WHERE bed_id = ? AND timestamp >= ? AND event_type = 'drink'
        """, (bed_id, since_ts)).fetchone()
    return float(row["total"])


def get_last_drink_ts(bed_id: str, since_ts: int) -> int | None:
    """Unix timestamp of most recent confirmed drink event today."""
    with db() as conn:
        row = conn.execute("""
            SELECT MAX(timestamp) AS last_ts
            FROM drink_events
            WHERE bed_id = ? AND timestamp >= ? AND event_type = 'drink'
        """, (bed_id, since_ts)).fetchone()
    return row["last_ts"] if row else None


def get_all_bed_states(ward_id: str | None = None) -> list[dict]:
    """All bed states for today — used by the dashboard WebSocket."""
    today = date.today().isoformat()
    with db() as conn:
        rows = conn.execute("""
            SELECT * FROM bed_daily_state WHERE date = ?
        """, (today,)).fetchall()
    return [dict(r) for r in rows]


def get_bed_events_today(bed_id: str, since_ts: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute("""
            SELECT * FROM drink_events
            WHERE bed_id = ? AND timestamp >= ?
            ORDER BY timestamp ASC
        """, (bed_id, since_ts)).fetchall()
    return [dict(r) for r in rows]
