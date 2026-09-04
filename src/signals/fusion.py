"""
Signal Fusion Engine
=====================

Combines signals from multiple independent strategies into a single
composite trading decision (Section 6).

Design:
- NEVER allows one indicator to automatically generate a trade.
- Weights signals by strategy type and market regime.
- Produces composite score with confidence calibration.
- Outputs: BUY | SELL | HOLD | NO_TRADE

Example (Section 6):
    Technical Signal       +0.72
    Momentum               +0.64
    Volume                 +0.51
    Market Regime          +0.80
    News                   -0.20
    Macro                  +0.30
    Order Flow             +0.62
    ────────────────────────────
    Combined Signal        +0.57

The combined signal includes:
- confidence
- expected return
- expected volatility
- expected drawdown
- risk/reward
- time horizon
- strategy attribution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.strategies.base import MarketRegime, SignalDirection, StrategySignal


@dataclass
class FusedSignal:
    """
    The output of the signal fusion engine.

    This is what the Trading Decision Protocol evaluates
    before proposing a trade.
    """
    symbol: str
    timestamp: datetime

    # Decision
    direction: SignalDirection
    combined_score: float       # -1.0 to +1.0
    confidence: float           # 0.0 to 1.0

    # Component signals
    component_scores: dict[str, float] = field(default_factory=dict)
    agreeing_strategies: list[str] = field(default_factory=list)
    disagreeing_strategies: list[str] = field(default_factory=list)
    neutral_strategies: list[str] = field(default_factory=list)

    # Expected outcomes
    expected_return_pct: float | None = None
    expected_volatility: float | None = None
    risk_reward_ratio: float | None = None
    time_horizon: str | None = None

    # Best trade parameters (from highest-confidence strategy)
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None

    # Market context
    market_regime: MarketRegime | None = None
    regime_confidence: float | None = None

    # Full reasoning
    reasoning: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction.value,
            "combined_score": self.combined_score,
            "confidence": self.confidence,
            "component_scores": self.component_scores,
            "agreeing_strategies": self.agreeing_strategies,
            "disagreeing_strategies": self.disagreeing_strategies,
            "neutral_strategies": self.neutral_strategies,
            "expected_return_pct": self.expected_return_pct,
            "risk_reward_ratio": self.risk_reward_ratio,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "market_regime": self.market_regime.value if self.market_regime else None,
            "reasoning": self.reasoning,
        }


# ── Default Strategy Weights ────────────────────────────────────────────
# Weights can be adjusted by regime (trending favors trend/momentum,
# ranging favors mean_reversion, etc.)

DEFAULT_WEIGHTS: dict[str, float] = {
    "trend_following": 0.20,
    "mean_reversion": 0.15,
    "momentum": 0.18,
    "breakout": 0.12,
    "volatility": 0.08,
    "event_driven": 0.10,
    "statistical": 0.10,
    "regime": 0.07,
}

# Regime-specific weight adjustments
REGIME_WEIGHT_MODIFIERS: dict[str, dict[str, float]] = {
    "trending": {
        "trend_following": 1.5,
        "momentum": 1.3,
        "mean_reversion": 0.5,
        "breakout": 0.8,
    },
    "ranging": {
        "trend_following": 0.5,
        "momentum": 0.6,
        "mean_reversion": 1.5,
        "statistical": 1.3,
        "breakout": 1.2,
    },
    "high_volatility": {
        "volatility": 1.5,
        "mean_reversion": 1.2,
        "trend_following": 0.7,
        "breakout": 0.6,
    },
    "low_volatility": {
        "volatility": 1.3,
        "breakout": 1.4,
        "mean_reversion": 0.8,
    },
}

# Minimum combined score thresholds for action
MIN_SCORE_BUY = 0.05
MIN_SCORE_SELL = -0.05
MIN_CONFIDENCE_TRADE = 0.50


class SignalFusionEngine:
    """
    Combines multiple strategy signals into a single trading decision.

    Key principles:
    1. No single strategy can force a trade.
    2. Weights are adjusted based on current market regime.
    3. Disagreeing strategies reduce confidence.
    4. The combined signal must exceed thresholds to generate BUY/SELL.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        min_score_buy: float = MIN_SCORE_BUY,
        min_score_sell: float = MIN_SCORE_SELL,
        min_confidence: float = MIN_CONFIDENCE_TRADE,
    ) -> None:
        self._base_weights = weights or DEFAULT_WEIGHTS.copy()
        self._min_score_buy = min_score_buy
        self._min_score_sell = min_score_sell
        self._min_confidence = min_confidence

    def fuse(
        self,
        signals: list[StrategySignal],
        market_regime: MarketRegime | None = None,
    ) -> FusedSignal:
        """
        Fuse multiple strategy signals into a composite decision.

        Args:
            signals: List of signals from different strategies
            market_regime: Current market regime for weight adjustment

        Returns:
            FusedSignal with combined score and decision
        """
        if not signals:
            return FusedSignal(
                symbol="",
                timestamp=datetime.now(timezone.utc),
                direction=SignalDirection.NO_TRADE,
                combined_score=0.0,
                confidence=0.0,
                reasoning={"note": "No signals received"},
            )

        symbol = signals[0].symbol

        # Get regime-adjusted weights
        weights = self._get_regime_weights(market_regime)

        # Compute weighted scores
        component_scores: dict[str, float] = {}
        weighted_sum = 0.0
        weight_total = 0.0
        agreeing: list[str] = []
        disagreeing: list[str] = []
        neutral: list[str] = []

        # Track best trade parameters (from highest confidence signal)
        best_signal: StrategySignal | None = None
        best_confidence = 0.0

        for signal in signals:
            strategy = signal.strategy_name
            weight = weights.get(strategy, 0.1)

            # Convert direction to score
            if signal.direction == SignalDirection.BUY:
                score = signal.strength * signal.confidence
            elif signal.direction == SignalDirection.SELL:
                score = -signal.strength * signal.confidence
            else:
                score = 0.0

            component_scores[strategy] = round(score, 4)
            weighted_sum += score * weight
            weight_total += weight

            # Classify agreement
            if signal.direction == SignalDirection.BUY:
                agreeing.append(strategy)
            elif signal.direction == SignalDirection.SELL:
                disagreeing.append(strategy)
            else:
                neutral.append(strategy)

            # Track best signal for trade parameters
            if signal.confidence > best_confidence and signal.direction != SignalDirection.HOLD:
                best_confidence = signal.confidence
                best_signal = signal

        # Normalize combined score
        combined_score = weighted_sum / weight_total if weight_total > 0 else 0.0
        combined_score = max(-1.0, min(1.0, combined_score))

        # Calculate confidence
        # More agreement = higher confidence
        total_strategies = len(signals)
        agreement_ratio = max(len(agreeing), len(disagreeing)) / total_strategies if total_strategies > 0 else 0
        avg_confidence = sum(s.confidence for s in signals) / total_strategies if total_strategies > 0 else 0

        # Reduce confidence if strategies disagree
        if len(agreeing) > 0 and len(disagreeing) > 0:
            conflict_penalty = len(min(agreeing, disagreeing, key=len)) / total_strategies * 0.3
            avg_confidence -= conflict_penalty

        confidence = round(min(agreement_ratio * 0.4 + avg_confidence * 0.6, 0.95), 3)

        # Determine direction
        if combined_score > self._min_score_buy and confidence >= self._min_confidence:
            direction = SignalDirection.BUY
        elif combined_score < self._min_score_sell and confidence >= self._min_confidence:
            direction = SignalDirection.SELL
        elif abs(combined_score) < 0.1:
            direction = SignalDirection.NO_TRADE
        else:
            direction = SignalDirection.HOLD

        # Extract best trade parameters
        entry = best_signal.entry_price if best_signal else None
        sl = best_signal.stop_loss if best_signal else None
        tp = best_signal.take_profit if best_signal else None
        rr = best_signal.risk_reward_ratio if best_signal else None

        # Detect regime from regime strategy if present
        regime_signal = next(
            (s for s in signals if s.strategy_name == "regime"), None
        )
        detected_regime = regime_signal.market_regime if regime_signal else market_regime
        regime_conf = regime_signal.confidence if regime_signal else None

        reasoning = {
            "component_scores": component_scores,
            "weights_used": {k: round(v, 3) for k, v in weights.items()},
            "agreement_ratio": round(agreement_ratio, 3),
            "avg_confidence": round(avg_confidence, 3),
            "decision_logic": (
                f"combined_score={combined_score:.3f}, "
                f"threshold_buy={self._min_score_buy}, "
                f"threshold_sell={self._min_score_sell}, "
                f"confidence={confidence:.3f}, "
                f"min_confidence={self._min_confidence}"
            ),
        }

        return FusedSignal(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            direction=direction,
            combined_score=round(combined_score, 4),
            confidence=confidence,
            component_scores=component_scores,
            agreeing_strategies=agreeing,
            disagreeing_strategies=disagreeing,
            neutral_strategies=neutral,
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            risk_reward_ratio=rr,
            market_regime=detected_regime,
            regime_confidence=regime_conf,
            reasoning=reasoning,
        )

    def _get_regime_weights(
        self, regime: MarketRegime | None
    ) -> dict[str, float]:
        """Get strategy weights adjusted for the current market regime."""
        weights = self._base_weights.copy()

        if regime is None:
            return weights

        modifiers = REGIME_WEIGHT_MODIFIERS.get(regime.value, {})
        for strategy, modifier in modifiers.items():
            if strategy in weights:
                weights[strategy] *= modifier

        # Normalize weights
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights
