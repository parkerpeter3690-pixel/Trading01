"""
Abstract Broker Interface
=========================

Defines the interface that all broker adapters must implement.

Design:
- Every order goes through the risk engine BEFORE reaching the broker.
- The broker adapter handles only execution — never makes trading decisions.
- All broker calls are async for non-blocking execution.
- Broker errors are wrapped in typed exceptions.

Order flow:
    Signal → Risk Engine → Order Validated → Broker Adapter → Execution → Confirmation

Usage:
    broker = PaperBroker(initial_capital=100_000)
    order = await broker.place_order(OrderRequest(...))
    positions = await broker.get_positions()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"       # Good 'til cancelled
    IOC = "ioc"       # Immediate or cancel
    FOK = "fok"       # Fill or kill


@dataclass
class OrderRequest:
    """Request to place an order."""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    limit_price: float | None = None
    stop_price: float | None = None
    trail_percent: float | None = None
    time_in_force: TimeInForce = TimeInForce.DAY
    client_order_id: str | None = None
    # Risk metadata (set by risk engine)
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass
class OrderResult:
    """Result of an order placement or query."""
    client_order_id: str
    broker_order_id: str | None = None
    symbol: str = ""
    side: str = ""
    order_type: str = ""
    quantity: float = 0.0
    filled_quantity: float = 0.0
    avg_fill_price: float | None = None
    limit_price: float | None = None
    stop_price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    commission: float = 0.0
    submitted_at: datetime | None = None
    filled_at: datetime | None = None
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_order_id": self.client_order_id,
            "broker_order_id": self.broker_order_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "avg_fill_price": self.avg_fill_price,
            "status": self.status.value,
            "commission": self.commission,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
        }


@dataclass
class BrokerPosition:
    """A position held at the broker."""
    symbol: str
    side: str          # "long" or "short"
    quantity: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "avg_entry_price": self.avg_entry_price,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
        }


@dataclass
class AccountInfo:
    """Broker account information."""
    account_id: str
    cash: float
    portfolio_value: float
    buying_power: float
    equity: float
    margin_used: float = 0.0
    day_trade_count: int = 0
    environment: str = "paper"

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "cash": self.cash,
            "portfolio_value": self.portfolio_value,
            "buying_power": self.buying_power,
            "equity": self.equity,
            "margin_used": self.margin_used,
            "environment": self.environment,
        }


class BrokerAdapter(ABC):
    """
    Abstract base class for broker adapters.

    Implementations handle the actual execution of orders
    against a paper or live trading environment.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Broker name."""
        ...

    @property
    @abstractmethod
    def environment(self) -> str:
        """'paper' or 'live'."""
        ...

    @abstractmethod
    async def get_account(self) -> AccountInfo:
        """Get account information."""
        ...

    @abstractmethod
    async def place_order(self, request: OrderRequest) -> OrderResult:
        """Place an order. Returns the execution result."""
        ...

    @abstractmethod
    async def cancel_order(self, client_order_id: str) -> OrderResult:
        """Cancel a pending order."""
        ...

    @abstractmethod
    async def modify_order(
        self, client_order_id: str, **updates: Any
    ) -> OrderResult:
        """Modify a pending order (limit price, quantity, etc.)."""
        ...

    @abstractmethod
    async def get_order(self, client_order_id: str) -> OrderResult:
        """Get the current status of an order."""
        ...

    @abstractmethod
    async def get_open_orders(self) -> list[OrderResult]:
        """Get all currently open/pending orders."""
        ...

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]:
        """Get all current positions."""
        ...

    @abstractmethod
    async def get_position(self, symbol: str) -> BrokerPosition | None:
        """Get position for a specific symbol."""
        ...

    async def health_check(self) -> bool:
        """Check if the broker connection is healthy."""
        try:
            await self.get_account()
            return True
        except Exception:
            return False
