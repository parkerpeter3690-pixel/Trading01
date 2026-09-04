"""
Market Data API Routes
======================

REST endpoints for market data, quotes, and indicators.

Uses the shared data provider from the paper trading engine
via the dependencies module.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from src.api.dependencies import get_data_provider
from src.core.logging import get_logger

logger = get_logger("market")
router = APIRouter()


@router.get("/quote/{symbol}")
async def get_quote(symbol: str) -> dict[str, Any]:
    """Get current price quote for a symbol."""
    quote = await get_data_provider().get_quote(symbol)
    return quote.to_dict()


@router.get("/quotes")
async def get_quotes(
    symbols: str = Query(..., description="Comma-separated symbols"),
) -> dict[str, Any]:
    """Get quotes for multiple symbols."""
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    quotes = await get_data_provider().get_multiple_quotes(symbol_list)
    return {s: q.to_dict() for s, q in quotes.items()}


@router.get("/history/{symbol}")
async def get_history(
    symbol: str,
    timeframe: str = Query("1d", description="Candle timeframe"),
    days: int = Query(30, description="Days of history"),
) -> dict[str, Any]:
    """Get historical OHLCV data."""
    import json
    df = await get_data_provider().get_historical_data(symbol, timeframe, days=days)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "rows": len(df),
        "data": json.loads(df.to_json(orient="index", date_format="iso")),
    }


@router.get("/search")
async def search_symbols(q: str = Query(..., description="Search query")) -> list[dict[str, str]]:
    """Search for symbols matching a query."""
    return await get_data_provider().search_symbols(q)
