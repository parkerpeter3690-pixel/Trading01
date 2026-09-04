"""
Volatility Strategy
====================

Trades based on volatility regime changes using ATR,
realized vs historical volatility, and volatility mean reversion.

Supported Regimes: HIGH_VOLATILITY, LOW_VOLATILITY
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import numpy as np
import pandas_ta as ta
from src.strategies.base import BaseStrategy, MarketContext, MarketRegime, SignalDirection, StrategySignal


class VolatilityStrategy(BaseStrategy):
    def __init__(self, atr_period: int = 14, vol_short: int = 10, vol_long: int = 60) -> None:
        self._atr_period = atr_period
        self._vol_short = vol_short
        self._vol_long = vol_long

    @property
    def name(self) -> str: return "volatility"
    @property
    def version(self) -> str: return "v1.0"
    @property
    def strategy_type(self) -> str: return "volatility"
    @property
    def supported_regimes(self) -> list[MarketRegime]:
        return [MarketRegime.HIGH_VOLATILITY, MarketRegime.LOW_VOLATILITY]

    async def generate_signals(self, context: MarketContext) -> list[StrategySignal]:
        df = context.data.copy()
        if not self.validate_data(df, min_rows=self._vol_long + 20):
            return []

        returns = df["close"].pct_change()
        vol_short = float(returns.tail(self._vol_short).std() * np.sqrt(252))
        vol_long = float(returns.tail(self._vol_long).std() * np.sqrt(252))
        vol_ratio = vol_short / vol_long if vol_long > 0 else 1.0

        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=self._atr_period)
        df["rsi"] = ta.rsi(df["close"], length=14)
        price = float(df["close"].iloc[-1])
        current_atr = float(df["atr"].iloc[-1])
        rsi = float(df["rsi"].iloc[-1])

        reasoning = {"vol_short": round(vol_short*100, 2), "vol_long": round(vol_long*100, 2), "vol_ratio": round(vol_ratio, 3)}

        # Vol squeeze (low → expect expansion)
        if vol_ratio < 0.5:
            # Prepare for breakout, wait for direction
            direction = SignalDirection.HOLD
            reasoning["signal"] = "Volatility squeeze detected, awaiting breakout direction"
            confidence = 0.5
        # Vol expansion with RSI confirmation
        elif vol_ratio > 1.5 and rsi < 30:
            direction = SignalDirection.BUY
            reasoning["signal"] = f"High vol + oversold RSI ({rsi:.1f}), mean reversion setup"
            confidence = 0.65
        elif vol_ratio > 1.5 and rsi > 70:
            direction = SignalDirection.SELL
            reasoning["signal"] = f"High vol + overbought RSI ({rsi:.1f}), mean reversion setup"
            confidence = 0.65
        else:
            return []

        if direction == SignalDirection.HOLD:
            return [StrategySignal(
                strategy_name=self.name, strategy_version=self.version,
                symbol=context.symbol, timeframe=context.timeframe,
                generated_at=datetime.now(timezone.utc),
                direction=direction, strength=0.0, confidence=confidence,
                market_regime=context.market_regime, reasoning=reasoning,
                indicators_used={"vol_ratio": round(vol_ratio, 3), "rsi": round(rsi, 2), "atr": round(current_atr, 4)},
            )]

        sl = current_atr * 2.5
        tp = current_atr * 3.5
        stop_loss = price - sl if direction == SignalDirection.BUY else price + sl
        take_profit = price + tp if direction == SignalDirection.BUY else price - tp

        return [StrategySignal(
            strategy_name=self.name, strategy_version=self.version,
            symbol=context.symbol, timeframe=context.timeframe,
            generated_at=datetime.now(timezone.utc),
            direction=direction, strength=0.6, confidence=round(confidence, 3),
            entry_price=round(price, 4),
            stop_loss=round(stop_loss, 4), take_profit=round(take_profit, 4),
            risk_reward_ratio=round(tp/sl, 2) if sl > 0 else None,
            market_regime=context.market_regime, time_horizon="short",
            reasoning=reasoning,
            indicators_used={"vol_ratio": round(vol_ratio, 3), "rsi": round(rsi, 2), "atr": round(current_atr, 4)},
        )]
