"""
Abstract Data Provider Base
============================

Defines the interface that all market data providers must implement.

Design:
- All providers return standardized pandas DataFrames.
- Providers handle their own rate limiting and error recovery.
- Caching is handled at the provider layer via Redis.
- Each provider declares which asset classes and features it supports.

Usage:
    provider = YFinanceProvider()
    df = await provider.get_historical_data("AAPL", "1d", days=365)
    quote = await provider.get_quote("AAPL")
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import pandas as pd


class AssetClass(str, Enum):
    """Supported asset classes."""
    US_EQUITY = "us_equity"
    CRYPTO = "crypto"
    FOREX = "forex"
    COMMODITY = "commodity"
    INDEX = "index"
    ETF = "etf"


@dataclass
class Quote:
    """Real-time price quote."""
    symbol: str
    bid: float | None
    ask: float | None
    last: float
    volume: float
    timestamp: datetime
    change: float = 0.0
    change_pct: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    prev_close: float = 0.0
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat(),
            "change": self.change,
            "change_pct": self.change_pct,
            "high": self.high,
            "low": self.low,
            "open": self.open,
            "prev_close": self.prev_close,
            "source": self.source,
        }


@dataclass
class ProviderCapabilities:
    """Declares what a data provider supports."""
    asset_classes: list[AssetClass] = field(default_factory=list)
    supports_realtime: bool = False
    supports_historical: bool = True
    supports_indicators: bool = False
    supports_orderbook: bool = False
    supports_news: bool = False
    max_history_days: int = 365 * 5
    rate_limit_per_minute: int = 5


class MarketDataProvider(ABC):
    """
    Abstract base class for market data providers.

    All providers must implement:
    - get_quote(): Current price
    - get_historical_data(): OHLCV history
    - get_multiple_quotes(): Batch quotes

    Optional methods:
    - get_orderbook(): Level 2 data
    - get_indicators(): Pre-computed indicators
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """What this provider supports."""
        ...

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote:
        """
        Get the current price quote for a symbol.

        Args:
            symbol: Ticker symbol (e.g., "AAPL", "BTC-USD")

        Returns:
            Quote with current bid/ask/last price
        """
        ...

    @abstractmethod
    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str = "1d",
        start: datetime | None = None,
        end: datetime | None = None,
        days: int | None = None,
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data.

        Returns a DataFrame with columns:
        - timestamp (index)
        - open, high, low, close, volume

        Args:
            symbol: Ticker symbol
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d, 1w)
            start: Start datetime (inclusive)
            end: End datetime (inclusive)
            days: Alternative to start/end — fetch last N days
        """
        ...

    @abstractmethod
    async def get_multiple_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """
        Get quotes for multiple symbols.

        Returns:
            Dict mapping symbol → Quote
        """
        ...

    async def get_orderbook(self, symbol: str, depth: int = 10) -> dict[str, Any]:
        """Get Level 2 order book data. Override if supported."""
        raise NotImplementedError(f"{self.name} does not support order book data")

    async def get_indicators(
        self, symbol: str, indicators: list[str], timeframe: str = "1d"
    ) -> dict[str, Any]:
        """Get pre-computed technical indicators. Override if supported."""
        raise NotImplementedError(f"{self.name} does not support indicators")

    async def search_symbols(self, query: str) -> list[dict[str, str]]:
        """Search for symbols matching a query. Override if supported."""
        raise NotImplementedError(f"{self.name} does not support symbol search")

    async def health_check(self) -> bool:
        """Check if the provider is available."""
        try:
            await self.get_quote("AAPL")
            return True
        except Exception:
            return False
