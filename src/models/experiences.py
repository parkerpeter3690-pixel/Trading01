"""
Agent Experience Models
=======================

Post-trade learning records — the "What did you learn?" database (Section 16).

Design:
- Every closed trade generates an experience record.
- Captures prediction vs actual outcome, error classification, and lessons.
- Used by the Meta-Agent (Section 17) to identify recurring failure patterns.
- Enables the adaptive learning loop (Section 11).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, TimestampMixin


class AgentExperience(TimestampMixin, Base):
    """
    A post-trade learning record.

    Answers "What did you learn?" with:
    - Prediction vs actual outcome
    - Error classification
    - Strategy performance in this context
    - Market regime at the time
    - Execution quality
    - Whether a strategy modification is proposed

    Example (Section 16):
        Experience #18291
        Asset: GOLD | Regime: HIGH_VOLATILITY | Strategy: EVENT_DRIVEN
        News: FED | Signal: SHORT | Confidence: 0.81
        Expected: -2.1% | Actual: +0.7% | Outcome: LOSS
        Error: Market had already priced in event.
        Lesson: Reduce event-driven confidence when pre-event positioning
                indicates high pricing-in probability.
    """

    __tablename__ = "agent_experiences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experience_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # ── Trade Reference ─────────────────────────────────────────────
    trade_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ── Context ─────────────────────────────────────────────────────
    market_regime: Mapped[str] = mapped_column(String(30), nullable=False)
    volatility_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    market_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    news_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Agent's Reasoning at the Time ───────────────────────────────
    agent_reasoning: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    signal_direction: Mapped[str] = mapped_column(String(10), nullable=False)
    signal_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # ── Trade Details ───────────────────────────────────────────────
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float, nullable=False)
    position_size: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Prediction vs Actual ────────────────────────────────────────
    predicted_return_pct: Mapped[float] = mapped_column(Float, nullable=False)
    actual_return_pct: Mapped[float] = mapped_column(Float, nullable=False)
    prediction_error_pct: Mapped[float] = mapped_column(Float, nullable=False)

    # ── Outcome ─────────────────────────────────────────────────────
    outcome: Mapped[str] = mapped_column(String(10), nullable=False)  # win | loss | breakeven
    net_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    risk_amount: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Excursion ───────────────────────────────────────────────────
    max_adverse_excursion_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_favorable_excursion_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Execution Quality ───────────────────────────────────────────
    execution_quality: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Error Analysis ──────────────────────────────────────────────
    error_classification: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    lesson_learned: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Strategy Modification Proposal ──────────────────────────────
    modification_proposed: Mapped[bool] = mapped_column(Boolean, default=False)
    proposed_modification: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    modification_validated: Mapped[bool | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_exp_strategy", "strategy_name", "strategy_version"),
        Index("ix_exp_regime", "market_regime"),
        Index("ix_exp_outcome", "outcome"),
        Index("ix_exp_error", "error_classification"),
    )

    def __repr__(self) -> str:
        return (
            f"<Experience {self.experience_id} {self.symbol} {self.strategy_name} "
            f"predicted={self.predicted_return_pct:+.1f}% actual={self.actual_return_pct:+.1f}%>"
        )
