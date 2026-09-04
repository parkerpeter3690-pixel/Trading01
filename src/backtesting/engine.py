"""
Backtesting Engine
==================

Simulates historical trading by stepping through time, generating signals,
and executing orders via a simulated PaperBroker.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import pandas as pd

from src.brokers.base import OrderRequest, OrderSide, OrderType
from src.brokers.paper_broker import PaperBroker
from src.core.logging import get_logger
from src.data.base import MarketDataProvider
from src.risk.engine import RiskEngine
from src.signals.fusion import SignalFusionEngine
from src.strategies.base import BaseStrategy, MarketContext, SignalDirection

logger = get_logger("backtest")


class BacktestEngine:
    """
    Event-driven backtesting engine.
    """

    def __init__(
        self,
        strategies: list[BaseStrategy],
        data_provider: MarketDataProvider,
        fusion_engine: SignalFusionEngine | None = None,
        initial_capital: float = 100000.0,
    ) -> None:
        self._strategies = strategies
        self._data_provider = data_provider
        self._fusion = fusion_engine or SignalFusionEngine()
        self._broker = PaperBroker(initial_capital=initial_capital)
        self._risk_engine = RiskEngine(self._broker)
        
        self.trade_history: list[dict[str, Any]] = []

    async def run(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1d",
        min_history_bars: int = 50,
    ) -> dict[str, Any]:
        """
        Run a backtest for a specific symbol over a date range.
        
        Fetches the full dataset, then iterates row by row, building
        a rolling context window.
        """
        logger.info(
            "backtest_started",
            symbol=symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            timeframe=timeframe
        )

        # 1. Fetch entire historical dataset + padding for indicators
        # We fetch more days before the start date to prime the indicators
        df = await self._data_provider.get_historical_data(
            symbol=symbol, timeframe=timeframe, start=start, end=end
        )
        
        if df.empty or len(df) < min_history_bars:
            logger.error("backtest_failed", reason="Insufficient historical data")
            return {"error": "Insufficient historical data"}

        total_bars = len(df)
        executed_trades = 0

        # 2. Iterate through time
        for i in range(min_history_bars, total_bars):
            # The "current" time is the index of the current row
            current_time = df.index[i]
            current_row = df.iloc[i]
            current_price = float(current_row["close"])
            
            # The historical window available up to this point
            window_df = df.iloc[:i+1]

            # Update broker price (triggers pending stops/limits)
            await self._broker.update_price(symbol, current_price)

            # Build context
            context = MarketContext(
                symbol=symbol,
                timeframe=timeframe,
                data=window_df,
                current_price=current_price,
            )

            # Generate signals
            all_signals = []
            for strategy in self._strategies:
                try:
                    signals = await strategy.generate_signals(context)
                    all_signals.extend(signals)
                except Exception:
                    pass
            
            # Detect regime
            regime_signal = next((s for s in all_signals if s.strategy_name == "regime"), None)
            regime = regime_signal.market_regime if regime_signal else None
            context.market_regime = regime

            # Fuse signals
            fused = self._fusion.fuse(all_signals, market_regime=regime)

            # 3. Decision Logic (Mathematical only - bypassing LLM)
            if fused.direction in (SignalDirection.BUY, SignalDirection.SELL):
                action = fused.direction.value
                
                # Ensure SL/TP exist to pass the Risk Engine
                sl = fused.stop_loss
                tp = fused.take_profit
                if sl is None:
                    if action == "buy":
                        sl = current_price * 0.95
                        tp = current_price * 1.10
                    elif action == "sell":
                        sl = current_price * 1.05
                        tp = current_price * 0.90
                
                order_request = OrderRequest(
                    symbol=symbol,
                    side=OrderSide.BUY if action == "buy" else OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=1.0,  # Or sized by risk engine
                    stop_loss=sl,
                    take_profit=tp,
                )
                
                risk_result = await self._risk_engine.validate_order(order_request)
                
                if risk_result.passed:
                    try:
                        # Execute the trade
                        await self._broker.place_order(order_request)
                        executed_trades += 1
                        self.trade_history.append({
                            "time": current_time,
                            "action": action,
                            "price": current_price,
                            "score": fused.combined_score,
                            "reason": "Fusion score threshold met"
                        })
                    except Exception as e:
                        logger.error("backtest_execution_error", error=str(e))

        # Close all open positions at the last price to calculate final PnL
        open_positions = await self._broker.get_positions()
        last_price = float(df.iloc[-1]["close"])
        for pos in open_positions:
            side = OrderSide.SELL if pos.side == "long" else OrderSide.BUY
            close_req = OrderRequest(
                symbol=pos.symbol,
                side=side,
                order_type=OrderType.MARKET,
                quantity=pos.quantity
            )
            await self._broker.update_price(pos.symbol, last_price)
            await self._broker.place_order(close_req)

        account = await self._broker.get_account()
        
        logger.info(
            "backtest_completed",
            symbol=symbol,
            trades=executed_trades,
            final_equity=account.portfolio_value
        )
        
        return {
            "symbol": symbol,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "initial_capital": self._broker._initial_capital,
            "final_equity": account.portfolio_value,
            "total_trades": executed_trades,
            "trade_history": self.trade_history
        }
