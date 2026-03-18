"""API key authentication for Control API endpoints."""

from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from telemelya.server.config import settings

security = HTTPBearer()


async def require_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """FastAPI dependency that validates the API key from Bearer token."""
    allowed = settings.auth_keys_set
    if not allowed:
        # No keys configured — auth is disabled
        return credentials.credentials

    if credentials.credentials not in allowed:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return credentials.credentials
