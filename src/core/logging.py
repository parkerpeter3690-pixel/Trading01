"""
Structured Logging
==================

Provides structured JSON logging via structlog for complete auditability.

Design:
- Every log entry includes a correlation_id for request tracing.
- Separate loggers for different subsystems: trading, risk, agent, system.
- JSON output in production, colored console output in development.
- All trading decisions are logged at INFO level for audit trail.

Usage:
    from src.core.logging import get_logger

    logger = get_logger("trading")
    logger.info("order_placed", symbol="AAPL", side="buy", quantity=100)
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

import structlog

from src.core.config import settings

# ── Context Variable for Correlation ID ──────────────────────────────────
# Every request/operation gets a unique ID that flows through all log entries.
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Get the current correlation ID, or generate a new one."""
    cid = correlation_id_var.get()
    if not cid:
        cid = str(uuid4())[:8]
        correlation_id_var.set(cid)
    return cid


def set_correlation_id(cid: str | None = None) -> str:
    """Set a correlation ID for the current context."""
    cid = cid or str(uuid4())[:8]
    correlation_id_var.set(cid)
    return cid


# ── Custom Processors ────────────────────────────────────────────────────

def add_correlation_id(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add correlation ID to every log entry."""
    event_dict["correlation_id"] = get_correlation_id()
    return event_dict


def add_app_info(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add application name and environment to log entries."""
    event_dict["app"] = settings.app_name
    event_dict["env"] = settings.app_env.value
    return event_dict


# ── Configure structlog ─────────────────────────────────────────────────

def configure_logging() -> None:
    """
    Configure structured logging for the entire application.

    Call this once at application startup.
    """
    # Shared processors for all loggers
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        add_correlation_id,
        add_app_info,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.is_development:
        # Development: colored console output for readability
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            pad_event=40,
        )
    else:
        # Production: JSON output for log aggregation (ELK, Datadog, etc.)
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, settings.app_log_level.upper()))

    # Suppress noisy third-party loggers
    for noisy_logger in ["urllib3", "asyncio", "sqlalchemy.engine"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


# ── Logger Factory ───────────────────────────────────────────────────────

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a named logger for a subsystem.

    Subsystem names:
    - "trading"   : Trade execution, orders, fills
    - "risk"      : Risk engine events, limit breaches, kill switch
    - "agent"     : AI agent decisions, reasoning, debates
    - "strategy"  : Strategy signals, parameter changes
    - "market"    : Market data, indicators, regime changes
    - "news"      : News ingestion, impact analysis
    - "system"    : Application lifecycle, health checks
    - "mcp"       : MCP tool calls, validation, errors

    Usage:
        logger = get_logger("trading")
        logger.info("order_filled", order_id="abc123", fill_price=150.25)
    """
    return structlog.get_logger(name)
