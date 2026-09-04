"""
Risk Event Models
=================

Logs every risk limit breach, kill switch activation, and risk check.

Design:
- Every risk event is immutable and cannot be deleted by the AI (Section 27).
- Kill switch events trigger immediate trading halt.
- Risk checks are logged even when they PASS, for full auditability.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, TimestampMixin


class RiskEventType(str, Enum):
    LIMIT_BREACH = "limit_breach"       # A risk limit was exceeded
    KILL_SWITCH = "kill_switch"         # Kill switch activated
    RISK_CHECK_PASS = "check_pass"     # Order passed risk check
    RISK_CHECK_FAIL = "check_fail"     # Order failed risk check
    EXPOSURE_WARNING = "warning"        # Approaching a limit
    DRAWDOWN_ALERT = "drawdown"        # Significant drawdown detected
    CORRELATION_ALERT = "correlation"   # High correlation detected


class RiskEvent(TimestampMixin, Base):
    """
    A risk event in the trading system.

    The AI CANNOT:
    - Delete risk events
    - Modify risk limits
    - Disable the kill switch
    - Override risk check failures

    All risk events are immutable audit records.
    """

    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_time: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # ── Event Classification ────────────────────────────────────────
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    environment: Mapped[str] = mapped_column(String(20), nullable=False, default="paper")

    # ── Details ─────────────────────────────────────────────────────
    limit_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    limit_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Context ─────────────────────────────────────────────────────
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    portfolio_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Resolution ──────────────────────────────────────────────────
    action_taken: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        Index("ix_risk_type_time", "event_type", "event_time"),
        Index("ix_risk_severity", "severity"),
    )

    def __repr__(self) -> str:
        return f"<RiskEvent [{self.severity}] {self.event_type}: {self.description[:50]}>"
