"""
Auth utilities: JWT encoding/decoding, password/token hashing, current-user dependency.

JWTs we issue contain:
    sub:  user UUID (string)
    exp:  expiration timestamp (set automatically by python-jose)
    type: 'access' or 'refresh'

The frontend stores both tokens in localStorage and sends the access token
in every request as 'Authorization: Bearer <token>'.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings
from app.db import get_db

# 'Bearer' token scheme — auto-extracts the token from Authorization header.
# auto_error=False so we can return our own 401 messages.
security = HTTPBearer(auto_error=False)


# ----------------------------------------------------------------
# Token creation
# ----------------------------------------------------------------

def create_access_token(user_id: UUID) -> str:
    """Short-lived (15 min) JWT used on every API request."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_refresh_token() -> tuple[str, str]:
    """
    Long-lived refresh token.
    Returns (raw_token, token_hash). Send the raw to the client, store the hash in DB.
    """
    raw = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash


def hash_refresh_token(raw: str) -> str:
    """Recompute the hash of a refresh token for lookup."""
    return hashlib.sha256(raw.encode()).hexdigest()


# ----------------------------------------------------------------
# Token decoding
# ----------------------------------------------------------------

def decode_access_token(token: str) -> UUID:
    """Decode a JWT access token and return the user_id. Raises if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Wrong token type")
        return UUID(payload["sub"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Malformed token")


# ----------------------------------------------------------------
# OTP generation
# ----------------------------------------------------------------

def generate_otp() -> str:
    """Generate a 4-digit OTP. Uses secrets for cryptographic randomness."""
    return f"{secrets.randbelow(10000):04d}"


# ----------------------------------------------------------------
# FastAPI dependency: get the current user
# ----------------------------------------------------------------

async def get_current_user_id(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UUID:
    """Require a valid access token. Returns the user_id."""
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(creds.credentials)


async def get_current_user_id_optional(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[UUID]:
    """Like get_current_user_id but returns None instead of raising if no token."""
    if creds is None:
        return None
    try:
        return decode_access_token(creds.credentials)
    except HTTPException:
        return None