"""
Order Models
============

Tracks the full lifecycle of every order: created → submitted → filled/rejected/cancelled.

Design:
- Supports all order types: market, limit, stop, stop-limit, trailing stop.
- Idempotency via unique client_order_id prevents duplicate submissions.
- Every order goes through the risk gate before reaching the broker.
- Fill details (price, quantity, fees) stored for execution analysis.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, TimestampMixin


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"           # Created, not yet submitted
    SUBMITTED = "submitted"       # Sent to broker
    PARTIALLY_FILLED = "partial"  # Some quantity filled
    FILLED = "filled"             # Fully filled
    CANCELLED = "cancelled"       # Cancelled by user or system
    REJECTED = "rejected"         # Rejected by risk engine or broker
    EXPIRED = "expired"           # Time-in-force expired
    FAILED = "failed"             # Execution failure


class Order(TimestampMixin, Base):
    """
    An order in the trading system — paper or live.

    Every order passes through:
    1. Signal → Trade Proposal
    2. Risk Engine validation
    3. Order submission
    4. Fill tracking
    5. Execution quality analysis
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_order_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Order Details ───────────────────────────────────────────────
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    limit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    trail_percent: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Status ──────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OrderStatus.PENDING.value
    )
    environment: Mapped[str] = mapped_column(String(20), nullable=False, default="paper")

    # ── Fill Details ────────────────────────────────────────────────
    filled_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    avg_fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission: Mapped[float] = mapped_column(Float, default=0.0)
    slippage: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Timestamps ──────────────────────────────────────────────────
    submitted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # ── Time in Force ───────────────────────────────────────────────
    time_in_force: Mapped[str] = mapped_column(String(10), default="day")
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # ── Risk Validation ─────────────────────────────────────────────
    risk_check_passed: Mapped[bool | None] = mapped_column(nullable=True)
    risk_check_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Attribution ─────────────────────────────────────────────────
    trade_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    strategy_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_orders_symbol_status", "symbol", "status"),
        Index("ix_orders_env_status", "environment", "status"),
        Index("ix_orders_submitted", "submitted_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Order {self.client_order_id} {self.side} {self.symbol} "
            f"qty={self.quantity} [{self.status}]>"
        )
