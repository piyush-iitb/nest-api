"""
Database connection pool using asyncpg.

We use a single connection pool for the entire application lifetime.
The pool manages multiple connections so concurrent requests don't block each other.
"""

import asyncpg
from typing import Optional
from app.config import settings

# Global pool, initialized at app startup.
pool: Optional[asyncpg.Pool] = None


async def connect_db() -> None:
    """Create the connection pool. Called once at app startup."""
    global pool
    pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
        timeout=30,
    )


async def disconnect_db() -> None:
    """Close the connection pool. Called once at app shutdown."""
    global pool
    if pool is not None:
        await pool.close()
        pool = None


async def get_db() -> asyncpg.Pool:
    """
    Dependency for FastAPI routes that need database access.
    Returns the global pool — individual queries acquire a connection from it.
    """
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool