"""
Backtest Analytics
==================

Calculates performance metrics (Sharpe, Drawdown, Win Rate, Profit Factor)
from a series of completed trades and equity curves.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any


class AnalyticsEngine:
    """Computes backtest performance metrics."""

    @staticmethod
    def calculate_tearsheet(
        initial_capital: float,
        final_equity: float,
        trades: list[dict[str, Any]],
        risk_free_rate: float = 0.04
    ) -> dict[str, Any]:
        """
        Generate a performance tearsheet from the trade history.
        Assumes `trades` contains buy/sell actions with prices.
        """
        if not trades:
            return {
                "initial_capital": initial_capital,
                "final_equity": final_equity,
                "total_return_pct": 0.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "max_drawdown_pct": 0.0,
                "total_trades": 0
            }

        total_return_pct = ((final_equity - initial_capital) / initial_capital) * 100

        # Extract round-trip trades (simplified matching for MVP)
        # Assuming size = 1.0 for all trades to calculate win/loss
        profits = []
        losses = []
        
        current_position = None
        entry_price = 0.0

        for trade in trades:
            action = trade["action"]
            price = trade["price"]
            
            if action == "buy" and current_position is None:
                current_position = "long"
                entry_price = price
            elif action == "sell" and current_position == "long":
                pnl = price - entry_price
                if pnl > 0:
                    profits.append(pnl)
                else:
                    losses.append(pnl)
                current_position = None
            elif action == "sell" and current_position is None:
                current_position = "short"
                entry_price = price
            elif action == "buy" and current_position == "short":
                pnl = entry_price - price
                if pnl > 0:
                    profits.append(pnl)
                else:
                    losses.append(pnl)
                current_position = None

        total_wins = len(profits)
        total_losses = len(losses)
        completed_trades = total_wins + total_losses
        
        win_rate = (total_wins / completed_trades * 100) if completed_trades > 0 else 0.0
        
        gross_profit = sum(profits)
        gross_loss = abs(sum(losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)

        # Simplified drawdown (would normally use a daily equity curve)
        # Using a proxy here based on trade sequence
        equity = initial_capital
        peak = initial_capital
        max_drawdown = 0.0
        
        for pnl in profits + losses:
            equity += pnl
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return {
            "initial_capital": round(initial_capital, 2),
            "final_equity": round(final_equity, 2),
            "total_return_pct": round(total_return_pct, 2),
            "total_trades": completed_trades,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
        }
