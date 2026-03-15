"""
Hydration Monitor — Backend Entry Point
Run with: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from mqtt_client import start_mqtt
from scheduler import start_scheduler
from database import init_db
from routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start MQTT subscriber and scheduler on boot."""
    init_db()
    await start_mqtt()
    start_scheduler()
    yield

app = FastAPI(title="Hydration Monitor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
