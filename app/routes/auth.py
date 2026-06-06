"""
/auth endpoints — phone OTP sign-in and token refresh.

Flow:
    POST /auth/request-otp   { phone }             -> { sent: true }
    POST /auth/verify-otp    { phone, code }       -> { access_token, refresh_token, user }
    POST /auth/refresh       { refresh_token }     -> { access_token }
    POST /auth/sign-out      (requires auth)       -> { ok: true }
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.db import get_db
from app.auth import (
    create_access_token, create_refresh_token, hash_refresh_token,
    generate_otp, get_current_user_id,
)
from app.config import settings


router = APIRouter(prefix="/auth", tags=["auth"])


# ----------------------------------------------------------------
# Request/response models
# ----------------------------------------------------------------

class PhoneRequest(BaseModel):
    phone: str = Field(min_length=10, max_length=15)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
        """Strip non-digits and ensure it's a 10-digit Indian mobile."""
        digits = re.sub(r"\D", "", v)
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]   # drop country code
        if len(digits) != 10:
            raise ValueError("Phone must be a 10-digit Indian mobile")
        if not digits[0] in "6789":
            raise ValueError("Phone must start with 6, 7, 8 or 9")
        return digits


class VerifyOtpRequest(BaseModel):
    phone: str
    code: str = Field(min_length=4, max_length=4)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        if len(digits) != 10:
            raise ValueError("Phone must be a 10-digit Indian mobile")
        return digits


class UpdateProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str


# ----------------------------------------------------------------
# POST /auth/request-otp
# ----------------------------------------------------------------

@router.post("/request-otp")
async def request_otp(body: PhoneRequest, db=Depends(get_db)):
    """
    Generate an OTP for this phone number and (eventually) send it via SMS.

    For local dev, the OTP is logged to the console instead of sent.
    In production this will call MSG91 or similar.
    """
    code = generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    async with db.acquire() as conn:
        # Rate limit: max 5 OTPs per phone per hour.
        recent_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM otps
            WHERE phone = $1 AND created_at > NOW() - INTERVAL '1 hour'
            """,
            body.phone,
        )
        if recent_count >= 5:
            raise HTTPException(status_code=429, detail="Too many OTP requests. Try again in an hour.")

        await conn.execute(
            "INSERT INTO otps (phone, code, expires_at) VALUES ($1, $2, $3)",
            body.phone, code, expires_at,
        )

    # STUB: in production, replace with MSG91 API call.
    print(f"\n  >>> OTP for +91 {body.phone}: {code} (valid 10 min)\n")

    return {"sent": True}


# ----------------------------------------------------------------
# POST /auth/verify-otp
# ----------------------------------------------------------------

@router.post("/verify-otp", response_model=AuthResponse)
async def verify_otp(body: VerifyOtpRequest, db=Depends(get_db)):
    """
    Verify the OTP. On success:
    - Find or create the user by phone
    - Issue access + refresh tokens
    - Return tokens and user info
    """
    async with db.acquire() as conn:
        # Find the most recent unconsumed OTP for this phone.
        otp_row = await conn.fetchrow(
            """
            SELECT id, code, expires_at, attempts
            FROM otps
            WHERE phone = $1 AND consumed_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            body.phone,
        )

        if otp_row is None:
            raise HTTPException(status_code=400, detail="No OTP requested for this phone")

        if otp_row["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="OTP expired. Request a new one.")

        if otp_row["attempts"] >= 3:
            raise HTTPException(status_code=400, detail="Too many wrong attempts. Request a new OTP.")

        if otp_row["code"] != body.code:
            # Increment attempts counter.
            await conn.execute(
                "UPDATE otps SET attempts = attempts + 1 WHERE id = $1",
                otp_row["id"],
            )
            raise HTTPException(status_code=400, detail="Wrong code")

        # OTP is valid — mark consumed.
        await conn.execute(
            "UPDATE otps SET consumed_at = NOW() WHERE id = $1",
            otp_row["id"],
        )

        # Find or create the user.
        user_row = await conn.fetchrow(
            "SELECT id, phone, name, current_intent, city FROM users WHERE phone = $1",
            body.phone,
        )
        if user_row is None:
            user_row = await conn.fetchrow(
                """
                INSERT INTO users (phone) VALUES ($1)
                RETURNING id, phone, name, current_intent, city
                """,
                body.phone,
            )

        user_id: UUID = user_row["id"]

        # Issue tokens.
        access_token = create_access_token(user_id)
        raw_refresh, refresh_hash = create_refresh_token()
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)

        await conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES ($1, $2, $3)
            """,
            user_id, refresh_hash, refresh_expires,
        )

    return AuthResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        user={
            "id": str(user_row["id"]),
            "phone": user_row["phone"],
            "name": user_row["name"],
            "current_intent": user_row["current_intent"],
            "city": user_row["city"],
        },
    )


# ----------------------------------------------------------------
# POST /auth/refresh
# ----------------------------------------------------------------

@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(body: RefreshRequest, db=Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    token_hash = hash_refresh_token(body.refresh_token)

    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT user_id, expires_at, revoked_at
            FROM refresh_tokens
            WHERE token_hash = $1
            """,
            token_hash,
        )

        if row is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        if row["revoked_at"] is not None:
            raise HTTPException(status_code=401, detail="Refresh token revoked")
        if row["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Refresh token expired")

        # Mark it used (helpful for analytics, not required).
        await conn.execute(
            "UPDATE refresh_tokens SET last_used_at = NOW() WHERE token_hash = $1",
            token_hash,
        )

        access_token = create_access_token(row["user_id"])

    return AccessTokenResponse(access_token=access_token)


# ----------------------------------------------------------------
# POST /auth/sign-out
# ----------------------------------------------------------------

@router.post("/sign-out")
async def sign_out(
    body: RefreshRequest,
    user_id: UUID = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """Revoke the refresh token used by this session."""
    token_hash = hash_refresh_token(body.refresh_token)
    async with db.acquire() as conn:
        await conn.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = NOW()
            WHERE token_hash = $1 AND user_id = $2
            """,
            token_hash, user_id,
        )
    return {"ok": True}