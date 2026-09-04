"""
Agent Decision Models
=====================

Records every AI agent decision with full reasoning chain.

Design:
- Every decision answers the 15 questions from Section 7.
- Stores the multi-agent debate record (Section 21).
- Links to resulting orders and trades for attribution.
- Enables "Why did you take this trade?" queries (Section 32).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, TimestampMixin


class AgentDecision(TimestampMixin, Base):
    """
    A complete AI agent decision record.

    Every decision includes:
    - Full trading decision protocol answers (15 questions)
    - Multi-agent debate transcript
    - Signal fusion breakdown
    - Risk assessment
    - Final action: BUY | SELL | HOLD | NO_TRADE

    This is the primary audit record for "Why did you take this trade?"
    """

    __tablename__ = "agent_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    decision_time: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # ── Decision ────────────────────────────────────────────────────
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # buy|sell|hold|no_trade
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # ── Trading Decision Protocol (Section 7 — 15 questions) ───────
    # Stored as structured JSONB for complete reasoning
    decision_protocol: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    """
    Example:
    {
        "market_situation": "Gold rallying on USD weakness",
        "market_regime": "trending",
        "trade_thesis": "Momentum continuation on macro shift",
        "strategies_agreeing": ["trend_following", "momentum"],
        "strategies_disagreeing": ["mean_reversion"],
        "relevant_news": ["Fed hints at rate pause"],
        "priced_in_factors": ["Expected rate pause partially priced"],
        "invalidation_level": 1920.0,
        "stop_loss": 1915.0,
        "target": 1960.0,
        "risk_reward": 2.5,
        "position_size_pct": 3.0,
        "max_possible_loss": -1500.0,
        "adverse_scenario": "USD strengthens on surprise data",
        "better_alternatives": "None identified"
    }
    """

    # ── Signal Fusion (Section 6) ───────────────────────────────────
    signal_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    """
    Example:
    {
        "technical": 0.72,
        "momentum": 0.64,
        "volume": 0.51,
        "regime": 0.80,
        "news": -0.20,
        "macro": 0.30,
        "combined": 0.57
    }
    """
    combined_signal: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Multi-Agent Debate (Section 21) ─────────────────────────────
    debate_transcript: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    """
    Example:
    {
        "bull_agent": {"thesis": "...", "confidence": 0.75},
        "bear_agent": {"thesis": "...", "confidence": 0.35},
        "technical_agent": {"analysis": "...", "signal": 0.72},
        "news_agent": {"analysis": "...", "impact": "low"},
        "risk_agent": {"assessment": "...", "approved": true},
        "consensus": "buy"
    }
    """

    # ── Market Context ──────────────────────────────────────────────
    market_regime: Mapped[str | None] = mapped_column(String(30), nullable=True)
    volatility_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    market_analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    news_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Risk Assessment ─────────────────────────────────────────────
    risk_assessment: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    position_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_risk_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Execution Result ────────────────────────────────────────────
    order_placed: Mapped[bool | None] = mapped_column(nullable=True)
    order_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    trade_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Agent Metadata ──────────────────────────────────────────────
    orchestrator_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    llm_tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_decisions_symbol_time", "symbol", "decision_time"),
        Index("ix_decisions_action", "action"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentDecision {self.decision_id} {self.action} {self.symbol} "
            f"conf={self.confidence:.2f}>"
        )
