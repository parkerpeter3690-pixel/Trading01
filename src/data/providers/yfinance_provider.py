"""
yFinance Market Data Provider
==============================

Free data provider for development and testing.
Uses the yfinance library to fetch data from Yahoo Finance.

Limitations:
- Unofficial API (may break without warning)
- Rate limited (risk of IP bans with heavy use)
- No real-time streaming (polling only)
- NOT suitable for production automated trading

Best for:
- Local development
- Backtesting with historical data
- Strategy prototyping

Usage:
    provider = YFinanceProvider()
    quote = await provider.get_quote("AAPL")
    df = await provider.get_historical_data("AAPL", "1d", days=365)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import yfinance as yf

from src.core.exceptions import DataProviderError, InsufficientDataError
from src.core.logging import get_logger
from src.data.base import (
    AssetClass,
    MarketDataProvider,
    ProviderCapabilities,
    Quote,
)

logger = get_logger("market")


class YFinanceProvider(MarketDataProvider):
    """
    Market data provider using Yahoo Finance (via yfinance).

    Runs blocking yfinance calls in a thread pool to avoid
    blocking the async event loop.
    """

    @property
    def name(self) -> str:
        return "yfinance"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            asset_classes=[
                AssetClass.US_EQUITY,
                AssetClass.CRYPTO,
                AssetClass.FOREX,
                AssetClass.COMMODITY,
                AssetClass.INDEX,
                AssetClass.ETF,
            ],
            supports_realtime=False,   # Polling only, not true real-time
            supports_historical=True,
            supports_indicators=False,
            supports_orderbook=False,
            max_history_days=365 * 10,
            rate_limit_per_minute=30,  # Conservative to avoid bans
        )

    # ── Timeframe Mapping ────────────────────────────────────────────
    _TF_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "1h": "1h",
        "4h": "1h",   # yfinance doesn't support 4h natively; resample
        "1d": "1d",
        "1w": "1wk",
    }

    async def get_quote(self, symbol: str) -> Quote:
        """
        Get the latest price quote for a symbol.

        Runs in thread pool since yfinance is synchronous.
        """
        try:
            ticker = await asyncio.to_thread(self._fetch_ticker_info, symbol)

            return Quote(
                symbol=symbol,
                bid=ticker.get("bid"),
                ask=ticker.get("ask"),
                last=ticker.get("regularMarketPrice", ticker.get("currentPrice", 0.0)),
                volume=ticker.get("regularMarketVolume", ticker.get("volume", 0)),
                timestamp=datetime.now(timezone.utc),
                change=ticker.get("regularMarketChange", 0.0),
                change_pct=ticker.get("regularMarketChangePercent", 0.0),
                high=ticker.get("regularMarketDayHigh", ticker.get("dayHigh", 0.0)),
                low=ticker.get("regularMarketDayLow", ticker.get("dayLow", 0.0)),
                open=ticker.get("regularMarketOpen", ticker.get("open", 0.0)),
                prev_close=ticker.get("regularMarketPreviousClose", ticker.get("previousClose", 0.0)),
                source="yfinance",
            )
        except Exception as e:
            logger.error("yfinance_quote_error", symbol=symbol, error=str(e))
            raise DataProviderError(
                f"Failed to fetch quote for {symbol} from yfinance",
                symbol=symbol,
                provider="yfinance",
            ) from e

    def _fetch_ticker_info(self, symbol: str) -> dict[str, Any]:
        """Synchronous yfinance call — runs in thread pool."""
        ticker = yf.Ticker(symbol)
        return ticker.info or {}

    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str = "1d",
        start: datetime | None = None,
        end: datetime | None = None,
        days: int | None = None,
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data from Yahoo Finance.

        Returns a DataFrame with standardized column names:
        [open, high, low, close, volume]
        """
        try:
            # Calculate date range
            if days is not None:
                end = end or datetime.now(timezone.utc)
                start = end - timedelta(days=days)

            if start is None:
                start = datetime.now(timezone.utc) - timedelta(days=365)
            if end is None:
                end = datetime.now(timezone.utc)

            yf_interval = self._TF_MAP.get(timeframe, "1d")

            # Run blocking call in thread pool
            df = await asyncio.to_thread(
                self._fetch_history, symbol, yf_interval, start, end
            )

            if df.empty:
                raise InsufficientDataError(
                    f"No data returned for {symbol}",
                    symbol=symbol,
                    timeframe=timeframe,
                )

            # Standardize column names
            df.columns = [c.lower() for c in df.columns]

            # Ensure we have required columns
            required = {"open", "high", "low", "close", "volume"}
            missing = required - set(df.columns)
            if missing:
                raise DataProviderError(
                    f"Missing columns: {missing}",
                    symbol=symbol,
                    provider="yfinance",
                )

            # Select only OHLCV columns (drop adj close, etc.)
            df = df[["open", "high", "low", "close", "volume"]].copy()

            # Resample 1h to 4h if needed
            if timeframe == "4h":
                df = self._resample_to_4h(df)

            # Drop any rows with NaN
            df = df.dropna()

            logger.info(
                "historical_data_fetched",
                symbol=symbol,
                timeframe=timeframe,
                rows=len(df),
                start=str(df.index[0]),
                end=str(df.index[-1]),
            )

            return df

        except (InsufficientDataError, DataProviderError):
            raise
        except Exception as e:
            logger.error("yfinance_history_error", symbol=symbol, error=str(e))
            raise DataProviderError(
                f"Failed to fetch historical data for {symbol}",
                symbol=symbol,
                provider="yfinance",
            ) from e

    def _fetch_history(
        self,
        symbol: str,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Synchronous yfinance history call — runs in thread pool."""
        ticker = yf.Ticker(symbol)
        return ticker.history(
            interval=interval,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True,
        )

    def _resample_to_4h(self, df: pd.DataFrame) -> pd.DataFrame:
        """Resample 1h data to 4h candles."""
        return df.resample("4h").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()

    async def get_multiple_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Get quotes for multiple symbols concurrently."""
        tasks = [self.get_quote(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        quotes: dict[str, Quote] = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Quote):
                quotes[symbol] = result
            else:
                logger.warning("quote_failed", symbol=symbol, error=str(result))

        return quotes

    async def search_symbols(self, query: str) -> list[dict[str, str]]:
        """Search for symbols matching a query."""
        try:
            results = await asyncio.to_thread(self._search, query)
            return results
        except Exception as e:
            logger.warning("symbol_search_failed", query=query, error=str(e))
            return []

    def _search(self, query: str) -> list[dict[str, str]]:
        """Synchronous symbol search."""
        # yfinance doesn't have a native search; use a basic approach
        ticker = yf.Ticker(query)
        info = ticker.info or {}
        if info.get("symbol"):
            return [{
                "symbol": info["symbol"],
                "name": info.get("longName", info.get("shortName", "")),
                "type": info.get("quoteType", ""),
                "exchange": info.get("exchange", ""),
            }]
        return []
