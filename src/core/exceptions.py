"""
Custom Exception Hierarchy
==========================

Typed exceptions for every subsystem in the trading platform.

Design:
- Every exception carries structured context for logging and debugging.
- Risk exceptions are always logged at CRITICAL level.
- Execution exceptions trigger automatic order cancellation.
- All exceptions are caught at the API boundary and converted to HTTP responses.

Usage:
    raise RiskLimitExceeded(
        limit_name="max_daily_loss",
        current_value=2.5,
        limit_value=2.0,
        details="Daily loss of 2.5% exceeds 2.0% limit",
    )
"""

from __future__ import annotations

from typing import Any


# ── Base Exception ───────────────────────────────────────────────────────

class TradingSystemError(Exception):
    """
    Base exception for all trading system errors.
    All exceptions carry structured context for logging.
    """

    def __init__(self, message: str, **context: Any) -> None:
        self.message = message
        self.context = context
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception for logging and API responses."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            **self.context,
        }


# ── Data Exceptions ─────────────────────────────────────────────────────

class DataProviderError(TradingSystemError):
    """Error fetching data from a market data or news provider."""
    pass


class DataValidationError(TradingSystemError):
    """Data failed validation checks (e.g., missing OHLCV fields, future timestamps)."""
    pass


class InsufficientDataError(TradingSystemError):
    """Not enough historical data to compute indicators or run strategies."""
    pass


# ── Risk Exceptions ─────────────────────────────────────────────────────

class RiskLimitExceeded(TradingSystemError):
    """
    A risk limit has been breached. Trade MUST be rejected.

    These are HARD limits from config that the AI cannot override.
    """

    def __init__(
        self,
        limit_name: str,
        current_value: float,
        limit_value: float,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            f"Risk limit '{limit_name}' exceeded: {current_value} > {limit_value}",
            limit_name=limit_name,
            current_value=current_value,
            limit_value=limit_value,
            **kwargs,
        )


class KillSwitchActivated(TradingSystemError):
    """
    Kill switch has been triggered. ALL trading must stop immediately.

    Triggers: daily loss exceeded, drawdown exceeded, broker disconnect,
    data corruption, abnormal volatility, execution anomaly.
    """
    pass


class StopLossRequired(TradingSystemError):
    """Trade rejected because it does not have a stop loss."""
    pass


class InsufficientMargin(TradingSystemError):
    """Insufficient margin/capital for the proposed position."""
    pass


# ── Order/Execution Exceptions ──────────────────────────────────────────

class OrderValidationError(TradingSystemError):
    """Order failed pre-execution validation."""
    pass


class OrderExecutionError(TradingSystemError):
    """Order execution failed at the broker level."""
    pass


class OrderNotFound(TradingSystemError):
    """Referenced order does not exist."""
    pass


class BrokerConnectionError(TradingSystemError):
    """Cannot connect to the broker API."""
    pass


class BrokerRateLimitError(TradingSystemError):
    """Broker API rate limit exceeded."""
    pass


# ── Strategy Exceptions ─────────────────────────────────────────────────

class StrategyError(TradingSystemError):
    """Error in strategy computation or signal generation."""
    pass


class StrategyNotFound(TradingSystemError):
    """Referenced strategy does not exist."""
    pass


class StrategyVersionConflict(TradingSystemError):
    """Attempting to modify a strategy version that is currently in use."""
    pass


# ── Agent Exceptions ────────────────────────────────────────────────────

class AgentError(TradingSystemError):
    """Error in AI agent processing."""
    pass


class LLMProviderError(TradingSystemError):
    """Error communicating with the LLM provider."""
    pass


class AgentDecisionTimeout(TradingSystemError):
    """Agent took too long to produce a decision."""
    pass


# ── MCP Exceptions ──────────────────────────────────────────────────────

class MCPAuthenticationError(TradingSystemError):
    """MCP tool call failed authentication."""
    pass


class MCPRateLimitError(TradingSystemError):
    """MCP tool call rate limit exceeded."""
    pass


class MCPToolError(TradingSystemError):
    """Error executing an MCP tool."""
    pass
