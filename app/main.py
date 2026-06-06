"""
nest API — main application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import connect_db, disconnect_db
from app.routes import listings, auth, me, shortlist, events


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup and shutdown logic."""
    await connect_db()
    print(f"nest API started in {settings.environment} mode")
    yield
    await disconnect_db()
    print("nest API shut down")


app = FastAPI(
    title="nest API",
    description="Backend for nest — a curated real estate platform.",
    version="0.1.0",
    lifespan=lifespan,
)


# CORS: allow localhost for dev, plus the deployed frontend URL in production.
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if settings.frontend_url:
    # Trim trailing slash if present — common copy/paste mistake.
    allowed_origins.append(settings.frontend_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register route modules
app.include_router(listings.router)
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(shortlist.router)
app.include_router(events.router)


@app.get("/")
async def root():
    """Sanity-check endpoint."""
    return {
        "service": "nest API",
        "version": "0.1.0",
        "environment": settings.environment,
    }


@app.get("/health")
async def health():
    """Liveness check — confirms the app is running and can reach the database."""
    from app.db import pool
    if pool is None:
        return {"status": "starting"}
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
    return {"status": "ok", "db": "connected" if result == 1 else "error"}
