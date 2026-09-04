"""
Standard Agent Nodes
====================

Implementations of the core trading nodes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.agents.graph import BaseAgentNode
from src.agents.types import AgentResult, AgentSignal, TradeDecision
from src.core.logging import get_logger
from src.signals.fusion import SignalFusionEngine
from src.strategies.base import MarketContext
from src.strategies.trend_following import TrendFollowingStrategy
from src.strategies.momentum import MomentumStrategy
from src.strategies.mean_reversion import MeanReversionStrategy

logger = get_logger("agent.nodes")


class TechnicalAgentNode(BaseAgentNode):
    """
    Evaluates price action using classic technical strategies.
    (Replaces the old linear strategy execution loop).
    """

    def __init__(self, config):
        super().__init__(config)
        self.strategies = [
            TrendFollowingStrategy(),
            MomentumStrategy(),
            MeanReversionStrategy(),
        ]
        self.fusion = SignalFusionEngine()

    async def execute(self, context: dict[str, Any], upstream: dict[str, AgentResult]) -> AgentResult:
        # Context contains MarketContext
        mkt_context: MarketContext = context["market_context"]
        
        all_signals = []
        for strategy in self.strategies:
            try:
                signals = await strategy.generate_signals(mkt_context)
                all_signals.extend(signals)
            except Exception as e:
                logger.error("technical_strategy_error", strategy=strategy.name, error=str(e))
                
        fused = self.fusion.fuse(all_signals)
        
        signal_val = AgentSignal.NEUTRAL
        if fused.direction.value == "buy":
            signal_val = AgentSignal.LONG
        elif fused.direction.value == "sell":
            signal_val = AgentSignal.SHORT
            
        return AgentResult(
            agent_id=self.config.id,
            timestamp=datetime.now(timezone.utc),
            signal=signal_val,
            confidence=fused.confidence,
            reasoning=f"Combined score: {fused.combined_score:.2f}. Agreeing: {len(fused.agreeing_strategies)}.",
            features={"agreeing": fused.agreeing_strategies, "score": fused.combined_score},
            data_sources=["historical_ohlcv"]
        )


class RiskAgentNode(BaseAgentNode):
    """
    Evaluates proposed trades against risk limits.
    """
    async def execute(self, context: dict[str, Any], upstream: dict[str, AgentResult]) -> AgentResult:
        # Check all upstream agents
        # For simplicity, if Technical says LONG, Risk approves if confidence > 0.5
        tech_result = upstream.get("technical")
        
        if not tech_result or tech_result.signal == AgentSignal.NEUTRAL:
            return AgentResult(
                agent_id=self.config.id,
                timestamp=datetime.now(timezone.utc),
                signal=AgentSignal.NEUTRAL,
                confidence=1.0,
                reasoning="No directional trade proposed by upstream."
            )
            
        # In a real scenario, this would consult RiskEngine and Broker for margin limits.
        return AgentResult(
            agent_id=self.config.id,
            timestamp=datetime.now(timezone.utc),
            signal=tech_result.signal,
            confidence=0.9,
            reasoning="Risk limits acceptable. Volatility within bounds."
        )


class DecisionAgentNode(BaseAgentNode):
    """
    Final node that aggregates upstream agents into a TradeDecision.
    """
    async def execute(self, context: dict[str, Any], upstream: dict[str, AgentResult]) -> AgentResult:
        # This node actually builds the final TradeDecision object and stores it in the context,
        # but must return an AgentResult to satisfy the graph contract.
        
        tech = upstream.get("technical")
        risk = upstream.get("risk")
        
        if not tech or not risk:
            raise ValueError("Decision agent missing required upstream dependencies.")
            
        approved = risk.signal == tech.signal and tech.signal != AgentSignal.NEUTRAL
        
        current_price = context["current_price"]
        sl = None
        tp = None
        if approved:
            if tech.signal == AgentSignal.LONG:
                sl = current_price * 0.95
                tp = current_price * 1.10
            elif tech.signal == AgentSignal.SHORT:
                sl = current_price * 1.05
                tp = current_price * 0.90
        
        from src.core.config import settings
        requires_human = getattr(settings, 'app_env', 'development') == 'production' or getattr(settings, 'app_env', 'development').value == 'production'
        
        decision = TradeDecision(
            symbol=context["market_context"].symbol,
            action=tech.signal if approved else AgentSignal.NEUTRAL,
            confidence=tech.confidence,
            expected_edge=tech.confidence * 1.5, # Dummy calc
            risk_approved=approved,
            stop_loss=sl,
            take_profit=tp,
            contributing_agents=["technical", "risk"],
            human_approval_required=requires_human
        )
        
        # Stash the final decision into context so Orchestrator can pull it
        context["final_decision"] = decision
        
        return AgentResult(
            agent_id=self.config.id,
            timestamp=datetime.now(timezone.utc),
            signal=decision.action,
            confidence=decision.confidence,
            reasoning=f"Decision finalized: {decision.action.value} (Risk Approved: {approved})"
        )
