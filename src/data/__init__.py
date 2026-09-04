"""
Data Providers Package
======================

Market data and news providers using the adapter pattern.

All providers implement abstract base classes, making them swappable:
- MarketDataProvider: OHLCV, quotes, indicators
- NewsProvider: Financial news with metadata

Available providers:
- yfinance (development, free, no API key)
- Alpha Vantage (production, free tier available)
- Finnhub (news + market data, free tier)
- Polygon.io (premium, high-quality)
"""
