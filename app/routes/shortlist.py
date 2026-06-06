"""
Shortlist endpoints — the user's saved listings.

POST   /me/shortlist/{listing_id}   — add a listing to the shortlist
DELETE /me/shortlist/{listing_id}   — remove it
GET    /me/shortlist                — list all shortlisted listings (full data, not just IDs)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.auth import get_current_user_id
from app.routes.listings import ListingSummary, _row_to_summary


router = APIRouter(prefix="/me/shortlist", tags=["shortlist"])


@router.get("", response_model=list[ListingSummary])
async def list_shortlist(
    user_id: UUID = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """Return all listings the user has shortlisted, with full listing data."""
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT l.*
            FROM listings l
            JOIN shortlists s ON s.listing_id = l.id
            WHERE s.user_id = $1 AND l.status = 'active'
            ORDER BY s.created_at DESC
            """,
            user_id,
        )
    return [_row_to_summary(r) for r in rows]


@router.post("/{listing_id}", status_code=201)
async def add_to_shortlist(
    listing_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """Add a listing to the user's shortlist. Idempotent — adding twice is fine."""
    async with db.acquire() as conn:
        # Make sure the listing exists and is active.
        listing_exists = await conn.fetchval(
            "SELECT 1 FROM listings WHERE id = $1 AND status = 'active'",
            listing_id,
        )
        if not listing_exists:
            raise HTTPException(status_code=404, detail="Listing not found")

        # ON CONFLICT DO NOTHING makes this idempotent.
        await conn.execute(
            """
            INSERT INTO shortlists (user_id, listing_id) VALUES ($1, $2)
            ON CONFLICT (user_id, listing_id) DO NOTHING
            """,
            user_id, listing_id,
        )
    return {"ok": True}


@router.delete("/{listing_id}", status_code=204)
async def remove_from_shortlist(
    listing_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """Remove a listing from the user's shortlist. Returns 204 No Content."""
    async with db.acquire() as conn:
        await conn.execute(
            "DELETE FROM shortlists WHERE user_id = $1 AND listing_id = $2",
            user_id, listing_id,
        )
    return None