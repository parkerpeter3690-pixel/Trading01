"""
Trend Following Strategy
=========================

Identifies and follows established trends using:
- Moving average crossovers (EMA 20/50/200)
- ADX for trend strength
- Market structure (higher highs, higher lows)
- Breakout confirmation with volume
- Momentum alignment

Supported Regimes: TRENDING
Not recommended: RANGING, HIGH_VOLATILITY

Signal Logic:
- Strong uptrend: EMA 20 > EMA 50 > EMA 200, ADX > 25, bullish structure
- Strong downtrend: EMA 20 < EMA 50 < EMA 200, ADX > 25, bearish structure
- Confirmation: Volume above average on trend moves
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


class TrendFollowingStrategy(BaseStrategy):
    """
    Trend following strategy using multiple moving averages, ADX, and structure.
    """

    def __init__(
        self,
        fast_ema: int = 20,
        medium_ema: int = 50,
        slow_ema: int = 200,
        adx_period: int = 14,
        adx_threshold: float = 25.0,
        volume_ma: int = 20,
        atr_period: int = 14,
        atr_sl_multiplier: float = 2.0,
        atr_tp_multiplier: float = 3.0,
    ) -> None:
        self._fast_ema = fast_ema
        self._medium_ema = medium_ema
        self._slow_ema = slow_ema
        self._adx_period = adx_period
        self._adx_threshold = adx_threshold
        self._volume_ma = volume_ma
        self._atr_period = atr_period
        self._atr_sl_multiplier = atr_sl_multiplier
        self._atr_tp_multiplier = atr_tp_multiplier

    @property
    def name(self) -> str:
        return "trend_following"

    @property
    def version(self) -> str:
        return "v1.0"

    @property
    def strategy_type(self) -> str:
        return "trend"

    @property
    def supported_regimes(self) -> list[MarketRegime]:
        return [MarketRegime.TRENDING, MarketRegime.RISK_ON, MarketRegime.RISK_OFF]

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "fast_ema": self._fast_ema,
            "medium_ema": self._medium_ema,
            "slow_ema": self._slow_ema,
            "adx_period": self._adx_period,
            "adx_threshold": self._adx_threshold,
            "atr_sl_multiplier": self._atr_sl_multiplier,
            "atr_tp_multiplier": self._atr_tp_multiplier,
        }

    async def generate_signals(self, context: MarketContext) -> list[StrategySignal]:
        """Generate trend following signals."""
        df = context.data.copy()

        if not self.validate_data(df, min_rows=self._slow_ema + 20):
            return []

        # Compute indicators
        df["ema_fast"] = ta.ema(df["close"], length=self._fast_ema)
        df["ema_medium"] = ta.ema(df["close"], length=self._medium_ema)
        df["ema_slow"] = ta.ema(df["close"], length=self._slow_ema)

        adx_df = ta.adx(df["high"], df["low"], df["close"], length=self._adx_period)
        if adx_df is not None and not adx_df.empty:
            df["adx"] = adx_df.iloc[:, 0]
            df["dmp"] = adx_df.iloc[:, 1]  # +DI
            df["dmn"] = adx_df.iloc[:, 2]  # -DI
        else:
            return []

        atr = ta.atr(df["high"], df["low"], df["close"], length=self._atr_period)
        df["atr"] = atr

        df["vol_ma"] = ta.sma(df["volume"], length=self._volume_ma)

        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        ema_f = latest["ema_fast"]
        ema_m = latest["ema_medium"]
        ema_s = latest["ema_slow"]
        adx_val = latest["adx"]
        dmp = latest["dmp"]
        dmn = latest["dmn"]
        current_price = latest["close"]
        current_atr = latest["atr"]
        vol_above_avg = latest["volume"] > latest["vol_ma"]

        # Trend alignment scoring
        bullish_score = 0.0
        bearish_score = 0.0
        reasoning: dict[str, Any] = {}

        # EMA alignment
        if ema_f > ema_m > ema_s:
            bullish_score += 0.30
            reasoning["ema_alignment"] = "bullish (fast > medium > slow)"
        elif ema_f < ema_m < ema_s:
            bearish_score += 0.30
            reasoning["ema_alignment"] = "bearish (fast < medium < slow)"
        else:
            reasoning["ema_alignment"] = "mixed"

        # ADX trend strength
        if adx_val > self._adx_threshold:
            trend_bonus = min((adx_val - self._adx_threshold) / 50, 0.25)
            if dmp > dmn:
                bullish_score += 0.20 + trend_bonus
                reasoning["adx"] = f"strong uptrend (ADX={adx_val:.1f}, +DI > -DI)"
            else:
                bearish_score += 0.20 + trend_bonus
                reasoning["adx"] = f"strong downtrend (ADX={adx_val:.1f}, -DI > +DI)"
        else:
            reasoning["adx"] = f"weak trend (ADX={adx_val:.1f} < {self._adx_threshold})"

        # Price relative to EMAs
        if current_price > ema_f > ema_m:
            bullish_score += 0.15
            reasoning["price_position"] = "above fast and medium EMA"
        elif current_price < ema_f < ema_m:
            bearish_score += 0.15
            reasoning["price_position"] = "below fast and medium EMA"

        # Volume confirmation
        if vol_above_avg:
            bullish_score += 0.10
            bearish_score += 0.10
            reasoning["volume"] = "above average (confirming)"
        else:
            reasoning["volume"] = "below average (weak)"

        # EMA crossover (recent)
        if prev["ema_fast"] <= prev["ema_medium"] and ema_f > ema_m:
            bullish_score += 0.15
            reasoning["crossover"] = "bullish EMA crossover"
        elif prev["ema_fast"] >= prev["ema_medium"] and ema_f < ema_m:
            bearish_score += 0.15
            reasoning["crossover"] = "bearish EMA crossover"

        # Determine signal
        net_score = bullish_score - bearish_score

        if net_score > 0.3:
            direction = SignalDirection.BUY
            strength = min(net_score, 1.0)
            stop_loss = current_price - (current_atr * self._atr_sl_multiplier)
            take_profit = current_price + (current_atr * self._atr_tp_multiplier)
        elif net_score < -0.3:
            direction = SignalDirection.SELL
            strength = max(-net_score, -1.0)
            stop_loss = current_price + (current_atr * self._atr_sl_multiplier)
            take_profit = current_price - (current_atr * self._atr_tp_multiplier)
        else:
            direction = SignalDirection.HOLD
            strength = 0.0
            stop_loss = None
            take_profit = None

        # Confidence based on signal alignment
        alignment_count = sum([
            abs(net_score) > 0.3,
            adx_val > self._adx_threshold,
            vol_above_avg,
            abs(bullish_score - bearish_score) > 0.4,
        ])
        confidence = min(0.4 + alignment_count * 0.15, 0.95)

        # Calculate R:R
        rr = None
        if stop_loss and take_profit:
            risk = abs(current_price - stop_loss)
            reward = abs(take_profit - current_price)
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
            entry_price=round(current_price, 4),
            stop_loss=round(stop_loss, 4) if stop_loss else None,
            take_profit=round(take_profit, 4) if take_profit else None,
            risk_reward_ratio=rr,
            market_regime=context.market_regime,
            time_horizon="medium",
            reasoning=reasoning,
            indicators_used={
                "ema_fast": round(ema_f, 4),
                "ema_medium": round(ema_m, 4),
                "ema_slow": round(ema_s, 4),
                "adx": round(adx_val, 2),
                "atr": round(current_atr, 4),
                "bullish_score": round(bullish_score, 3),
                "bearish_score": round(bearish_score, 3),
            },
        )

        return [signal]
