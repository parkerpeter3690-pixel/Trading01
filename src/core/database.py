"""
Async Database Engine
=====================

Provides the async SQLAlchemy engine, session factory, and base model class.

Architecture:
- Uses asyncpg for non-blocking PostgreSQL access.
- Connection pooling configured for concurrent agent operations.
- All database access flows through async sessions — never blocking the event loop.

Usage:
    from src.core.database import get_session, Base

    async with get_session() as session:
        result = await session.execute(select(Trade))
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import MetaData, event
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from src.core.config import settings

# ── Naming Convention for Constraints ────────────────────────────────────
# Ensures Alembic auto-generates clean, predictable constraint names.
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


# ── Base Model ───────────────────────────────────────────────────────────

class Base(AsyncAttrs, DeclarativeBase):
    """
    Base class for all ORM models.

    Provides:
    - AsyncAttrs for lazy-loading async relationships
    - Shared metadata with naming conventions
    - Common audit columns (created_at, updated_at)
    """
    metadata = metadata


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at audit columns.
    Every trading table must include this for full auditability.
    """
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


# ── Engine & Session Factory ─────────────────────────────────────────────

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,       # Detect stale connections
    pool_recycle=3600,         # Recycle connections every hour
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,    # Prevent lazy-load issues after commit
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.

    Automatically commits on success, rolls back on exception.
    Every database operation in the system should use this.

    Example:
        async with get_session() as session:
            session.add(Trade(...))
            # auto-commits here
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session_dep() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for injecting database sessions into route handlers.

    Usage:
        @router.get("/trades")
        async def get_trades(session: AsyncSession = Depends(get_session_dep)):
            ...
    """
    async with get_session() as session:
        yield session


async def init_db() -> None:
    """
    Initialize database tables.
    In production, use Alembic migrations instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Gracefully close the database engine."""
    await engine.dispose()
