"""
Signal Models
=============

Stores individual strategy signals and fused composite signals.

Design:
- Each strategy produces independent signals stored separately.
- Signal fusion combines them into a composite signal (Section 6).
- Every signal records full reasoning for auditability (Section 32).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, TimestampMixin


class Signal(TimestampMixin, Base):
    """
    A trading signal from a strategy or the signal fusion engine.

    Types:
    - "strategy": Individual signal from one strategy (e.g., trend_following)
    - "fused": Composite signal from signal fusion engine
    - "agent": Signal from an AI agent analysis

    The fused signal combines all strategy signals with weights:
        Technical Signal       +0.72
        Momentum               +0.64
        Volume                 +0.51
        Market Regime          +0.80
        News                   -0.20
        Macro                  +0.30
        Order Flow             +0.62
        ────────────────────────────
        Combined Signal        +0.57
    """

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Signal Identity ─────────────────────────────────────────────
    signal_type: Mapped[str] = mapped_column(String(20), nullable=False)  # strategy | fused | agent
    source: Mapped[str] = mapped_column(String(100), nullable=False)       # strategy name or "fusion_engine"
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # ── Signal Value ────────────────────────────────────────────────
    # direction: "buy" | "sell" | "hold" | "no_trade"
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    # strength: -1.0 (strong sell) to +1.0 (strong buy)
    strength: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # ── Expected Outcomes ───────────────────────────────────────────
    expected_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_volatility: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_reward_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_horizon: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ── Market Context ──────────────────────────────────────────────
    market_regime: Mapped[str | None] = mapped_column(String(30), nullable=True)
    volatility_state: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ── Reasoning (Section 32 — full explanation) ───────────────────
    reasoning: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # For fused signals: component signal breakdown
    # Example: {"trend": 0.72, "momentum": 0.64, "news": -0.20, ...}
    component_signals: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Outcome Tracking ────────────────────────────────────────────
    # Filled after the signal's time horizon expires
    actual_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    signal_correct: Mapped[bool | None] = mapped_column(nullable=True)

    # Strategy version that generated this signal
    strategy_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    __table_args__ = (
        Index("ix_signals_symbol_time", "symbol", "generated_at"),
        Index("ix_signals_type_source", "signal_type", "source"),
    )

    def __repr__(self) -> str:
        return (
            f"<Signal {self.source} {self.symbol} {self.direction} "
            f"strength={self.strength:.2f} conf={self.confidence:.2f}>"
        )
