"""
Strategies API Routes
=====================

REST endpoints for strategy management, versions, and performance.

Uses the shared engine from the dependencies module to reflect
actual strategy state instead of returning hardcoded data.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from src.api.dependencies import get_engine
from src.core.logging import get_logger

logger = get_logger("strategy")
router = APIRouter()


@router.get("/")
async def list_strategies() -> dict[str, Any]:
    """List all registered strategies with their active versions and status."""
    engine = get_engine()
    strategies = engine._strategies

    return {
        "strategies": [
            {
                "name": s.name,
                "type": s.strategy_type,
                "active_version": s.version,
                "supported_regimes": [r.value for r in s.supported_regimes],
                "enabled": True,
            }
            for s in strategies
        ]
    }


@router.get("/{strategy_name}")
async def get_strategy(strategy_name: str) -> dict[str, Any]:
    """Get detailed information about a specific strategy."""
    engine = get_engine()

    for s in engine._strategies:
        if s.name == strategy_name:
            return {
                "name": s.name,
                "type": s.strategy_type,
                "version": s.version,
                "supported_regimes": [r.value for r in s.supported_regimes],
                "enabled": True,
            }

    return {"error": f"Strategy '{strategy_name}' not found"}


@router.get("/{strategy_name}/performance")
async def get_strategy_performance(strategy_name: str) -> dict[str, Any]:
    """Get performance metrics for a strategy."""
    # TODO: Wire up to database when trade persistence is added
    return {
        "strategy": strategy_name,
        "message": "Performance data will be populated after backtesting and trading",
    }
