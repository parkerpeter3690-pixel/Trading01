"""
Abstract Strategy Base Class
=============================

Defines the interface for all trading strategies.

Design:
- Every strategy produces standardized StrategySignal outputs.
- Strategies declare which market regimes they support.
- Strategies have immutable versioned parameter snapshots.
- Strategies do NOT make trading decisions — they generate signals.
  The Signal Fusion Engine and Orchestrator combine and act on signals.

Usage:
    class MyStrategy(BaseStrategy):
        @property
        def name(self) -> str: return "my_strategy"

        async def generate_signals(self, data, context) -> list[StrategySignal]:
            # Compute signals from data
            ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import pandas as pd


class MarketRegime(str, Enum):
    """Market regime classifications (Section 5)."""
    TRENDING = "trending"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    EVENT_DRIVEN = "event_driven"
    UNKNOWN = "unknown"


class SignalDirection(str, Enum):
    """Signal direction."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    NO_TRADE = "no_trade"


@dataclass
class StrategySignal:
    """
    A signal produced by a strategy.

    Each signal includes:
    - Direction and strength
    - Confidence score
    - Risk parameters (stop loss, target, R:R)
    - Market context
    - Full reasoning for auditability
    """
    # Identity
    strategy_name: str
    strategy_version: str
    symbol: str
    timeframe: str
    generated_at: datetime

    # Signal
    direction: SignalDirection
    strength: float              # -1.0 (strong sell) to +1.0 (strong buy)
    confidence: float            # 0.0 to 1.0

    # Trade parameters
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward_ratio: float | None = None

    # Expected outcomes
    expected_return_pct: float | None = None
    expected_volatility: float | None = None
    time_horizon: str | None = None

    # Context
    market_regime: MarketRegime | None = None
    reasoning: dict[str, Any] = field(default_factory=dict)
    indicators_used: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "generated_at": self.generated_at.isoformat(),
            "direction": self.direction.value,
            "strength": self.strength,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward_ratio": self.risk_reward_ratio,
            "expected_return_pct": self.expected_return_pct,
            "time_horizon": self.time_horizon,
            "market_regime": self.market_regime.value if self.market_regime else None,
            "reasoning": self.reasoning,
            "indicators_used": self.indicators_used,
        }


@dataclass
class MarketContext:
    """Market context passed to strategies for signal generation."""
    symbol: str
    timeframe: str
    data: pd.DataFrame              # OHLCV data
    current_price: float
    volume_avg: float | None = None
    market_regime: MarketRegime | None = None
    news_events: list[dict] = field(default_factory=list)
    economic_events: list[dict] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    Subclasses must implement:
    - name: Strategy name
    - version: Current version
    - supported_regimes: Which market regimes this strategy works in
    - generate_signals: Core signal generation logic
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name (e.g., 'trend_following')."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Current version (e.g., 'v1.0')."""
        ...

    @property
    @abstractmethod
    def strategy_type(self) -> str:
        """Strategy type (e.g., 'trend', 'mean_reversion')."""
        ...

    @property
    @abstractmethod
    def supported_regimes(self) -> list[MarketRegime]:
        """Market regimes where this strategy is expected to perform."""
        ...

    @property
    def supported_timeframes(self) -> list[str]:
        """Timeframes this strategy supports. Override if limited."""
        return ["1h", "4h", "1d"]

    @property
    def parameters(self) -> dict[str, Any]:
        """Current strategy parameters. Override to expose parameters."""
        return {}

    @abstractmethod
    async def generate_signals(
        self, context: MarketContext
    ) -> list[StrategySignal]:
        """
        Generate trading signals from market data.

        This is the core strategy logic. It should:
        1. Compute indicators from the provided data
        2. Evaluate conditions
        3. Return signals with direction, strength, and confidence

        Args:
            context: Market data and context

        Returns:
            List of signals (usually 0 or 1 per call)
        """
        ...

    def validate_data(self, data: pd.DataFrame, min_rows: int = 50) -> bool:
        """Check if enough data is available for the strategy."""
        if data is None or data.empty or len(data) < min_rows:
            return False
        required = {"open", "high", "low", "close", "volume"}
        return required.issubset(set(data.columns))

    def __repr__(self) -> str:
        return f"<Strategy '{self.name}' {self.version}>"
