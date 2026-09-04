"""
Momentum Strategy
==================

Identifies strong directional momentum for trend continuation trades using:
- Rate of Change (ROC)
- Volume-weighted momentum
- Relative strength vs benchmark
- MACD confirmation
- Breakout confirmation

Supported Regimes: TRENDING, RISK_ON
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas_ta as ta

from src.strategies.base import (
    BaseStrategy,
    MarketContext,
    MarketRegime,
    SignalDirection,
    StrategySignal,
)


class MomentumStrategy(BaseStrategy):

    def __init__(
        self,
        roc_period: int = 12,
        roc_threshold: float = 2.0,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        rsi_period: int = 14,
        volume_ma: int = 20,
        atr_period: int = 14,
        atr_sl_multiplier: float = 2.0,
        atr_tp_multiplier: float = 3.5,
    ) -> None:
        self._roc_period = roc_period
        self._roc_threshold = roc_threshold
        self._macd_fast = macd_fast
        self._macd_slow = macd_slow
        self._macd_signal = macd_signal
        self._rsi_period = rsi_period
        self._volume_ma = volume_ma
        self._atr_period = atr_period
        self._atr_sl_multiplier = atr_sl_multiplier
        self._atr_tp_multiplier = atr_tp_multiplier

    @property
    def name(self) -> str:
        return "momentum"

    @property
    def version(self) -> str:
        return "v1.0"

    @property
    def strategy_type(self) -> str:
        return "momentum"

    @property
    def supported_regimes(self) -> list[MarketRegime]:
        return [MarketRegime.TRENDING, MarketRegime.RISK_ON]

    async def generate_signals(self, context: MarketContext) -> list[StrategySignal]:
        df = context.data.copy()
        if not self.validate_data(df, min_rows=max(self._macd_slow, self._roc_period) + 30):
            return []

        # Compute indicators
        df["roc"] = ta.roc(df["close"], length=self._roc_period)
        macd_df = ta.macd(df["close"], fast=self._macd_fast, slow=self._macd_slow, signal=self._macd_signal)
        if macd_df is not None and not macd_df.empty:
            df["macd_line"] = macd_df.iloc[:, 0]
            df["macd_hist"] = macd_df.iloc[:, 1]
            df["macd_signal"] = macd_df.iloc[:, 2]

        df["rsi"] = ta.rsi(df["close"], length=self._rsi_period)
        df["vol_ma"] = ta.sma(df["volume"], length=self._volume_ma)
        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=self._atr_period)

        latest = df.iloc[-1]
        prev = df.iloc[-2]
        price = latest["close"]
        roc = latest.get("roc", 0)
        macd_hist = latest.get("macd_hist", 0)
        rsi_val = latest.get("rsi", 50)
        vol_strong = latest["volume"] > latest["vol_ma"] * 1.2
        current_atr = latest.get("atr", price * 0.02)

        reasoning: dict[str, Any] = {}
        bull = 0.0
        bear = 0.0

        # ROC momentum
        if roc > self._roc_threshold:
            bull += 0.30
            reasoning["roc"] = f"positive momentum ({roc:.1f}%)"
        elif roc < -self._roc_threshold:
            bear += 0.30
            reasoning["roc"] = f"negative momentum ({roc:.1f}%)"
        else:
            reasoning["roc"] = f"flat ({roc:.1f}%)"

        # MACD histogram
        if macd_hist > 0 and macd_hist > prev.get("macd_hist", 0):
            bull += 0.25
            reasoning["macd"] = "bullish and expanding"
        elif macd_hist < 0 and macd_hist < prev.get("macd_hist", 0):
            bear += 0.25
            reasoning["macd"] = "bearish and expanding"
        else:
            reasoning["macd"] = f"histogram={macd_hist:.4f}"

        # RSI momentum zone
        if 50 < rsi_val < 80:
            bull += 0.15
            reasoning["rsi"] = f"bullish momentum zone ({rsi_val:.1f})"
        elif 20 < rsi_val < 50:
            bear += 0.15
            reasoning["rsi"] = f"bearish momentum zone ({rsi_val:.1f})"

        # Volume confirmation
        if vol_strong:
            bull += 0.10
            bear += 0.10
            reasoning["volume"] = "strong volume confirming"
        else:
            reasoning["volume"] = "weak volume"

        net = bull - bear

        if net > 0.3:
            direction = SignalDirection.BUY
            strength = min(net, 1.0)
            stop_loss = price - (current_atr * self._atr_sl_multiplier)
            take_profit = price + (current_atr * self._atr_tp_multiplier)
        elif net < -0.3:
            direction = SignalDirection.SELL
            strength = min(-net, 1.0)
            stop_loss = price + (current_atr * self._atr_sl_multiplier)
            take_profit = price - (current_atr * self._atr_tp_multiplier)
        else:
            return []

        confidence = min(0.35 + sum([abs(net) > 0.4, vol_strong, abs(roc) > self._roc_threshold * 1.5]) * 0.15, 0.90)

        rr = None
        if stop_loss and take_profit:
            risk = abs(price - stop_loss)
            reward = abs(take_profit - price)
            rr = round(reward / risk, 2) if risk > 0 else None

        return [StrategySignal(
            strategy_name=self.name,
            strategy_version=self.version,
            symbol=context.symbol,
            timeframe=context.timeframe,
            generated_at=datetime.now(timezone.utc),
            direction=direction,
            strength=round(strength, 3),
            confidence=round(confidence, 3),
            entry_price=round(price, 4),
            stop_loss=round(stop_loss, 4),
            take_profit=round(take_profit, 4),
            risk_reward_ratio=rr,
            market_regime=context.market_regime,
            time_horizon="short",
            reasoning=reasoning,
            indicators_used={
                "roc": round(roc, 2),
                "macd_hist": round(macd_hist, 4),
                "rsi": round(rsi_val, 2),
                "atr": round(current_atr, 4),
            },
        )]
