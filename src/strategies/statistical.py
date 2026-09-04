"""
Statistical Strategy
=====================

Uses statistical methods for trading:
- Correlation analysis between assets
- Mean/variance analysis
- Statistical arbitrage signals
- Regime detection via hidden states

Supported Regimes: ALL (statistical methods are regime-aware)
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import numpy as np
import pandas_ta as ta
from src.strategies.base import BaseStrategy, MarketContext, MarketRegime, SignalDirection, StrategySignal


class StatisticalStrategy(BaseStrategy):
    def __init__(self, zscore_window: int = 30, zscore_entry: float = 2.0, zscore_exit: float = 0.5) -> None:
        self._zscore_window = zscore_window
        self._zscore_entry = zscore_entry
        self._zscore_exit = zscore_exit

    @property
    def name(self) -> str: return "statistical"
    @property
    def version(self) -> str: return "v1.0"
    @property
    def strategy_type(self) -> str: return "statistical"
    @property
    def supported_regimes(self) -> list[MarketRegime]:
        return list(MarketRegime)

    async def generate_signals(self, context: MarketContext) -> list[StrategySignal]:
        df = context.data.copy()
        if not self.validate_data(df, min_rows=self._zscore_window + 30):
            return []

        # Z-score of returns
        returns = df["close"].pct_change()
        rolling_mean = returns.rolling(self._zscore_window).mean()
        rolling_std = returns.rolling(self._zscore_window).std()
        zscore = (returns - rolling_mean) / rolling_std
        df["return_zscore"] = zscore

        # Price z-score relative to rolling mean
        price_mean = df["close"].rolling(self._zscore_window).mean()
        price_std = df["close"].rolling(self._zscore_window).std()
        df["price_zscore"] = (df["close"] - price_mean) / price_std

        latest = df.iloc[-1]
        price = latest["close"]
        pz = latest["price_zscore"]
        rz = latest["return_zscore"]

        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
        atr = float(df["atr"].iloc[-1])

        reasoning = {"price_zscore": round(pz, 3), "return_zscore": round(rz, 3)}

        if pz < -self._zscore_entry:
            direction = SignalDirection.BUY
            reasoning["signal"] = f"Price z-score {pz:.2f} < -{self._zscore_entry} (statistically oversold)"
            confidence = min(0.45 + abs(pz - self._zscore_entry) * 0.1, 0.80)
            stop_loss = price - atr * 2
            take_profit = float(price_mean.iloc[-1])
        elif pz > self._zscore_entry:
            direction = SignalDirection.SELL
            reasoning["signal"] = f"Price z-score {pz:.2f} > {self._zscore_entry} (statistically overbought)"
            confidence = min(0.45 + abs(pz - self._zscore_entry) * 0.1, 0.80)
            stop_loss = price + atr * 2
            take_profit = float(price_mean.iloc[-1])
        else:
            return []

        rr = abs(take_profit - price) / abs(price - stop_loss) if abs(price - stop_loss) > 0 else None

        return [StrategySignal(
            strategy_name=self.name, strategy_version=self.version,
            symbol=context.symbol, timeframe=context.timeframe,
            generated_at=datetime.now(timezone.utc),
            direction=direction, strength=round(min(abs(pz) / 3, 1.0), 3),
            confidence=round(confidence, 3),
            entry_price=round(price, 4),
            stop_loss=round(stop_loss, 4), take_profit=round(take_profit, 4),
            risk_reward_ratio=round(rr, 2) if rr else None,
            market_regime=context.market_regime, time_horizon="short",
            reasoning=reasoning,
            indicators_used={"price_zscore": round(pz, 3), "atr": round(atr, 4)},
        )]
