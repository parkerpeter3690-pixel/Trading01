"""
System Event, Backtest, and Strategy Promotion Models
=====================================================

Tracks application lifecycle, backtest results, and strategy promotions.

Design:
- SystemEvent: Application startup, shutdown, errors, health checks.
- Backtest: Complete backtest results with performance metrics.
- StrategyPromotion: Audit trail for strategy level changes (Section 14).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, TimestampMixin


class SystemEvent(TimestampMixin, Base):
    """
    Application lifecycle event.

    Tracks: startup, shutdown, errors, health checks, configuration changes.
    """

    __tablename__ = "system_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_time: Mapped[datetime] = mapped_column(nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="info")
    component: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_sys_type_time", "event_type", "event_time"),
    )


class Backtest(TimestampMixin, Base):
    """
    A completed backtest run with full results.

    Stores strategy, parameters, period, and all performance metrics
    for reproducibility and comparison.
    """

    __tablename__ = "backtests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    run_at: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # ── Configuration ───────────────────────────────────────────────
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    symbols: Mapped[list] = mapped_column(JSONB, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)

    # ── Period ──────────────────────────────────────────────────────
    start_date: Mapped[datetime] = mapped_column(nullable=False)
    end_date: Mapped[datetime] = mapped_column(nullable=False)
    is_walk_forward: Mapped[bool] = mapped_column(Boolean, default=False)
    is_out_of_sample: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Results ─────────────────────────────────────────────────────
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0)
    losing_trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Return Metrics ──────────────────────────────────────────────
    total_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    annualized_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_trade_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_trade_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    worst_trade_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Risk Metrics ────────────────────────────────────────────────
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    sortino_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    calmar_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Execution Costs ─────────────────────────────────────────────
    total_commission: Mapped[float] = mapped_column(Float, default=0.0)
    total_slippage: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Detailed Results ────────────────────────────────────────────
    equity_curve: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    monthly_returns: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    regime_performance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    trade_log: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # ── Validation ──────────────────────────────────────────────────
    passed: Mapped[bool | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_bt_strategy", "strategy_name", "strategy_version"),
    )


class StrategyPromotion(TimestampMixin, Base):
    """
    Audit trail for strategy promotion/demotion (Section 14).

    Records:
    - PROMOTE: Strategy moved to a higher level
    - HOLD: Strategy stays at current level
    - DEMOTE: Strategy moved to a lower level
    - DISABLE: Strategy disabled entirely

    Live activation (→ PRODUCTION) requires explicit human approval.
    """

    __tablename__ = "strategy_promotions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promotion_time: Mapped[datetime] = mapped_column(nullable=False, index=True)

    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # Level change
    from_level: Mapped[str] = mapped_column(String(20), nullable=False)
    to_level: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # promote|hold|demote|disable

    # Criteria that were evaluated
    criteria_met: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    """
    Example:
    {
        "min_trades": {"required": 50, "actual": 67, "passed": true},
        "max_drawdown": {"required": 10.0, "actual": 7.2, "passed": true},
        "min_sharpe": {"required": 1.0, "actual": 1.4, "passed": true},
        "stable_across_regimes": {"passed": true}
    }
    """

    # Authorization
    approved_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    human_approved: Mapped[bool | None] = mapped_column(nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_promo_strategy", "strategy_name"),
    )
