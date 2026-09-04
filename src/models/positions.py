"""
Position Models
===============

Tracks current open positions in the portfolio.

Design:
- One row per symbol per environment (paper/live).
- Unrealized P&L updated in real-time from market data.
- Supports portfolio-level analysis (Section 20 — correlation, exposure).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, TimestampMixin


class Position(TimestampMixin, Base):
    """
    A current open position in the portfolio.

    Updated continuously with unrealized P&L from market data.
    Used by the Risk Engine for exposure and drawdown calculations.
    Used by the Portfolio Agent for correlation and diversification analysis.
    """

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Position Identity ───────────────────────────────────────────
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # long | short
    environment: Mapped[str] = mapped_column(String(20), nullable=False, default="paper")

    # ── Size ────────────────────────────────────────────────────────
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    avg_entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    position_value: Mapped[float] = mapped_column(Float, nullable=False)

    # ── Current Market ──────────────────────────────────────────────
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── P&L ─────────────────────────────────────────────────────────
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Risk ────────────────────────────────────────────────────────
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    trailing_stop: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Portfolio Weight ────────────────────────────────────────────
    portfolio_weight_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector: Mapped[str | None] = mapped_column(String(50), nullable=True)
    asset_class: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── Timing ──────────────────────────────────────────────────────
    opened_at: Mapped[datetime] = mapped_column(nullable=False)
    last_updated: Mapped[datetime | None] = mapped_column(nullable=True)

    # ── Attribution ─────────────────────────────────────────────────
    strategy_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trade_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_positions_symbol_env", "symbol", "environment", unique=True),
        Index("ix_positions_env", "environment"),
    )

    def __repr__(self) -> str:
        return (
            f"<Position {self.side} {self.quantity} {self.symbol} "
            f"@{self.avg_entry_price} PnL={self.unrealized_pnl:.2f}>"
        )
