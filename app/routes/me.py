"""
/me endpoint — info about the currently signed-in user.

GET /me     -> current user record
PATCH /me   -> update profile (name, intent, city)
"""

from typing import Optional, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import get_db
from app.auth import get_current_user_id


router = APIRouter(prefix="/me", tags=["me"])


class UserResponse(BaseModel):
    id: str
    phone: str
    name: Optional[str] = None
    current_intent: Optional[Literal["casual", "soon", "serious"]] = None
    city: Optional[str] = None


class UpdateMeRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=120)
    current_intent: Optional[Literal["casual", "soon", "serious"]] = None
    city: Optional[str] = Field(None, max_length=60)


@router.get("", response_model=UserResponse)
async def get_me(
    user_id: UUID = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """Return the currently authenticated user."""
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, phone, name, current_intent, city FROM users WHERE id = $1",
            user_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=str(row["id"]),
        phone=row["phone"],
        name=row["name"],
        current_intent=row["current_intent"],
        city=row["city"],
    )


@router.patch("", response_model=UserResponse)
async def update_me(
    body: UpdateMeRequest,
    user_id: UUID = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """Update the user's profile. Only fields you pass get changed."""

    # Build a dynamic UPDATE based on which fields were sent.
    updates = []
    params: list = []

    if body.name is not None:
        params.append(body.name)
        updates.append(f"name = ${len(params)}")
    if body.current_intent is not None:
        params.append(body.current_intent)
        updates.append(f"current_intent = ${len(params)}")
    if body.city is not None:
        params.append(body.city)
        updates.append(f"city = ${len(params)}")

    if not updates:
        # Nothing to update — just return the current state.
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, phone, name, current_intent, city FROM users WHERE id = $1",
                user_id,
            )
    else:
        params.append(user_id)
        query = f"""
            UPDATE users
            SET {', '.join(updates)}
            WHERE id = ${len(params)}
            RETURNING id, phone, name, current_intent, city
        """
        async with db.acquire() as conn:
            row = await conn.fetchrow(query, *params)

            # Audit: if intent changed, log it to the intents table.
            if body.current_intent is not None:
                await conn.execute(
                    "INSERT INTO intents (user_id, intent) VALUES ($1, $2)",
                    user_id, body.current_intent,
                )

    return UserResponse(
        id=str(row["id"]),
        phone=row["phone"],
        name=row["name"],
        current_intent=row["current_intent"],
        city=row["city"],
    )