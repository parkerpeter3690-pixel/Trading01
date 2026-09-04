"""
Trading API Routes
==================

REST endpoints for order management and trade history.

All routes use the shared broker instance from the paper trading engine
via the dependencies module.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.brokers.base import OrderSide, OrderType
from src.brokers.paper_broker import OrderRequest
from src.api.dependencies import get_broker
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger("trading")
router = APIRouter()


class PlaceOrderRequest(BaseModel):
    """Request body for placing an order."""
    symbol: str = Field(..., description="Ticker symbol")
    side: str = Field(..., description="buy or sell")
    quantity: float = Field(..., gt=0, description="Order quantity")
    order_type: str = Field("market", description="market, limit, stop")
    limit_price: float | None = Field(None, description="Limit price for limit orders")
    stop_loss: float | None = Field(None, description="Stop loss price")
    take_profit: float | None = Field(None, description="Take profit price")


@router.post("/orders")
async def place_order(request: PlaceOrderRequest) -> dict[str, Any]:
    """
    Place a paper trading order.

    Order must pass risk validation before execution.
    """
    logger.info(
        "api_place_order",
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
    )

    # Enforce stop loss
    if settings.require_stop_loss and request.stop_loss is None:
        return {
            "status": "rejected",
            "reason": "Stop loss is required for all trades",
        }

    order_req = OrderRequest(
        symbol=request.symbol,
        side=OrderSide(request.side),
        order_type=OrderType(request.order_type),
        quantity=request.quantity,
        limit_price=request.limit_price,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
    )

    result = await get_broker().place_order(order_req)
    return result.to_dict()


@router.get("/orders")
async def get_open_orders() -> list[dict[str, Any]]:
    """Get all open/pending orders."""
    orders = await get_broker().get_open_orders()
    return [o.to_dict() for o in orders]


@router.delete("/orders/{client_order_id}")
async def cancel_order(client_order_id: str) -> dict[str, Any]:
    """Cancel a pending order."""
    result = await get_broker().cancel_order(client_order_id)
    return result.to_dict()


@router.get("/orders/{client_order_id}")
async def get_order_status(client_order_id: str) -> dict[str, Any]:
    """Get the status of a specific order."""
    result = await get_broker().get_order(client_order_id)
    return result.to_dict()
