import os
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

import pandas as pd
import finnhub
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.core.logging import get_logger
from src.data.base import AssetClass, MarketDataProvider, ProviderCapabilities, Quote

logger = get_logger("data.finnhub")

class FinnhubProvider(MarketDataProvider):
    """
    Market Data Provider using Finnhub.
    Supports real-time quotes and historical data.
    Configured for the Free Tier limits.
    """

    def __init__(self) -> None:
        api_key = settings.finnhub_api_key.get_secret_value()
        if not api_key:
            raise ValueError("FINNHUB_API_KEY environment variable is not set")
        
        self.client = finnhub.Client(api_key=api_key)
        self._capabilities = ProviderCapabilities(
            asset_classes=[AssetClass.US_EQUITY],
            supports_realtime=True,
            supports_historical=True,
            supports_news=True,
            max_history_days=365,  # Free tier limit
            rate_limit_per_minute=60, # Finnhub free tier limit is 60 calls/min
        )
        logger.info("finnhub_provider_initialized", mode="free_tier")

    @property
    def name(self) -> str:
        return "finnhub"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_quote(self, symbol: str) -> Quote:
        """Fetch real-time quote for a symbol."""
        # Convert crypto symbols if necessary (Finnhub expects BINANCE:BTCUSDT for crypto, but we'll stick to US Equity)
        # Note: Finnhub API is synchronous, so we run it in a thread executor
        loop = asyncio.get_running_loop()
        try:
            res = await loop.run_in_executor(None, self.client.quote, symbol)
            
            if not res or res.get("c", 0) == 0:
                raise ValueError(f"Invalid quote received for {symbol}")

            return Quote(
                symbol=symbol,
                bid=res.get("c"), # Finnhub quote doesn't give bid/ask on free tier usually, fallback to close
                ask=res.get("c"),
                last=res.get("c"),
                volume=0.0, # Not provided in basic quote
                timestamp=datetime.fromtimestamp(res.get("t", datetime.now().timestamp()), tz=timezone.utc),
                change=res.get("d", 0.0),
                change_pct=res.get("dp", 0.0),
                high=res.get("h", 0.0),
                low=res.get("l", 0.0),
                open=res.get("o", 0.0),
                prev_close=res.get("pc", 0.0),
                source="finnhub",
            )
        except Exception as e:
            logger.error("finnhub_quote_error", symbol=symbol, error=str(e))
            raise

    async def get_multiple_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Fetch quotes for multiple symbols concurrently."""
        quotes = {}
        # Finnhub free tier limit is 60 API calls per minute (1 per second on average)
        # We will just gather them, Tenacity retry will handle 429s if we burst a little
        tasks = [self.get_quote(sym) for sym in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for sym, res in zip(symbols, results):
            if isinstance(res, Exception):
                logger.warning("finnhub_batch_quote_failed", symbol=sym, error=str(res))
            else:
                quotes[sym] = res
                
        return quotes

    def _map_timeframe(self, timeframe: str) -> str:
        """Map standard timeframe to Finnhub resolution."""
        mapping = {
            "1m": "1",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "1h": "60",
            "1d": "D",
            "1w": "W",
            "1M": "M"
        }
        if timeframe not in mapping:
            logger.warning("unsupported_timeframe_fallback_to_day", timeframe=timeframe)
            return "D"
        return mapping[timeframe]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str = "1d",
        start: datetime | None = None,
        end: datetime | None = None,
        days: int | None = None,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data."""
        resolution = self._map_timeframe(timeframe)

        # Free tier limitation logic
        if resolution != "D" and resolution != "W" and resolution != "M":
            logger.warning("finnhub_free_tier_intraday_warning", symbol=symbol, timeframe=timeframe)
            # Intraday is limited to 30 days on free tier, but we'll let the API reject it if it's too far back

        if not end:
            end = datetime.now(timezone.utc)
            
        if not start:
            if days:
                # Free tier cap
                if resolution == "D" and days > 365:
                    logger.warning("capping_history_to_1_year_for_free_tier", symbol=symbol, requested_days=days)
                    days = 365
                start = end - timedelta(days=days)
            else:
                start = end - timedelta(days=30) # Default to 30 days

        start_ts = int(start.timestamp())
        end_ts = int(end.timestamp())

        loop = asyncio.get_running_loop()
        try:
            res = await loop.run_in_executor(
                None, 
                self.client.stock_candles, 
                symbol, 
                resolution, 
                start_ts, 
                end_ts
            )

            if not res or res.get("s") != "ok":
                logger.warning("finnhub_no_data", symbol=symbol, status=res.get("s") if res else "None")
                return pd.DataFrame()

            df = pd.DataFrame({
                "timestamp": pd.to_datetime(res["t"], unit="s", utc=True),
                "open": res["o"],
                "high": res["h"],
                "low": res["l"],
                "close": res["c"],
                "volume": res["v"]
            })
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)
            
            logger.info("historical_data_fetched", symbol=symbol, timeframe=timeframe, rows=len(df), source="finnhub")
            return df
            
        except Exception as e:
            logger.error("finnhub_history_error", symbol=symbol, error=str(e))
            raise
