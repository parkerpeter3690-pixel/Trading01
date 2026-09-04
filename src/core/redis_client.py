"""
Redis Connection & Cache Layer
==============================

Provides Redis connectivity for three purposes:
1. Data Caching  — market data, indicators, and news with TTL
2. Pub/Sub Bus   — real-time events (new trades, kill switch, agent decisions)
3. Rate Limiting — per-tool and per-user rate limits for MCP

Design:
- Uses redis.asyncio for non-blocking operations.
- hiredis parser for maximum performance.
- All keys are namespaced to avoid collisions.

Usage:
    from src.core.redis_client import redis_client, cache

    # Simple cache
    await cache.set("market:AAPL:price", 150.25, ttl=60)
    price = await cache.get("market:AAPL:price")

    # Pub/Sub
    await redis_client.publish("events:trade", json.dumps(trade_data))
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from src.core.config import settings

# ── Redis Connection Pool ────────────────────────────────────────────────

redis_pool = aioredis.ConnectionPool.from_url(
    settings.redis_url,
    max_connections=50,
    decode_responses=True,
)

redis_client = aioredis.Redis(connection_pool=redis_pool)


# ── Cache Abstraction ────────────────────────────────────────────────────

class TradingCache:
    """
    Type-safe cache layer over Redis.

    All cache keys are namespaced with 'trading:' prefix.
    Supports JSON serialization for complex objects.
    """

    PREFIX = "trading"

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    def _key(self, key: str) -> str:
        """Namespace all cache keys."""
        return f"{self.PREFIX}:{key}"

    async def get(self, key: str) -> Any | None:
        """Get a cached value, returns None if not found or expired."""
        raw = await self._client.get(self._key(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """
        Cache a value with TTL in seconds.

        Args:
            key: Cache key (auto-namespaced)
            value: Any JSON-serializable value
            ttl: Time-to-live in seconds (default 5 minutes)
        """
        serialized = json.dumps(value, default=str)
        await self._client.setex(self._key(key), ttl, serialized)

    async def delete(self, key: str) -> None:
        """Remove a cached value."""
        await self._client.delete(self._key(key))

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        return bool(await self._client.exists(self._key(key)))

    async def get_or_set(self, key: str, factory: Any, ttl: int = 300) -> Any:
        """
        Get from cache, or compute and cache if missing.

        Args:
            key: Cache key
            factory: Async callable that produces the value
            ttl: Time-to-live in seconds
        """
        cached = await self.get(key)
        if cached is not None:
            return cached
        value = await factory()
        await self.set(key, value, ttl)
        return value

    async def flush_namespace(self, namespace: str) -> int:
        """
        Delete all keys matching a namespace pattern.

        Example: cache.flush_namespace("market:AAPL") clears all AAPL market data.
        """
        pattern = self._key(f"{namespace}:*")
        keys = []
        async for key in self._client.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            await self._client.delete(*keys)
        return len(keys)


# ── Rate Limiter ─────────────────────────────────────────────────────────

class RateLimiter:
    """
    Token bucket rate limiter using Redis.

    Used by MCP middleware to prevent excessive tool calls.
    """

    PREFIX = "ratelimit"

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    async def is_allowed(
        self,
        identifier: str,
        max_requests: int = 60,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """
        Check if a request is allowed under rate limits.

        Args:
            identifier: Unique identifier (e.g., user_id, tool_name)
            max_requests: Maximum requests in window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        key = f"{self.PREFIX}:{identifier}"
        current = await self._client.get(key)

        if current is None:
            await self._client.setex(key, window_seconds, 1)
            return True, max_requests - 1

        count = int(current)
        if count >= max_requests:
            return False, 0

        await self._client.incr(key)
        return True, max_requests - count - 1


# ── Event Bus ────────────────────────────────────────────────────────────

class EventBus:
    """
    Redis Pub/Sub event bus for real-time system events.

    Channels:
    - events:trade       — New trade executions
    - events:signal      — New trading signals
    - events:risk        — Risk events (limit breaches, kill switch)
    - events:agent       — Agent decisions and debates
    - events:news        — Breaking news with impact analysis
    - events:system      — System events (heartbeat, errors)
    """

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    async def publish(self, channel: str, data: dict[str, Any]) -> None:
        """Publish an event to a channel."""
        await self._client.publish(channel, json.dumps(data, default=str))

    async def subscribe(self, *channels: str):
        """
        Subscribe to one or more channels.

        Returns an async pubsub object for iteration.
        """
        pubsub = self._client.pubsub()
        await pubsub.subscribe(*channels)
        return pubsub


# ── Module-level instances ───────────────────────────────────────────────

cache = TradingCache(redis_client)
rate_limiter = RateLimiter(redis_client)
event_bus = EventBus(redis_client)


async def close_redis() -> None:
    """Gracefully close the Redis connection pool."""
    await redis_client.aclose()
    await redis_pool.aclose()
