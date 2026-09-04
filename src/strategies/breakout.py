"""
Breakout Strategy
==================

Detects price breakouts from consolidation ranges using:
- Consolidation detection (narrow range bars)
- Volume expansion on breakout
- Support/resistance level breaks
- Volatility expansion (ATR breakout)

Supported Regimes: RANGING → TRENDING transition, LOW_VOLATILITY (pre-breakout)
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import numpy as np
import pandas_ta as ta
from src.strategies.base import BaseStrategy, MarketContext, MarketRegime, SignalDirection, StrategySignal


class BreakoutStrategy(BaseStrategy):

    def __init__(self, lookback: int = 20, atr_period: int = 14, vol_expansion: float = 1.5,
                 atr_sl_mult: float = 1.5, atr_tp_mult: float = 3.0) -> None:
        self._lookback = lookback
        self._atr_period = atr_period
        self._vol_expansion = vol_expansion
        self._atr_sl_mult = atr_sl_mult
        self._atr_tp_mult = atr_tp_mult

    @property
    def name(self) -> str: return "breakout"
    @property
    def version(self) -> str: return "v1.0"
    @property
    def strategy_type(self) -> str: return "breakout"
    @property
    def supported_regimes(self) -> list[MarketRegime]:
        return [MarketRegime.RANGING, MarketRegime.LOW_VOLATILITY]

    async def generate_signals(self, context: MarketContext) -> list[StrategySignal]:
        df = context.data.copy()
        if not self.validate_data(df, min_rows=self._lookback + 30):
            return []

        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=self._atr_period)
        df["vol_ma"] = ta.sma(df["volume"], length=self._lookback)

        # Support and resistance from lookback range
        lookback_high = df["high"].rolling(self._lookback).max()
        lookback_low = df["low"].rolling(self._lookback).min()
        df["resistance"] = lookback_high
        df["support"] = lookback_low
        df["range_width"] = (lookback_high - lookback_low) / lookback_low * 100

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        price = latest["close"]
        resistance = latest["resistance"]
        support = latest["support"]
        current_atr = latest["atr"]
        vol_strong = latest["volume"] > latest["vol_ma"] * self._vol_expansion

        reasoning: dict[str, Any] = {}
        bull = bear = 0.0

        # Breakout above resistance
        if price > resistance and prev["close"] <= prev["resistance"]:
            bull += 0.40
            reasoning["breakout"] = f"price broke above resistance {resistance:.2f}"
        elif price < support and prev["close"] >= prev["support"]:
            bear += 0.40
            reasoning["breakout"] = f"price broke below support {support:.2f}"
        else:
            reasoning["breakout"] = "no breakout detected"
            return []  # No breakout → no signal

        # Volume confirmation
        if vol_strong:
            bull += 0.20 if bull > 0 else 0
            bear += 0.20 if bear > 0 else 0
            reasoning["volume"] = "expanding (confirms breakout)"
        else:
            reasoning["volume"] = "weak (false breakout risk)"
            bull *= 0.6
            bear *= 0.6

        # ATR expansion
        atr_prev_avg = df["atr"].tail(10).mean()
        if current_atr > atr_prev_avg * 1.2:
            bull += 0.10
            bear += 0.10
            reasoning["volatility"] = "expanding (confirms breakout)"

        net = bull - bear
        if net > 0.2:
            direction = SignalDirection.BUY
            stop_loss = price - (current_atr * self._atr_sl_mult)
            take_profit = price + (current_atr * self._atr_tp_mult)
        elif net < -0.2:
            direction = SignalDirection.SELL
            stop_loss = price + (current_atr * self._atr_sl_mult)
            take_profit = price - (current_atr * self._atr_tp_mult)
        else:
            return []

        rr = abs(take_profit - price) / abs(price - stop_loss) if abs(price - stop_loss) > 0 else None
        confidence = min(0.4 + sum([vol_strong, abs(net) > 0.4]) * 0.2, 0.85)

        return [StrategySignal(
            strategy_name=self.name, strategy_version=self.version,
            symbol=context.symbol, timeframe=context.timeframe,
            generated_at=datetime.now(timezone.utc),
            direction=direction, strength=round(abs(net), 3),
            confidence=round(confidence, 3),
            entry_price=round(price, 4),
            stop_loss=round(stop_loss, 4), take_profit=round(take_profit, 4),
            risk_reward_ratio=round(rr, 2) if rr else None,
            market_regime=context.market_regime, time_horizon="medium",
            reasoning=reasoning,
            indicators_used={"resistance": round(resistance, 4), "support": round(support, 4), "atr": round(current_atr, 4)},
        )]
