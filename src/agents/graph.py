"""
Agent Graph Executor
====================

Executes the dynamic DAG of trading agents.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

from src.agents.types import AgentNodeConfig, AgentResult, TradeDecision, AgentSignal
from src.core.logging import get_logger

logger = get_logger("agent.graph")


class BaseAgentNode(ABC):
    """Base class for all nodes in the Agent Graph."""

    def __init__(self, config: AgentNodeConfig):
        self.config = config

    @abstractmethod
    async def execute(self, context: dict[str, Any], upstream_results: dict[str, AgentResult]) -> AgentResult:
        """Execute the agent logic."""
        pass


class AgentGraph:
    """
    Executes a directed acyclic graph of agent nodes.
    Nodes can depend on the outputs of other nodes.
    """

    def __init__(self, nodes: list[BaseAgentNode], version: str = "1.0"):
        self.nodes = {node.config.id: node for node in nodes}
        self.version = version
        self._validate_dag()

    def _validate_dag(self):
        """Ensure there are no cycles and dependencies exist."""
        # A simple validation could be added here.
        for node_id, node in self.nodes.items():
            for dep in node.config.dependencies:
                if dep not in self.nodes:
                    raise ValueError(f"Node {node_id} depends on missing node {dep}")

    async def execute(self, context: dict[str, Any]) -> dict[str, AgentResult]:
        """
        Execute the graph concurrently where possible, respecting dependencies.
        Returns the output of all nodes.
        """
        results: dict[str, AgentResult] = {}
        pending = set(self.nodes.keys())
        running_tasks = {}

        logger.info("graph_execution_started", version=self.version, nodes_count=len(self.nodes))

        while pending or running_tasks:
            # Find nodes ready to run (all dependencies met)
            ready_to_run = []
            for node_id in list(pending):
                node = self.nodes[node_id]
                deps_met = all(dep in results for dep in node.config.dependencies)
                if deps_met and node.config.enabled:
                    ready_to_run.append(node_id)
                elif not node.config.enabled:
                    pending.remove(node_id)

            # Start ready tasks
            for node_id in ready_to_run:
                pending.remove(node_id)
                node = self.nodes[node_id]
                
                # Provide only the requested inputs/dependencies to the node
                upstream = {dep: results[dep] for dep in node.config.dependencies if dep in results}
                
                task = asyncio.create_task(self._safe_execute_node(node, context, upstream))
                running_tasks[node_id] = task

            if not running_tasks:
                if pending:
                    logger.error("graph_deadlock", pending=list(pending))
                break

            # Wait for at least one task to finish
            done, _ = await asyncio.wait(
                running_tasks.values(), return_when=asyncio.FIRST_COMPLETED
            )

            # Process completed tasks
            for node_id, task in list(running_tasks.items()):
                if task in done:
                    del running_tasks[node_id]
                    try:
                        result = task.result()
                        results[node_id] = result
                    except Exception as e:
                        logger.error("node_execution_failed", node=node_id, error=str(e))
                        # If a node fails, we might still continue, depending on graph strictness.

        logger.info("graph_execution_completed", completed_nodes=len(results))
        return results

    async def _safe_execute_node(
        self, node: BaseAgentNode, context: dict[str, Any], upstream: dict[str, AgentResult]
    ) -> AgentResult:
        start_time = time.perf_counter()
        try:
            # Enforce timeout
            result = await asyncio.wait_for(
                node.execute(context, upstream), 
                timeout=node.config.timeout_ms / 1000.0
            )
            result.latency_ms = (time.perf_counter() - start_time) * 1000
            return result
        except asyncio.TimeoutError:
            logger.warning("node_timeout", node=node.config.id, timeout_ms=node.config.timeout_ms)
            raise
