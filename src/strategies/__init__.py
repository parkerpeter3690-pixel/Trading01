"""
Strategy Engine Package
========================

Eight independent trading strategies, each with:
- Standardized signal output
- Version tracking
- Supported regime declaration
- Configurable parameters

Strategies:
1. Trend Following  — MAs, ADX, market structure
2. Mean Reversion   — Bollinger, Z-score, RSI
3. Momentum         — ROC, relative strength
4. Breakout         — Consolidation detection, volume expansion
5. Volatility       — ATR, vol regime
6. Event Driven     — Economic calendar, news
7. Statistical      — Correlation, cointegration
8. Regime           — Market state classification
"""

from __future__ import annotations

from src.strategies.base import BaseStrategy


def get_all_strategies() -> list[BaseStrategy]:
    """
    Instantiate and return all 8 trading strategies.

    This is the canonical way to get the full strategy suite.
    Used by PaperTradingEngine, BacktestEngine, and the API.
    """
    from src.strategies.breakout import BreakoutStrategy
    from src.strategies.event_driven import EventDrivenStrategy
    from src.strategies.mean_reversion import MeanReversionStrategy
    from src.strategies.momentum import MomentumStrategy
    from src.strategies.regime import RegimeStrategy
    from src.strategies.statistical import StatisticalStrategy
    from src.strategies.trend_following import TrendFollowingStrategy
    from src.strategies.volatility import VolatilityStrategy

    return [
        TrendFollowingStrategy(),
        MeanReversionStrategy(),
        MomentumStrategy(),
        BreakoutStrategy(),
        VolatilityStrategy(),
        EventDrivenStrategy(),
        StatisticalStrategy(),
        RegimeStrategy(),
    ]
