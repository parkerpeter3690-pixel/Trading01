"""
Market Data Models
==================

Stores OHLCV market data snapshots and derived indicators.

Design:
- Composite index on (symbol, timeframe, timestamp) for fast lookups.
- Supports multiple timeframes (1m, 5m, 15m, 1h, 4h, 1d).
- Stores raw data separately from computed indicators.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, TimestampMixin


class Timeframe(str, Enum):
    """Supported chart timeframes."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class MarketData(TimestampMixin, Base):
    """
    OHLCV market data with computed indicators.

    Each row represents one candle for a specific symbol and timeframe.
    Indicators are stored as JSONB for flexibility — different strategies
    may compute different indicator sets.
    """

    __tablename__ = "market_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)

    # OHLCV
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Additional market data (may be null for some data sources)
    vwap: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Computed indicators stored as JSONB for flexibility
    # Example: {"sma_20": 150.5, "rsi_14": 65.3, "atr_14": 2.1, ...}
    indicators: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Data source tracking
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="yfinance")

    __table_args__ = (
        # Primary lookup: what is the price of AAPL on the 1h chart at time T?
        Index("ix_market_data_symbol_tf_ts", "symbol", "timeframe", "timestamp", unique=True),
        # Time-range queries: all data for AAPL in the last 24 hours
        Index("ix_market_data_symbol_ts", "symbol", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<MarketData {self.symbol} {self.timeframe} {self.timestamp} C={self.close}>"
