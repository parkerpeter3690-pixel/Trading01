"""
News & Economic Events Models
=============================

Stores financial news events with LLM-analyzed impact and economic calendar events.

Design:
- NewsEvent stores both raw news AND the AI's interpretation.
- Expected vs actual market reaction is tracked for learning (Section 4).
- EconomicEvent stores scheduled releases (CPI, GDP, employment).
- JSONB fields for flexible structured data that varies by event type.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, TimestampMixin


class NewsEvent(TimestampMixin, Base):
    """
    Financial news event with AI-analyzed impact.

    Implements the Section 4 news intelligence pipeline:
    Event → Entity → Asset → Direction → Magnitude → Time Horizon
    → Confidence → Historical Analogues → Market Reaction

    The 'actual_reaction' field is filled AFTER the event to enable
    expected-vs-actual learning (news-market correlation engine).
    """

    __tablename__ = "news_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Raw News Data ───────────────────────────────────────────────
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── AI Analysis (Section 4 pipeline) ────────────────────────────
    event_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entities_affected: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    assets_affected: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Expected impact analysis
    expected_direction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    expected_magnitude: Mapped[str | None] = mapped_column(String(20), nullable=True)
    expected_time_horizon: Mapped[str | None] = mapped_column(String(20), nullable=True)
    impact_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_volatility: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # AI reasoning and historical analogues
    reasoning: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    historical_analogues: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # ── Actual Market Reaction (filled post-event) ──────────────────
    actual_direction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    actual_magnitude_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    reaction_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reaction_analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    prediction_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # ── Sentiment ───────────────────────────────────────────────────
    raw_sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_news_published", "published_at"),
        Index("ix_news_category", "category"),
        Index("ix_news_processed", "processed"),
    )

    def __repr__(self) -> str:
        return f"<NewsEvent '{self.headline[:50]}...' impact={self.impact_level}>"


class EconomicEvent(TimestampMixin, Base):
    """
    Scheduled economic calendar event.

    Examples: CPI release, FOMC decision, NFP report, GDP.
    Used by the Event Driven strategy to trade around scheduled events.
    """

    __tablename__ = "economic_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    event_name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str] = mapped_column(String(10), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # Expected values
    previous_value: Mapped[str | None] = mapped_column(String(50), nullable=True)
    forecast_value: Mapped[str | None] = mapped_column(String(50), nullable=True)
    actual_value: Mapped[str | None] = mapped_column(String(50), nullable=True)

    impact_level: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")

    # Assets this event is expected to affect
    affected_assets: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Post-event analysis
    market_reaction: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_econ_scheduled", "scheduled_at"),
        Index("ix_econ_country", "country"),
    )

    def __repr__(self) -> str:
        return f"<EconomicEvent '{self.event_name}' {self.scheduled_at}>"
