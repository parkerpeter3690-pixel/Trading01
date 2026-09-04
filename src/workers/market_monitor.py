"""
Market Monitor Worker
=====================

Background task that continuously scans the market and triggers
the AI Orchestrator. This is the beating heart of the autonomous
trading system.

The monitor accepts an optional broadcast callback to decouple
it from the WebSocket manager and avoid circular imports.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from src.agents.orchestrator import Orchestrator
from src.core.logging import get_logger

logger = get_logger("worker")

# Type for the broadcast callback
BroadcastFn = Callable[[dict], Awaitable[None]]


class MarketMonitor:
    """
    Automated trading loop.
    """

    def __init__(
        self,
        orchestrator: Orchestrator,
        watchlist: list[str] | None = None,
        interval_seconds: int = 60,
    ) -> None:
        self._orchestrator = orchestrator
        self._watchlist = watchlist or ["AAPL", "MSFT", "TSLA", "SPY"]
        self._interval_seconds = interval_seconds
        self._is_running = False
        self._task: asyncio.Task | None = None
        self._broadcast_fn: BroadcastFn | None = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    def set_broadcast(self, fn: BroadcastFn) -> None:
        """Set the broadcast callback (called from main.py after app init)."""
        self._broadcast_fn = fn

    def start(self) -> None:
        """Start the background worker loop."""
        if self._is_running:
            logger.warning("monitor_already_running")
            return
            
        self._is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("market_monitor_started", watchlist=self._watchlist, interval=self._interval_seconds)

    def stop(self) -> None:
        """Stop the background worker loop."""
        if not self._is_running:
            return
            
        self._is_running = False
        if self._task:
            self._task.cancel()
        logger.info("market_monitor_stopped")

    async def _broadcast(self, msg_type: str, title: str, text: str) -> None:
        """Broadcast status to dashboard via WebSocket (if callback is set)."""
        payload = {
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "type": msg_type,
            "title": title,
            "text": text,
        }

        if self._broadcast_fn:
            try:
                await self._broadcast_fn(payload)
            except Exception as e:
                logger.error("broadcast_error", error=str(e))

    async def _run_loop(self) -> None:
        """The infinite trading loop."""
        await self._broadcast("SYSTEM", "Engine Started", f"Scanning watchlist: {', '.join(self._watchlist)}")
        
        while self._is_running:
            try:
                logger.info("starting_scan_cycle")
                await self._broadcast("ANALYSIS", "Market Scan Started", f"Running strategies on {len(self._watchlist)} symbols...")
                
                decisions = await self._orchestrator.scan_watchlist(self._watchlist)
                
                for dec in decisions:
                    # Broadcast interesting events
                    if dec.action not in ["no_trade", "hold"]:
                        await self._broadcast(
                            "DEBATE", 
                            f"Signal Fusion: {dec.symbol}", 
                            f"Action: {dec.action.upper()}, Confidence: {dec.confidence:.2f}"
                        )
                    
                    # Broadcast ablation impacts if any
                    ablation = getattr(dec, "ablation", {})
                    if ablation:
                        for node, impact in ablation.items():
                            if impact > 0:
                                await self._broadcast(
                                    "ANALYSIS",
                                    f"Ablation Impact ({dec.symbol})",
                                    f"Node '{node}' impact score: {impact:.2f}"
                                )
                        
                    if dec.executed:
                        await self._broadcast(
                            "TRADE", 
                            f"Order Executed: {dec.symbol}", 
                            f"Action: {dec.action.upper()} at MKT. Passed risk checks."
                        )
                        
                logger.info("scan_cycle_complete")
                await self._broadcast("SYSTEM", "Scan Complete", f"Sleeping for {self._interval_seconds}s before next cycle.")
                
                # Sleep until next cycle
                await asyncio.sleep(self._interval_seconds)
                
            except asyncio.CancelledError:
                logger.info("worker_loop_cancelled")
                break
            except Exception as e:
                logger.error("worker_loop_error", error=str(e))
                await self._broadcast("RISK", "Worker Error", f"Exception in trading loop: {str(e)}")
                await asyncio.sleep(5)  # Backoff before retry
