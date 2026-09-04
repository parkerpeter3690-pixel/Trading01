"""
Adaptive Ablation Engine
========================

Tests the mathematical value of individual Agent Nodes by performing
"shadow runs" with nodes temporarily disabled (ablated).

If removing a node changes the final decision, that node has a high
Ablation Impact Score. If the decision remains identical, the node
is contributing zero marginal value and should eventually be pruned.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.agents.graph import AgentGraph
from src.agents.types import AgentSignal, TradeDecision
from src.core.logging import get_logger

logger = get_logger("agent.ablation")


class AblationEngine:
    """Runs shadow evaluations to measure agent impact."""

    def __init__(self, baseline_graph: AgentGraph):
        self.baseline_graph = baseline_graph

    async def evaluate_impact(self, context: dict[str, Any], baseline_decision: TradeDecision) -> dict[str, Any]:
        """
        Temporarily disable each optional node, re-run the graph, 
        and measure the deviation from the baseline decision.
        """
        impact_scores = {}
        
        # Identify nodes that can be ablated (e.g., skip Decision or Risk nodes, only ablate signal generators)
        ablatable_nodes = [
            n_id for n_id, node in self.baseline_graph.nodes.items()
            if node.config.type not in ("decision", "risk")
        ]
        
        for node_id in ablatable_nodes:
            # 1. Disable the node
            original_state = self.baseline_graph.nodes[node_id].config.enabled
            self.baseline_graph.nodes[node_id].config.enabled = False
            
            try:
                # 2. Re-run the graph
                # We need a fresh context so we don't overwrite the original final_decision
                shadow_context = context.copy()
                shadow_context.pop("final_decision", None)
                
                await self.baseline_graph.execute(shadow_context)
                shadow_decision = shadow_context.get("final_decision")
                
                # 3. Calculate impact
                impact = self._calculate_deviation(baseline_decision, shadow_decision)
                impact_scores[node_id] = impact
                
                if impact > 0.0:
                    logger.info(
                        "ablation_impact_detected", 
                        node=node_id, 
                        impact=impact,
                        baseline_action=baseline_decision.action.value,
                        shadow_action=shadow_decision.action.value if shadow_decision else "None"
                    )
                    
            except Exception as e:
                logger.error("ablation_run_failed", node=node_id, error=str(e))
            finally:
                # 4. Restore the node
                self.baseline_graph.nodes[node_id].config.enabled = original_state
                
        return impact_scores

    def _calculate_deviation(self, baseline: TradeDecision, shadow: TradeDecision | None) -> float:
        """
        Calculates the mathematical deviation between two decisions.
        0.0 = Node provided no value (decision is identical without it)
        1.0 = Node completely changed the direction of the trade
        """
        if not shadow:
            return 1.0  # Graph failed to produce a decision without this node!
            
        if baseline.action != shadow.action:
            # The direction flipped! Maximum impact.
            return 1.0
            
        # Direction is the same, check confidence deviation
        conf_diff = abs(baseline.confidence - shadow.confidence)
        
        # Normalize impact: 0 to 0.5 based on confidence shifts
        return min(0.5, conf_diff)
