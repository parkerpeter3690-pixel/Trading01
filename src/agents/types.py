"""
Agent Graph Type Definitions
============================

Core types and contracts for the Adaptive Agent Graph.
Ensures normalized inputs and outputs for every node in the graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AgentSignal(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class NodeStatus(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    WAITING = "waiting"
    FAILED = "failed"
    DISABLED = "disabled"
    EXPERIMENT = "experiment"


@dataclass
class AgentResult:
    """Standardized output contract for every agent node."""
    agent_id: str
    timestamp: datetime
    signal: AgentSignal
    confidence: float          # 0.0 to 1.0
    reasoning: str
    features: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    token_cost: float = 0.0
    data_sources: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "signal": self.signal.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "features": self.features,
            "latency_ms": self.latency_ms,
            "token_cost": self.token_cost,
            "data_sources": self.data_sources,
        }


@dataclass
class TradeDecision:
    """The final decision produced by the Decision Engine."""
    symbol: str
    action: AgentSignal
    confidence: float
    expected_edge: float
    risk_approved: bool
    position_size: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    contributing_agents: list[str] = field(default_factory=list)
    rejection_reason: str | None = None
    human_approval_required: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action": self.action.value,
            "confidence": self.confidence,
            "expected_edge": self.expected_edge,
            "risk_approved": self.risk_approved,
            "position_size": self.position_size,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "contributing_agents": self.contributing_agents,
            "rejection_reason": self.rejection_reason,
            "human_approval_required": self.human_approval_required,
        }


@dataclass
class AgentNodeConfig:
    """Configuration for a node within the Agent Graph."""
    id: str
    name: str
    type: str  # 'technical', 'flow', 'sentiment', 'risk', 'decision'
    enabled: bool = True
    model: str | None = None
    inputs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    timeout_ms: int = 5000
