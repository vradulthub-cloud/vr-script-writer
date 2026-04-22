"""
Eclatech Hub API — FastAPI application entry point.

Serves the API backend for the Next.js frontend.
Runs alongside the existing Streamlit app during migration.

Usage:
    uvicorn api.main:app --host 0.0.0.0 --port 8502 --reload

Production (Windows, via NSSM):
    python -m uvicorn api.main:app --host 0.0.0.0 --port 8502
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import require_admin as _require_admin_dep
from api.database import init_db
from api.sync_engine import start_sync_loop, stop_sync_loop
from api.routers import tickets, scenes, scripts, descriptions, models, approvals, compilations, titles, call_sheets, users, notifications, shoots, calendar_events, tasks

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (startup/shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and start sync loop on startup."""
    _log.info("Starting Eclatech Hub API...")
    init_db()
    start_sync_loop()
    _log.info("API ready — sync loop running")
    yield
    _log.info("Shutting down...")
    stop_sync_loop()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Eclatech Hub API",
    version="2.0.0",
    description="Backend API for the Eclatech Hub production management tool.",
    lifespan=lifespan,
)

# CORS — allow the Next.js frontend (running on different port during dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",       # Next.js dev
        "http://localhost:8502",       # API self
        "https://desktop-9d407v9.tail3f755a.ts.net",  # Tailscale (internal)
        "https://desktop-9d407v9.tail3f755a.ts.net:8443",  # Tailscale Funnel (public FastAPI)
        "https://eclatech-hub.vercel.app",  # Vercel production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(tickets.router)
app.include_router(scenes.router)
app.include_router(scripts.router)
app.include_router(descriptions.router)
app.include_router(models.router)
app.include_router(approvals.router)
app.include_router(compilations.router)
app.include_router(titles.router)
app.include_router(call_sheets.router)
app.include_router(users.router)
app.include_router(notifications.router)
app.include_router(shoots.router)
app.include_router(calendar_events.router)
app.include_router(tasks.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    """Health check endpoint."""
    from api.database import get_db, get_sync_meta

    syncs = {}
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM sync_meta").fetchall()
        for r in rows:
            d = dict(r)
            syncs[d["source"]] = {
                "last_synced": d["last_synced_at"],
                "rows": d["row_count"],
                "status": d["status"],
            }

    return {
        "status": "ok",
        "version": "2.0.0",
        "syncs": syncs,
    }


@app.get("/api/sync/status")
async def sync_status():
    """Get the last sync status for all data sources."""
    from api.database import get_db

    with get_db() as conn:
        rows = conn.execute("SELECT * FROM sync_meta ORDER BY source").fetchall()

    return [dict(r) for r in rows]


@app.post("/api/sync/trigger")
async def trigger_sync(_admin: dict = Depends(_require_admin_dep)):
    """Manually trigger a full sync from Google Sheets. Admin only."""
    from api.sync_engine import run_full_sync
    return {"status": "completed", "results": run_full_sync()}


@app.post("/api/sync/trigger/{source}")
async def trigger_sync_one(source: str, _admin: dict = Depends(_require_admin_dep)):
    """Manually trigger a sync for a single source. Admin only.
    Sources: users, tickets, notifications, approvals, scenes, scripts, bookings."""
    from api.sync_engine import (
        sync_users, sync_tickets, sync_notifications, sync_approvals,
        sync_scenes, sync_scripts, sync_bookings,
    )
    from api.database import update_sync_meta
    from fastapi import HTTPException

    funcs = {
        "users": sync_users,
        "tickets": sync_tickets,
        "notifications": sync_notifications,
        "approvals": sync_approvals,
        "scenes": sync_scenes,
        "scripts": sync_scripts,
        "bookings": sync_bookings,
    }
    fn = funcs.get(source)
    if not fn:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source}")
    try:
        count = fn()
        return {"source": source, "row_count": count, "status": "ok"}
    except Exception as exc:
        update_sync_meta(source, status="error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
