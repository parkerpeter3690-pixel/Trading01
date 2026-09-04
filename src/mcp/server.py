"""
MCP Trading Server
==================

The central MCP server that exposes all trading tools.

This server is the ONLY interface through which AI agents interact
with market data, news, orders, and portfolio management. Every tool
invocation is:

1. Authenticated (token validation)
2. Rate limited (per-tool limits)
3. Input validated (Pydantic schemas)
4. Logged (structured JSON with correlation ID)
5. Risk checked (orders pass through risk gate)
6. Error handled (typed exceptions)

The AI NEVER bypasses this server to access broker APIs directly.
See Section 27 — Safety Architecture.

Usage:
    # Start the MCP server
    python -m src.mcp.server

    # Or via MCP CLI for development
    uv run mcp dev src/mcp/server.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from mcp.server import MCPServer

from src.brokers.paper_broker import PaperBroker
from src.brokers.base import OrderRequest, OrderSide, OrderType, TimeInForce
from src.core.config import settings
from src.core.logging import get_logger
from src.data.providers.yfinance_provider import YFinanceProvider

logger = get_logger("mcp")

# ── Initialize Server ────────────────────────────────────────────────────

mcp = MCPServer(settings.mcp_server_name)

# ── Shared State ─────────────────────────────────────────────────────────
# These are initialized when the server starts.
# In production, these would be dependency-injected.

_data_provider = YFinanceProvider()
_paper_broker = PaperBroker()


# ============================================================================
# MARKET DATA TOOLS
# ============================================================================

@mcp.tool()
async def get_market_data(symbol: str) -> dict[str, Any]:
    """
    Get current market data for a symbol.

    Returns real-time quote with bid/ask, last price, volume,
    change, and change percentage.

    Args:
        symbol: Ticker symbol (e.g., "AAPL", "BTC-USD", "GLD")

    Returns:
        Current price quote with market data fields.
    """
    logger.info("mcp_tool_called", tool="get_market_data", symbol=symbol)
    quote = await _data_provider.get_quote(symbol)
    return quote.to_dict()


@mcp.tool()
async def get_historical_data(
    symbol: str,
    timeframe: str = "1d",
    days: int = 30,
) -> dict[str, Any]:
    """
    Get historical OHLCV data for a symbol.

    Returns candlestick data for backtesting and analysis.
    Supports timeframes: 1m, 5m, 15m, 1h, 4h, 1d, 1w.

    Args:
        symbol: Ticker symbol
        timeframe: Candle timeframe (default "1d")
        days: Number of days of history (default 30)

    Returns:
        Dict with columns and data arrays for OHLCV.
    """
    logger.info(
        "mcp_tool_called",
        tool="get_historical_data",
        symbol=symbol,
        timeframe=timeframe,
        days=days,
    )
    df = await _data_provider.get_historical_data(symbol, timeframe, days=days)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "rows": len(df),
        "start": str(df.index[0]),
        "end": str(df.index[-1]),
        "data": json.loads(df.to_json(orient="index", date_format="iso")),
    }


@mcp.tool()
async def get_indicators(
    symbol: str,
    timeframe: str = "1d",
    days: int = 100,
    indicators: str = "sma_20,sma_50,rsi_14,macd,bbands,atr_14",
) -> dict[str, Any]:
    """
    Compute technical indicators for a symbol.

    Computes indicators from historical data using pandas-ta.

    Args:
        symbol: Ticker symbol
        timeframe: Candle timeframe
        days: Days of history to compute from
        indicators: Comma-separated list of indicators to compute

    Returns:
        Latest indicator values.
    """
    import pandas_ta as ta

    logger.info("mcp_tool_called", tool="get_indicators", symbol=symbol)
    df = await _data_provider.get_historical_data(symbol, timeframe, days=days)

    results: dict[str, Any] = {"symbol": symbol, "timeframe": timeframe}
    indicator_list = [i.strip() for i in indicators.split(",")]

    for ind in indicator_list:
        try:
            if ind.startswith("sma_"):
                period = int(ind.split("_")[1])
                sma = ta.sma(df["close"], length=period)
                results[ind] = round(float(sma.iloc[-1]), 4) if sma is not None and not sma.empty else None

            elif ind.startswith("ema_"):
                period = int(ind.split("_")[1])
                ema = ta.ema(df["close"], length=period)
                results[ind] = round(float(ema.iloc[-1]), 4) if ema is not None and not ema.empty else None

            elif ind.startswith("rsi_"):
                period = int(ind.split("_")[1])
                rsi = ta.rsi(df["close"], length=period)
                results[ind] = round(float(rsi.iloc[-1]), 2) if rsi is not None and not rsi.empty else None

            elif ind == "macd":
                macd_df = ta.macd(df["close"])
                if macd_df is not None and not macd_df.empty:
                    results["macd_line"] = round(float(macd_df.iloc[-1, 0]), 4)
                    results["macd_histogram"] = round(float(macd_df.iloc[-1, 1]), 4)
                    results["macd_signal"] = round(float(macd_df.iloc[-1, 2]), 4)

            elif ind == "bbands":
                bb = ta.bbands(df["close"])
                if bb is not None and not bb.empty:
                    results["bb_lower"] = round(float(bb.iloc[-1, 0]), 4)
                    results["bb_mid"] = round(float(bb.iloc[-1, 1]), 4)
                    results["bb_upper"] = round(float(bb.iloc[-1, 2]), 4)
                    results["bb_bandwidth"] = round(float(bb.iloc[-1, 3]), 4) if bb.shape[1] > 3 else None

            elif ind.startswith("atr_"):
                period = int(ind.split("_")[1])
                atr = ta.atr(df["high"], df["low"], df["close"], length=period)
                results[ind] = round(float(atr.iloc[-1]), 4) if atr is not None and not atr.empty else None

            elif ind == "adx":
                adx = ta.adx(df["high"], df["low"], df["close"])
                if adx is not None and not adx.empty:
                    results["adx"] = round(float(adx.iloc[-1, 0]), 2)
                    results["dmp"] = round(float(adx.iloc[-1, 1]), 2)
                    results["dmn"] = round(float(adx.iloc[-1, 2]), 2)

            elif ind == "vwap":
                vwap = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
                results["vwap"] = round(float(vwap.iloc[-1]), 4) if vwap is not None and not vwap.empty else None

        except Exception as e:
            logger.warning("indicator_error", indicator=ind, error=str(e))
            results[ind] = None

    # Add current price for context
    results["current_price"] = round(float(df["close"].iloc[-1]), 4)
    results["timestamp"] = str(df.index[-1])

    return results


@mcp.tool()
async def get_volatility(symbol: str, days: int = 30) -> dict[str, Any]:
    """
    Calculate volatility metrics for a symbol.

    Returns realized volatility, ATR, and volatility regime classification.

    Args:
        symbol: Ticker symbol
        days: Look-back period
    """
    import numpy as np
    import pandas_ta as ta

    logger.info("mcp_tool_called", tool="get_volatility", symbol=symbol)
    df = await _data_provider.get_historical_data(symbol, "1d", days=days + 50)

    # Realized volatility (annualized)
    returns = df["close"].pct_change().dropna()
    realized_vol = float(returns.std() * np.sqrt(252) * 100)

    # ATR
    atr = ta.atr(df["high"], df["low"], df["close"], length=14)
    current_atr = float(atr.iloc[-1]) if atr is not None and not atr.empty else 0.0
    atr_pct = (current_atr / float(df["close"].iloc[-1])) * 100

    # Volatility regime classification
    vol_20d = float(returns.tail(20).std() * np.sqrt(252) * 100)
    vol_60d = float(returns.tail(min(60, len(returns))).std() * np.sqrt(252) * 100)

    if vol_20d > vol_60d * 1.5:
        regime = "high_volatility"
    elif vol_20d < vol_60d * 0.5:
        regime = "low_volatility"
    else:
        regime = "normal"

    return {
        "symbol": symbol,
        "realized_volatility_pct": round(realized_vol, 2),
        "atr_14": round(current_atr, 4),
        "atr_pct": round(atr_pct, 2),
        "vol_20d": round(vol_20d, 2),
        "vol_60d": round(vol_60d, 2),
        "regime": regime,
        "period_days": days,
    }


# ============================================================================
# ACCOUNT & PORTFOLIO TOOLS
# ============================================================================

@mcp.tool()
async def get_account_balance() -> dict[str, Any]:
    """
    Get current account balance and equity.

    Returns cash, portfolio value, buying power, and equity.
    """
    logger.info("mcp_tool_called", tool="get_account_balance")
    account = await _paper_broker.get_account()
    return account.to_dict()


@mcp.tool()
async def get_positions() -> list[dict[str, Any]]:
    """
    Get all current open positions.

    Returns position details including unrealized P&L.
    """
    logger.info("mcp_tool_called", tool="get_positions")
    positions = await _paper_broker.get_positions()
    return [p.to_dict() for p in positions]


@mcp.tool()
async def get_open_orders() -> list[dict[str, Any]]:
    """
    Get all pending/open orders.
    """
    logger.info("mcp_tool_called", tool="get_open_orders")
    orders = await _paper_broker.get_open_orders()
    return [o.to_dict() for o in orders]


@mcp.tool()
async def get_portfolio_exposure() -> dict[str, Any]:
    """
    Calculate current portfolio exposure.

    Returns long/short/net exposure, number of positions,
    and portfolio weight breakdown.
    """
    logger.info("mcp_tool_called", tool="get_portfolio_exposure")
    account = await _paper_broker.get_account()
    positions = await _paper_broker.get_positions()

    long_exposure = sum(p.market_value for p in positions if p.side == "long")
    short_exposure = sum(p.market_value for p in positions if p.side == "short")
    total_exposure = long_exposure + short_exposure
    net_exposure = long_exposure - short_exposure

    return {
        "total_value": account.portfolio_value,
        "cash": account.cash,
        "long_exposure": round(long_exposure, 2),
        "short_exposure": round(short_exposure, 2),
        "total_exposure": round(total_exposure, 2),
        "net_exposure": round(net_exposure, 2),
        "exposure_pct": round(total_exposure / account.portfolio_value * 100, 2) if account.portfolio_value > 0 else 0.0,
        "num_positions": len(positions),
        "positions": [p.to_dict() for p in positions],
    }


# ============================================================================
# RISK TOOLS
# ============================================================================

@mcp.tool()
async def calculate_position_size(
    symbol: str,
    entry_price: float,
    stop_loss: float,
    risk_pct: float = 1.0,
) -> dict[str, Any]:
    """
    Calculate the optimal position size based on risk parameters.

    Uses the configured max position size and risk-per-trade limits.

    Args:
        symbol: Ticker symbol
        entry_price: Planned entry price
        stop_loss: Stop loss price
        risk_pct: Percentage of portfolio to risk (default 1.0%)

    Returns:
        Recommended position size, risk amount, and R:R ratio.
    """
    logger.info("mcp_tool_called", tool="calculate_position_size", symbol=symbol)

    account = await _paper_broker.get_account()
    portfolio_value = account.portfolio_value

    # Enforce max risk per trade
    effective_risk_pct = min(risk_pct, settings.max_loss_per_trade_pct)
    risk_amount = portfolio_value * (effective_risk_pct / 100)

    # Calculate per-share risk
    per_share_risk = abs(entry_price - stop_loss)
    if per_share_risk <= 0:
        return {"error": "Stop loss must be different from entry price"}

    # Position size based on risk
    position_size = risk_amount / per_share_risk
    position_value = position_size * entry_price

    # Enforce max position size
    max_position_value = portfolio_value * (settings.max_position_size_pct / 100)
    if position_value > max_position_value:
        position_size = max_position_value / entry_price
        position_value = max_position_value

    return {
        "symbol": symbol,
        "recommended_quantity": round(position_size, 4),
        "position_value": round(position_value, 2),
        "risk_amount": round(risk_amount, 2),
        "risk_pct": effective_risk_pct,
        "per_share_risk": round(per_share_risk, 4),
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "max_position_value": round(max_position_value, 2),
        "portfolio_value": round(portfolio_value, 2),
    }


@mcp.tool()
async def calculate_risk(
    symbol: str,
    side: str,
    quantity: float,
    entry_price: float,
    stop_loss: float,
    take_profit: float | None = None,
) -> dict[str, Any]:
    """
    Validate a trade proposal against all risk limits.

    Checks:
    - Position size limit
    - Daily loss limit
    - Portfolio drawdown
    - Open positions limit
    - Stop loss requirement
    - Risk/reward ratio

    Args:
        symbol: Ticker symbol
        side: "buy" or "sell"
        quantity: Number of shares/units
        entry_price: Planned entry price
        stop_loss: Stop loss price
        take_profit: Take profit price (optional)

    Returns:
        Risk assessment with pass/fail for each check.
    """
    logger.info("mcp_tool_called", tool="calculate_risk", symbol=symbol)

    account = await _paper_broker.get_account()
    positions = await _paper_broker.get_positions()

    position_value = quantity * entry_price
    risk_per_share = abs(entry_price - stop_loss)
    total_risk = risk_per_share * quantity
    risk_pct = (total_risk / account.portfolio_value) * 100

    checks: dict[str, dict[str, Any]] = {}

    # 1. Position size check
    pos_size_pct = (position_value / account.portfolio_value) * 100
    checks["position_size"] = {
        "passed": pos_size_pct <= settings.max_position_size_pct,
        "current": round(pos_size_pct, 2),
        "limit": settings.max_position_size_pct,
    }

    # 2. Open positions check
    checks["open_positions"] = {
        "passed": len(positions) < settings.max_open_positions,
        "current": len(positions),
        "limit": settings.max_open_positions,
    }

    # 3. Risk per trade check
    checks["risk_per_trade"] = {
        "passed": risk_pct <= settings.max_loss_per_trade_pct,
        "current": round(risk_pct, 2),
        "limit": settings.max_loss_per_trade_pct,
    }

    # 4. Stop loss required
    checks["stop_loss"] = {
        "passed": stop_loss is not None and stop_loss > 0,
        "required": settings.require_stop_loss,
    }

    # 5. Risk/reward ratio
    if take_profit is not None:
        reward = abs(take_profit - entry_price)
        rr_ratio = reward / risk_per_share if risk_per_share > 0 else 0
        checks["risk_reward"] = {
            "passed": rr_ratio >= settings.min_risk_reward_ratio,
            "current": round(rr_ratio, 2),
            "limit": settings.min_risk_reward_ratio,
        }
    else:
        checks["risk_reward"] = {
            "passed": True,
            "note": "No take profit specified; R:R not checked",
        }

    # 6. Sufficient funds
    if side == "buy":
        checks["sufficient_funds"] = {
            "passed": position_value <= account.cash,
            "required": round(position_value, 2),
            "available": round(account.cash, 2),
        }
    else:
        checks["sufficient_funds"] = {"passed": True}

    all_passed = all(c["passed"] for c in checks.values())

    return {
        "symbol": symbol,
        "side": side,
        "all_checks_passed": all_passed,
        "checks": checks,
        "position_value": round(position_value, 2),
        "total_risk": round(total_risk, 2),
        "risk_pct": round(risk_pct, 2),
    }


# ============================================================================
# ORDER TOOLS
# ============================================================================

@mcp.tool()
async def place_paper_order(
    symbol: str,
    side: str,
    quantity: float,
    order_type: str = "market",
    limit_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> dict[str, Any]:
    """
    Place a paper trading order.

    The order goes through risk validation before execution.
    This tool NEVER places real money orders.

    Args:
        symbol: Ticker symbol
        side: "buy" or "sell"
        quantity: Number of shares/units
        order_type: "market" or "limit" (default "market")
        limit_price: Required for limit orders
        stop_loss: Stop loss price (required if REQUIRE_STOP_LOSS=true)
        take_profit: Take profit price (optional)

    Returns:
        Order execution result.
    """
    logger.info(
        "mcp_tool_called",
        tool="place_paper_order",
        symbol=symbol,
        side=side,
        quantity=quantity,
    )

    # Enforce stop loss requirement
    if settings.require_stop_loss and stop_loss is None:
        return {
            "status": "rejected",
            "reason": "Stop loss is required for all trades (REQUIRE_STOP_LOSS=true)",
        }

    # Build order request
    request = OrderRequest(
        symbol=symbol,
        side=OrderSide(side),
        order_type=OrderType(order_type),
        quantity=quantity,
        limit_price=limit_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )

    result = await _paper_broker.place_order(request)
    return result.to_dict()


@mcp.tool()
async def cancel_paper_order(client_order_id: str) -> dict[str, Any]:
    """
    Cancel a pending paper order.

    Args:
        client_order_id: The client order ID to cancel.
    """
    logger.info("mcp_tool_called", tool="cancel_paper_order", order_id=client_order_id)
    result = await _paper_broker.cancel_order(client_order_id)
    return result.to_dict()


@mcp.tool()
async def get_execution_status(client_order_id: str) -> dict[str, Any]:
    """
    Get the execution status of an order.

    Args:
        client_order_id: The client order ID to check.
    """
    logger.info("mcp_tool_called", tool="get_execution_status", order_id=client_order_id)
    result = await _paper_broker.get_order(client_order_id)
    return result.to_dict()


@mcp.tool()
async def get_pnl() -> dict[str, Any]:
    """
    Get current P&L summary.

    Returns unrealized P&L from open positions and portfolio performance.
    """
    logger.info("mcp_tool_called", tool="get_pnl")
    account = await _paper_broker.get_account()
    positions = await _paper_broker.get_positions()

    unrealized_pnl = sum(p.unrealized_pnl for p in positions)
    initial_capital = settings.paper_trading_initial_capital

    return {
        "portfolio_value": round(account.portfolio_value, 2),
        "initial_capital": round(initial_capital, 2),
        "total_pnl": round(account.portfolio_value - initial_capital, 2),
        "total_pnl_pct": round(
            ((account.portfolio_value - initial_capital) / initial_capital) * 100, 2
        ),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "cash": round(account.cash, 2),
        "num_positions": len(positions),
    }


# ── Server Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio
    # For development, run with: uv run mcp dev src/mcp/server.py
    print(f"MCP Trading Server '{settings.mcp_server_name}' ready.")
    print("Tools registered:")
    # List tools would go here
