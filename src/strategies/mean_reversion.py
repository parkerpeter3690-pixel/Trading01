"""
Mean Reversion Strategy
========================

Identifies overbought/oversold conditions for counter-trend trades using:
- Bollinger Bands (2σ)
- Z-score of price relative to moving average
- RSI extremes
- VWAP deviation
- Statistical distance from mean

Supported Regimes: RANGING, LOW_VOLATILITY
Not recommended: TRENDING, HIGH_VOLATILITY

Signal Logic:
- Oversold: Price below lower BB, RSI < 30, negative Z-score > 2
- Overbought: Price above upper BB, RSI > 70, positive Z-score > 2
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import pandas_ta as ta

from src.strategies.base import (
    BaseStrategy,
    MarketContext,
    MarketRegime,
    SignalDirection,
    StrategySignal,
)


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy using Bollinger Bands, RSI, and Z-score."""

    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        zscore_period: int = 20,
        zscore_threshold: float = 2.0,
        atr_period: int = 14,
        atr_sl_multiplier: float = 1.5,
    ) -> None:
        self._bb_period = bb_period
        self._bb_std = bb_std
        self._rsi_period = rsi_period
        self._rsi_oversold = rsi_oversold
        self._rsi_overbought = rsi_overbought
        self._zscore_period = zscore_period
        self._zscore_threshold = zscore_threshold
        self._atr_period = atr_period
        self._atr_sl_multiplier = atr_sl_multiplier

    @property
    def name(self) -> str:
        return "mean_reversion"

    @property
    def version(self) -> str:
        return "v1.0"

    @property
    def strategy_type(self) -> str:
        return "mean_reversion"

    @property
    def supported_regimes(self) -> list[MarketRegime]:
        return [MarketRegime.RANGING, MarketRegime.LOW_VOLATILITY]

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "bb_period": self._bb_period,
            "bb_std": self._bb_std,
            "rsi_period": self._rsi_period,
            "rsi_oversold": self._rsi_oversold,
            "rsi_overbought": self._rsi_overbought,
            "zscore_period": self._zscore_period,
            "zscore_threshold": self._zscore_threshold,
        }

    async def generate_signals(self, context: MarketContext) -> list[StrategySignal]:
        """Generate mean reversion signals."""
        df = context.data.copy()

        if not self.validate_data(df, min_rows=self._bb_period + 30):
            return []

        # Compute indicators
        bb = ta.bbands(df["close"], length=self._bb_period, std=self._bb_std)
        if bb is None or bb.empty:
            return []

        df["bb_lower"] = bb.iloc[:, 0]
        df["bb_mid"] = bb.iloc[:, 1]
        df["bb_upper"] = bb.iloc[:, 2]

        rsi = ta.rsi(df["close"], length=self._rsi_period)
        df["rsi"] = rsi

        # Z-score
        sma = ta.sma(df["close"], length=self._zscore_period)
        std = df["close"].rolling(self._zscore_period).std()
        df["zscore"] = (df["close"] - sma) / std

        # ATR for stops
        atr = ta.atr(df["high"], df["low"], df["close"], length=self._atr_period)
        df["atr"] = atr

        latest = df.iloc[-1]
        price = latest["close"]
        rsi_val = latest["rsi"]
        zscore = latest["zscore"]
        bb_lower = latest["bb_lower"]
        bb_upper = latest["bb_upper"]
        bb_mid = latest["bb_mid"]
        current_atr = latest["atr"]

        reasoning: dict[str, Any] = {}
        buy_score = 0.0
        sell_score = 0.0

        # Bollinger Band position
        if price <= bb_lower:
            buy_score += 0.30
            reasoning["bollinger"] = "price at/below lower band (oversold)"
        elif price >= bb_upper:
            sell_score += 0.30
            reasoning["bollinger"] = "price at/above upper band (overbought)"
        else:
            bb_pos = (price - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
            reasoning["bollinger"] = f"price at {bb_pos:.0%} of bands"

        # RSI
        if rsi_val < self._rsi_oversold:
            buy_score += 0.25
            reasoning["rsi"] = f"oversold ({rsi_val:.1f} < {self._rsi_oversold})"
        elif rsi_val > self._rsi_overbought:
            sell_score += 0.25
            reasoning["rsi"] = f"overbought ({rsi_val:.1f} > {self._rsi_overbought})"
        else:
            reasoning["rsi"] = f"neutral ({rsi_val:.1f})"

        # Z-score
        if zscore < -self._zscore_threshold:
            buy_score += 0.25
            reasoning["zscore"] = f"extreme negative ({zscore:.2f})"
        elif zscore > self._zscore_threshold:
            sell_score += 0.25
            reasoning["zscore"] = f"extreme positive ({zscore:.2f})"
        else:
            reasoning["zscore"] = f"normal ({zscore:.2f})"

        # Distance from mean
        dist_from_mean = (price - bb_mid) / bb_mid * 100
        if abs(dist_from_mean) > 2:
            if dist_from_mean < 0:
                buy_score += 0.10
            else:
                sell_score += 0.10
            reasoning["mean_distance"] = f"{dist_from_mean:+.1f}% from mean"

        # Determine direction
        net = buy_score - sell_score

        if net > 0.3:
            direction = SignalDirection.BUY
            strength = min(net, 1.0)
            stop_loss = price - (current_atr * self._atr_sl_multiplier)
            take_profit = bb_mid  # Target mean reversion to middle
        elif net < -0.3:
            direction = SignalDirection.SELL
            strength = min(-net, 1.0)
            stop_loss = price + (current_atr * self._atr_sl_multiplier)
            take_profit = bb_mid
        else:
            return []  # No signal

        # Confidence
        signals_count = sum([
            abs(net) > 0.3,
            rsi_val < self._rsi_oversold or rsi_val > self._rsi_overbought,
            abs(zscore) > self._zscore_threshold,
        ])
        confidence = min(0.35 + signals_count * 0.2, 0.90)

        rr = None
        if stop_loss and take_profit:
            risk = abs(price - stop_loss)
            reward = abs(take_profit - price)
            rr = round(reward / risk, 2) if risk > 0 else None

        signal = StrategySignal(
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
                "rsi": round(rsi_val, 2),
                "zscore": round(zscore, 3),
                "bb_lower": round(bb_lower, 4),
                "bb_mid": round(bb_mid, 4),
                "bb_upper": round(bb_upper, 4),
                "atr": round(current_atr, 4),
            },
        )

        return [signal]
