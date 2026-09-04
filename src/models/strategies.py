"""
Strategy Models
===============

Strategy definitions and versioned parameter tracking.

Design:
- Every strategy has immutable versions (Section 13).
- Parameters, training period, validation period, and performance
  are stored per version for rollback capability.
- Promotion status tracks the strategy's lifecycle (Section 14):
  BACKTEST → REPLAY → PAPER → SHADOW → MICRO → LIMITED → PRODUCTION

Example version lifecycle:
    GoldTrend_v1.0 → GoldTrend_v1.1 → GoldTrend_v2.0 (rejected) → v1.1 restored
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, TimestampMixin


class PromotionLevel(str, Enum):
    """Strategy promotion levels (Section 14)."""
    BACKTEST = "backtest"           # Level 0
    HISTORICAL_REPLAY = "replay"   # Level 1
    PAPER_TRADING = "paper"        # Level 2
    SHADOW_TRADING = "shadow"      # Level 3
    MICRO_CAPITAL = "micro"        # Level 4
    LIMITED_LIVE = "limited"       # Level 5
    PRODUCTION = "production"      # Level 6
    DISABLED = "disabled"          # Explicitly disabled


class Strategy(TimestampMixin, Base):
    """
    A trading strategy definition.

    Each strategy has a name, description, supported asset classes,
    supported market regimes, and one or more versions.
    """

    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # What this strategy supports
    supported_assets: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    supported_regimes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    supported_timeframes: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Current active version
    active_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Promotion level
    promotion_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PromotionLevel.BACKTEST.value
    )

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Versions relationship
    versions: Mapped[list["StrategyVersion"]] = relationship(
        "StrategyVersion", back_populates="strategy", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Strategy '{self.name}' v{self.active_version} [{self.promotion_level}]>"


class StrategyVersion(TimestampMixin, Base):
    """
    An immutable snapshot of strategy parameters and performance.

    Once created, a version's parameters CANNOT be modified.
    To change parameters, create a new version.
    This ensures complete reproducibility of any past trade.

    Performance metrics are updated as the strategy runs.
    """

    __tablename__ = "strategy_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("strategies.id"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)

    # ── Parameters (immutable once set) ─────────────────────────────
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # ── Training/Validation Period ──────────────────────────────────
    training_start: Mapped[datetime | None] = mapped_column(nullable=True)
    training_end: Mapped[datetime | None] = mapped_column(nullable=True)
    validation_start: Mapped[datetime | None] = mapped_column(nullable=True)
    validation_end: Mapped[datetime | None] = mapped_column(nullable=True)

    # ── Performance Metrics ─────────────────────────────────────────
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    sortino_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_trade_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    calmar_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Regime Performance ──────────────────────────────────────────
    # Example: {"trending": {"win_rate": 0.65, "sharpe": 1.2}, ...}
    regime_performance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Validation Status ───────────────────────────────────────────
    backtest_passed: Mapped[bool | None] = mapped_column(nullable=True)
    walk_forward_passed: Mapped[bool | None] = mapped_column(nullable=True)
    out_of_sample_passed: Mapped[bool | None] = mapped_column(nullable=True)
    paper_trading_passed: Mapped[bool | None] = mapped_column(nullable=True)
    statistical_significance: Mapped[bool | None] = mapped_column(nullable=True)

    # ── Status ──────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_rejected: Mapped[bool] = mapped_column(Boolean, default=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Notes / changelog
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="versions")

    __table_args__ = (
        Index("ix_sv_strategy_version", "strategy_id", "version", unique=True),
    )

    def __repr__(self) -> str:
        status = "active" if self.is_active else ("rejected" if self.is_rejected else "inactive")
        return f"<StrategyVersion {self.strategy_id} v{self.version} [{status}]>"
