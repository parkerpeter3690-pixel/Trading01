"""
AI Orchestrator
================

Central coordinator for the autonomous trading system.
Uses the dynamic AgentGraph to generate decisions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.agents.llm.base import BaseLLMProvider
from src.agents.llm.providers import get_llm_provider
from src.brokers.base import BrokerAdapter, OrderRequest, OrderSide, OrderType
from src.core.config import settings
from src.core.logging import get_logger
from src.data.base import MarketDataProvider
from src.risk.engine import RiskEngine
from src.strategies.base import MarketContext

# New Graph Imports
from src.agents.types import AgentNodeConfig, AgentSignal, TradeDecision
from src.agents.graph import AgentGraph
from src.agents.nodes import TechnicalAgentNode, RiskAgentNode, DecisionAgentNode
from src.agents.ablation import AblationEngine

logger = get_logger("agent")


class Orchestrator:
    """
    Central AI orchestrator coordinating the trading system.

    Flow:
    Market Data → Agent Graph (Technical → Risk → Decision) → Ablation → Broker Execution
    """

    def __init__(
        self,
        strategies: list[Any], # Kept for backward compat signature
        data_provider: MarketDataProvider,
        broker: BrokerAdapter,
        risk_engine: RiskEngine,
        fusion_engine: Any = None,
        llm_provider: BaseLLMProvider | None = None,
    ) -> None:
        self._data_provider = data_provider
        self._broker = broker
        self._risk_engine = risk_engine
        self._llm = llm_provider or get_llm_provider()
        
        # Build the dynamic graph
        tech_config = AgentNodeConfig(id="technical", name="Technical Analysis", type="technical")
        risk_config = AgentNodeConfig(id="risk", name="Risk Check", type="risk", dependencies=["technical"])
        dec_config = AgentNodeConfig(id="decision", name="Final Decision", type="decision", dependencies=["technical", "risk"])
        
        self.graph = AgentGraph(nodes=[
            TechnicalAgentNode(tech_config),
            RiskAgentNode(risk_config),
            DecisionAgentNode(dec_config)
        ])
        self.ablation = AblationEngine(self.graph)

    async def analyze_and_decide(
        self,
        symbol: str,
        timeframe: str = "1d",
    ) -> Any:
        """
        Run the complete graph analysis and decision pipeline for a symbol.
        """
        decision_id = f"dec-{uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        logger.info("orchestrator_start", decision_id=decision_id, symbol=symbol)

        # 1. Fetch market data
        df = await self._data_provider.get_historical_data(
            symbol, timeframe, days=365
        )
        quote = await self._data_provider.get_quote(symbol)

        mkt_context = MarketContext(
            symbol=symbol,
            timeframe=timeframe,
            data=df,
            current_price=quote.last,
        )
        
        graph_context = {
            "market_context": mkt_context,
            "current_price": quote.last,
        }

        # 2. Execute Graph
        results = await self.graph.execute(graph_context)
        
        final_decision: TradeDecision | None = graph_context.get("final_decision")
        
        if not final_decision:
            logger.error("graph_failed_to_produce_decision", symbol=symbol)
            return type("DummyDec", (), {"action": "no_trade", "executed": False, "symbol": symbol, "ablation": {}})()
            
        # Run Ablation Shadow Tests
        ablation_impacts = await self.ablation.evaluate_impact(graph_context, final_decision)

        # Determine action format for backwards compatibility
        action_str = "buy" if final_decision.action == AgentSignal.LONG else "sell" if final_decision.action == AgentSignal.SHORT else "hold"

        # If NEUTRAL/HOLD, record and return
        if final_decision.action == AgentSignal.NEUTRAL:
            logger.info("decision_no_trade", decision_id=decision_id, symbol=symbol)
            return type("DummyDec", (), {"action": "hold", "executed": False, "symbol": symbol, "confidence": final_decision.confidence, "ablation": ablation_impacts})()

        # 3. Calculate position size and build order
        account = await self._broker.get_account()
        quantity = self._calculate_position_size(
            account_equity=account.portfolio_value,
            entry_price=quote.last,
            stop_loss=final_decision.stop_loss,
        )

        order_request = OrderRequest(
            symbol=symbol,
            side=OrderSide.BUY if final_decision.action == AgentSignal.LONG else OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=quantity,
            stop_loss=final_decision.stop_loss,
            take_profit=final_decision.take_profit,
        )

        # Final risk engine validation (Hard checks)
        risk_result = await self._risk_engine.validate_order(order_request)

        # 4. Execute or reject
        executed = False
        order_id = None

        if risk_result.passed:
            if getattr(final_decision, "human_approval_required", False):
                logger.warning(
                    "trade_pending_human_approval",
                    decision_id=decision_id,
                    symbol=symbol,
                    side=action_str,
                    reason="TRADING_ENV=live requires human approval"
                )
                # In production, we'd emit an event and wait. For now, block execution.
            else:
                try:
                    result = await self._broker.place_order(order_request)
                    executed = True
                    order_id = result.client_order_id
                    logger.info(
                        "trade_executed",
                        decision_id=decision_id,
                        order_id=order_id,
                        symbol=symbol,
                        side=action_str,
                    )
                except Exception as e:
                    logger.error("execution_error", error=str(e))
        else:
            logger.warning(
                "trade_rejected_by_risk",
                decision_id=decision_id,
                symbol=symbol,
                reasons=risk_result.rejection_reasons,
            )

        # Return a decision object that the MarketMonitor understands
        class LegacyDecisionRecord:
            def __init__(self):
                self.symbol = symbol
                self.action = action_str
                self.confidence = final_decision.confidence
                self.executed = executed
                self.ablation = ablation_impacts
                
        return LegacyDecisionRecord()

    def _calculate_position_size(
        self,
        account_equity: float,
        entry_price: float,
        stop_loss: float | None,
    ) -> float:
        """Risk-based position sizing."""
        if entry_price <= 0 or account_equity <= 0:
            return 1.0

        if not stop_loss:
            quantity = (account_equity * 0.01) / entry_price
            return max(1.0, round(quantity, 2))

        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share < 0.001:
            risk_per_share = entry_price * 0.02

        max_risk_amount = account_equity * (settings.max_loss_per_trade_pct / 100)
        quantity_by_risk = max_risk_amount / risk_per_share

        max_position_value = account_equity * (settings.max_position_size_pct / 100)
        quantity_by_size = max_position_value / entry_price

        quantity = min(quantity_by_risk, quantity_by_size)
        return max(1.0, round(quantity, 2))

    async def scan_watchlist(
        self,
        symbols: list[str],
        timeframe: str = "1d",
    ) -> list[Any]:
        """Scan a watchlist of symbols and make decisions for each."""
        decisions = []

        for symbol in symbols:
            try:
                decision = await self.analyze_and_decide(symbol, timeframe)
                decisions.append(decision)
            except Exception as e:
                logger.error("scan_error", symbol=symbol, error=str(e))

        actions = {d.action for d in decisions}
        logger.info(
            "watchlist_scan_complete",
            symbols_scanned=len(symbols),
            decisions=len(decisions),
            trades_executed=sum(1 for d in decisions if d.executed),
            actions=list(actions),
        )

        return decisions
