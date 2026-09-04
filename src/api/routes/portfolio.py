"""
Portfolio API Routes
====================

REST endpoints for portfolio state, positions, and P&L.

All routes use the shared broker instance from the paper trading engine
via the dependencies module, ensuring the dashboard reflects actual state.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from src.api.dependencies import get_broker
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger("trading")
router = APIRouter()


@router.get("/account")
async def get_account() -> dict[str, Any]:
    """Get account information."""
    account = await get_broker().get_account()
    return account.to_dict()


@router.get("/positions")
async def get_positions() -> list[dict[str, Any]]:
    """Get all current open positions."""
    positions = await get_broker().get_positions()
    return [p.to_dict() for p in positions]


@router.get("/positions/{symbol}")
async def get_position(symbol: str) -> dict[str, Any]:
    """Get position for a specific symbol."""
    pos = await get_broker().get_position(symbol)
    if pos is None:
        return {"symbol": symbol, "message": "No position found"}
    return pos.to_dict()


@router.get("/pnl")
async def get_pnl() -> dict[str, Any]:
    """Get current P&L summary."""
    broker = get_broker()
    account = await broker.get_account()
    positions = await broker.get_positions()

    unrealized_pnl = sum(p.unrealized_pnl for p in positions)
    initial = settings.paper_trading_initial_capital

    return {
        "portfolio_value": round(account.portfolio_value, 2),
        "initial_capital": round(initial, 2),
        "total_pnl": round(account.portfolio_value - initial, 2),
        "total_pnl_pct": round(((account.portfolio_value - initial) / initial) * 100, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "cash": round(account.cash, 2),
    }


@router.get("/exposure")
async def get_exposure() -> dict[str, Any]:
    """Get portfolio exposure breakdown."""
    broker = get_broker()
    account = await broker.get_account()
    positions = await broker.get_positions()

    long_exp = sum(p.market_value for p in positions if p.side == "long")
    short_exp = sum(p.market_value for p in positions if p.side == "short")

    return {
        "total_value": round(account.portfolio_value, 2),
        "long_exposure": round(long_exp, 2),
        "short_exposure": round(short_exp, 2),
        "net_exposure": round(long_exp - short_exp, 2),
        "num_positions": len(positions),
    }
