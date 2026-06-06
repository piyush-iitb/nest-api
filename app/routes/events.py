"""
Behavioral events — signals from the frontend that feed lead scoring.

POST /events    — record one event (anonymous allowed)

Events have a flexible JSONB payload so we can capture different event types
without schema changes. Examples:
    { "type": "listing_view",  "payload": { "listing_id": "..." } }
    { "type": "search",        "payload": { "city": "Mumbai", "filters": {...} } }
    { "type": "compare_add",   "payload": { "listing_id": "..." } }
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.db import get_db
from app.auth import get_current_user_id_optional


router = APIRouter(prefix="/events", tags=["events"])


# Whitelist of event types we accept. Prevents random garbage in the events table.
ALLOWED_EVENT_TYPES = {
    "listing_view",
    "listing_image_view",
    "search",
    "shortlist_add",
    "shortlist_remove",
    "compare_add",
    "compare_remove",
    "share_listing",
    "contact_attempt",   # user tried to contact but was gated by intent
}


class EventRequest(BaseModel):
    type: str = Field(description="Event type. Must be in the allowed set.")
    payload: dict = Field(default_factory=dict, description="Free-form event metadata")


@router.post("", status_code=201)
async def log_event(
    body: EventRequest,
    user_id: Optional[UUID] = Depends(get_current_user_id_optional),
    db=Depends(get_db),
):
    """
    Log a behavioral event.

    Note: this endpoint accepts both authenticated and anonymous requests.
    For anonymous users, user_id is NULL — useful for tracking pre-signup interest.
    """
    if body.type not in ALLOWED_EVENT_TYPES:
        # We don't raise — silently drop unknown types so a stale frontend
        # doesn't generate errors. Log it so we know to add it.
        print(f"  ⚠ Dropped event with unknown type: {body.type}")
        return {"ok": False, "reason": "unknown_type"}

    async with db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (user_id, event_type, payload)
            VALUES ($1, $2, $3::jsonb)
            """,
            user_id, body.type, _json_dumps(body.payload),
        )

    return {"ok": True}


def _json_dumps(obj: dict) -> str:
    """asyncpg wants JSONB as a string. Python's json handles UUIDs poorly, so use repr fallback."""
    import json
    return json.dumps(obj, default=str)