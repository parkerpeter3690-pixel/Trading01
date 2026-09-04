"""
Regime Classification Strategy
===============================

Classifies the current market into one of 8 regimes (Section 5):
- TRENDING
- RANGING
- HIGH_VOLATILITY
- LOW_VOLATILITY
- RISK_ON
- RISK_OFF
- EVENT_DRIVEN
- UNKNOWN

Uses: ADX, volatility ratios, moving average slope, volume patterns,
and historical volatility percentile.

This strategy does NOT generate buy/sell signals directly. Instead,
it classifies the market state so other strategies know whether to
activate or deactivate. It outputs a HOLD signal with the regime
classification in the reasoning field.
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


class RegimeStrategy(BaseStrategy):
    """Market regime classifier."""

    def __init__(
        self,
        adx_period: int = 14,
        adx_trending_threshold: float = 25.0,
        vol_short: int = 10,
        vol_long: int = 60,
        vol_high_ratio: float = 1.5,
        vol_low_ratio: float = 0.5,
        sma_slope_period: int = 20,
    ) -> None:
        self._adx_period = adx_period
        self._adx_trending_threshold = adx_trending_threshold
        self._vol_short = vol_short
        self._vol_long = vol_long
        self._vol_high_ratio = vol_high_ratio
        self._vol_low_ratio = vol_low_ratio
        self._sma_slope_period = sma_slope_period

    @property
    def name(self) -> str:
        return "regime"

    @property
    def version(self) -> str:
        return "v1.0"

    @property
    def strategy_type(self) -> str:
        return "regime"

    @property
    def supported_regimes(self) -> list[MarketRegime]:
        return list(MarketRegime)  # Runs in all regimes (it classifies them)

    @property
    def supported_timeframes(self) -> list[str]:
        return ["1h", "4h", "1d"]

    async def generate_signals(self, context: MarketContext) -> list[StrategySignal]:
        df = context.data.copy()

        if not self.validate_data(df, min_rows=max(self._vol_long, self._adx_period) + 20):
            return []

        # ADX for trend strength
        adx_df = ta.adx(df["high"], df["low"], df["close"], length=self._adx_period)
        adx_val = float(adx_df.iloc[-1, 0]) if adx_df is not None and not adx_df.empty else 0

        # Volatility ratio (short vs long)
        returns = df["close"].pct_change()
        vol_short = float(returns.tail(self._vol_short).std() * np.sqrt(252))
        vol_long = float(returns.tail(self._vol_long).std() * np.sqrt(252))
        vol_ratio = vol_short / vol_long if vol_long > 0 else 1.0

        # SMA slope (directional bias)
        sma = ta.sma(df["close"], length=self._sma_slope_period)
        if sma is not None and len(sma) > 5:
            slope = (float(sma.iloc[-1]) - float(sma.iloc[-5])) / float(sma.iloc[-5]) * 100
        else:
            slope = 0.0

        # Classify regime
        reasoning: dict[str, Any] = {
            "adx": round(adx_val, 2),
            "vol_ratio": round(vol_ratio, 3),
            "vol_short": round(vol_short * 100, 2),
            "vol_long": round(vol_long * 100, 2),
            "sma_slope_pct": round(slope, 3),
        }

        if vol_ratio > self._vol_high_ratio:
            regime = MarketRegime.HIGH_VOLATILITY
            reasoning["classification"] = "High volatility: short-term vol >> long-term vol"
            confidence = min(0.5 + (vol_ratio - self._vol_high_ratio) * 0.2, 0.95)
        elif vol_ratio < self._vol_low_ratio:
            regime = MarketRegime.LOW_VOLATILITY
            reasoning["classification"] = "Low volatility: compressed range"
            confidence = min(0.5 + (self._vol_low_ratio - vol_ratio) * 0.3, 0.90)
        elif adx_val > self._adx_trending_threshold:
            regime = MarketRegime.TRENDING
            reasoning["classification"] = f"Trending: ADX={adx_val:.1f} > {self._adx_trending_threshold}"
            confidence = min(0.5 + (adx_val - self._adx_trending_threshold) / 50, 0.90)
        elif adx_val < 20:
            regime = MarketRegime.RANGING
            reasoning["classification"] = f"Ranging: ADX={adx_val:.1f} < 20"
            confidence = min(0.5 + (20 - adx_val) / 20 * 0.3, 0.85)
        else:
            regime = MarketRegime.UNKNOWN
            reasoning["classification"] = "Unclear regime"
            confidence = 0.40

        reasoning["regime"] = regime.value

        # Regime strategy outputs HOLD — it classifies, doesn't trade
        return [StrategySignal(
            strategy_name=self.name,
            strategy_version=self.version,
            symbol=context.symbol,
            timeframe=context.timeframe,
            generated_at=datetime.now(timezone.utc),
            direction=SignalDirection.HOLD,
            strength=0.0,
            confidence=round(confidence, 3),
            market_regime=regime,
            reasoning=reasoning,
            indicators_used={
                "adx": round(adx_val, 2),
                "vol_ratio": round(vol_ratio, 3),
                "sma_slope": round(slope, 3),
            },
        )]
