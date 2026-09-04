"""
Portfolio Snapshot Models
=========================

Point-in-time snapshots of the entire portfolio state.

Design:
- Snapshots taken at configurable intervals (default: every 15 minutes).
- Enables equity curve plotting and drawdown analysis.
- Stores complete position breakdown for historical analysis.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, TimestampMixin


class PortfolioSnapshot(TimestampMixin, Base):
    """
    Point-in-time snapshot of the portfolio.

    Taken periodically to enable:
    - Equity curve visualization
    - Drawdown calculation
    - Portfolio risk tracking over time
    - Correlation analysis history
    """

    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_time: Mapped[datetime] = mapped_column(nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, default="paper")

    # ── Value ───────────────────────────────────────────────────────
    total_value: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    positions_value: Mapped[float] = mapped_column(Float, nullable=False)

    # ── P&L ─────────────────────────────────────────────────────────
    daily_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    daily_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    total_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    total_pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Risk Metrics ────────────────────────────────────────────────
    peak_value: Mapped[float] = mapped_column(Float, nullable=False)
    drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Exposure ────────────────────────────────────────────────────
    total_exposure: Mapped[float] = mapped_column(Float, default=0.0)
    long_exposure: Mapped[float] = mapped_column(Float, default=0.0)
    short_exposure: Mapped[float] = mapped_column(Float, default=0.0)
    net_exposure: Mapped[float] = mapped_column(Float, default=0.0)
    leverage: Mapped[float] = mapped_column(Float, default=0.0)
    num_positions: Mapped[int] = mapped_column(Integer, default=0)

    # ── Position Breakdown ──────────────────────────────────────────
    # Example: [{"symbol": "AAPL", "weight": 5.2, "pnl": 120.50}, ...]
    positions_detail: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # ── Sector / Asset Exposure ─────────────────────────────────────
    # Example: {"tech": 15.2, "energy": 8.1, "crypto": 5.0}
    sector_exposure: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    asset_class_exposure: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_portfolio_env_time", "environment", "snapshot_time"),
    )

    def __repr__(self) -> str:
        return (
            f"<PortfolioSnapshot {self.snapshot_time} "
            f"value={self.total_value:.2f} dd={self.drawdown_pct:.1f}%>"
        )
