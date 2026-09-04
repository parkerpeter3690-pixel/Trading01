"""
Trade Models
============

Stores completed trades with full audit trail.

Design:
- Every trade links back to the signal, strategy, and agent decision that caused it.
- Maximum adverse/favorable excursion tracked for learning (Section 11).
- Execution quality metrics for shadow trading comparison (Section 15).
- Both paper and live trades use the same model for consistency.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, TimestampMixin


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    PARTIALLY_CLOSED = "partially_closed"
    CANCELLED = "cancelled"


class TradeEnvironment(str, Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    SHADOW = "shadow"
    LIVE = "live"


class Trade(TimestampMixin, Base):
    """
    A completed trade with full audit trail.

    Stores everything needed to answer:
    - "Why did you take this trade?" (Section 32)
    - "What did you learn?" (Section 32)
    """

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # ── Trade Identity ──────────────────────────────────────────────
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TradeStatus.OPEN.value)

    # ── Entry ───────────────────────────────────────────────────────
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    entry_time: Mapped[datetime] = mapped_column(nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    position_value: Mapped[float] = mapped_column(Float, nullable=False)

    # ── Exit ────────────────────────────────────────────────────────
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_time: Mapped[datetime | None] = mapped_column(nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── Risk Management ─────────────────────────────────────────────
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    trailing_stop: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_reward_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── P&L ─────────────────────────────────────────────────────────
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission: Mapped[float] = mapped_column(Float, default=0.0)
    slippage: Mapped[float] = mapped_column(Float, default=0.0)
    net_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Excursion Tracking (Section 11) ─────────────────────────────
    max_adverse_excursion: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_favorable_excursion: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    mfe_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Execution Quality (Section 15 — shadow comparison) ──────────
    expected_entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_slippage: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_slippage: Mapped[float | None] = mapped_column(Float, nullable=True)
    execution_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Attribution ─────────────────────────────────────────────────
    strategy_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    strategy_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    signal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("signals.id"), nullable=True)
    decision_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("agent_decisions.id"), nullable=True
    )

    # ── Market Context at Entry ─────────────────────────────────────
    market_regime: Mapped[str | None] = mapped_column(String(30), nullable=True)
    volatility_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    market_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Full reasoning (Section 32) ─────────────────────────────────
    entry_reasoning: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    exit_reasoning: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Post-trade learning ─────────────────────────────────────────
    mistake_classification: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lesson_learned: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_trades_symbol_time", "symbol", "entry_time"),
        Index("ix_trades_env_status", "environment", "status"),
        Index("ix_trades_strategy", "strategy_name", "strategy_version"),
    )

    def __repr__(self) -> str:
        return (
            f"<Trade {self.trade_id} {self.side} {self.symbol} "
            f"@{self.entry_price} [{self.status}]>"
        )
