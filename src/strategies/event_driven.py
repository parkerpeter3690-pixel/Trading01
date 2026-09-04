"""
Event Driven Strategy
======================

Trades around scheduled economic events (CPI, FOMC, NFP, GDP, earnings).
Uses pre/post-event volatility patterns and historical event outcomes.

Supported Regimes: EVENT_DRIVEN
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from src.strategies.base import BaseStrategy, MarketContext, MarketRegime, SignalDirection, StrategySignal


class EventDrivenStrategy(BaseStrategy):
    @property
    def name(self) -> str: return "event_driven"
    @property
    def version(self) -> str: return "v1.0"
    @property
    def strategy_type(self) -> str: return "event_driven"
    @property
    def supported_regimes(self) -> list[MarketRegime]:
        return [MarketRegime.EVENT_DRIVEN]

    async def generate_signals(self, context: MarketContext) -> list[StrategySignal]:
        """
        Event driven signals require news/economic event context.
        If no events are in context, no signals are generated.

        In production, the News Agent populates context.economic_events
        and context.news_events before calling this strategy.
        """
        if not context.economic_events and not context.news_events:
            return []

        # Placeholder: in production, this analyzes event impact
        # using historical event reactions and current market positioning
        reasoning = {
            "events": context.economic_events[:3] if context.economic_events else [],
            "news": [n.get("headline", "") for n in context.news_events[:3]],
            "note": "Event analysis requires LLM interpretation — delegated to News Agent",
        }

        return [StrategySignal(
            strategy_name=self.name, strategy_version=self.version,
            symbol=context.symbol, timeframe=context.timeframe,
            generated_at=datetime.now(timezone.utc),
            direction=SignalDirection.HOLD,
            strength=0.0, confidence=0.4,
            market_regime=MarketRegime.EVENT_DRIVEN,
            reasoning=reasoning,
        )]
