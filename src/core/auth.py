"""
Authentication & Authorization
==============================

Provides authentication for the API and MCP server.

Architecture:
- API Dashboard: JWT token-based auth with role-based access control.
- MCP Server: Token-based auth (shared secret).
- Roles: viewer (read-only), trader (can trigger paper trades), admin (full access).

Security Rules:
- The AI CANNOT change its own permissions.
- The AI CANNOT access broker credentials directly.
- Live trading activation requires admin role + explicit confirmation.

Usage:
    from src.core.auth import get_current_user, require_role

    @router.get("/positions")
    async def get_positions(user: User = Depends(get_current_user)):
        ...
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from src.core.config import settings

# ── Roles ────────────────────────────────────────────────────────────────

class Role(str, Enum):
    """
    User roles with increasing privilege levels.

    - VIEWER: Read-only access to dashboard and data.
    - TRADER: Can trigger paper trades, run backtests, manage strategies.
    - ADMIN: Full access — can modify risk limits, activate live trading,
             manage kill switch. Required for all critical operations.
    """
    VIEWER = "viewer"
    TRADER = "trader"
    ADMIN = "admin"


# Role hierarchy: higher roles include all lower role permissions
ROLE_HIERARCHY: dict[Role, set[Role]] = {
    Role.ADMIN: {Role.ADMIN, Role.TRADER, Role.VIEWER},
    Role.TRADER: {Role.TRADER, Role.VIEWER},
    Role.VIEWER: {Role.VIEWER},
}


# ── User Model ───────────────────────────────────────────────────────────

class User(BaseModel):
    """Authenticated user with role."""
    user_id: str
    username: str
    role: Role


# ── JWT Token Management ────────────────────────────────────────────────

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

security = HTTPBearer()


def create_access_token(
    user_id: str,
    username: str,
    role: Role,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: Unique user identifier
        username: Display name
        role: User role
        expires_delta: Custom expiration (default: 24 hours)
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=JWT_EXPIRATION_HOURS)
    )
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "role": role.value,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(
        payload,
        settings.app_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.app_secret_key.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI Dependencies ────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    FastAPI dependency to extract the current authenticated user.

    Usage:
        @router.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            ...
    """
    payload = decode_token(credentials.credentials)
    return User(
        user_id=payload["sub"],
        username=payload["username"],
        role=Role(payload["role"]),
    )


def require_role(required_role: Role):
    """
    FastAPI dependency factory to enforce role-based access.

    Usage:
        @router.post("/activate-live-trading")
        async def activate(user: User = Depends(require_role(Role.ADMIN))):
            ...
    """
    async def role_checker(
        user: User = Depends(get_current_user),
    ) -> User:
        allowed_roles = ROLE_HIERARCHY.get(user.role, set())
        if required_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role.value}' required. You have '{user.role.value}'.",
            )
        return user
    return role_checker


# ── MCP Authentication ──────────────────────────────────────────────────

def validate_mcp_token(token: str) -> bool:
    """
    Validate MCP server authentication token.

    This is a simple shared-secret check. In production,
    consider using OAuth2 or mutual TLS.
    """
    return token == settings.mcp_auth_token.get_secret_value()
