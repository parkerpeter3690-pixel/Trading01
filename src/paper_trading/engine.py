"""
Paper Trading Engine
=====================

Factory that wires together all components needed for autonomous
paper trading and provides lifecycle management.

Components assembled:
- FinnhubProvider (market data)
- All 8 trading strategies
- PaperBroker (with data provider for real prices)
- RiskEngine (independent, immutable limits)
- SignalFusionEngine (weighted multi-strategy fusion)
- Orchestrator (AI coordination + LLM debate)
- MarketMonitor (background trading loop)

Usage:
    engine = PaperTradingEngine(watchlist=["AAPL", "MSFT"])
    engine.start()
    # ... trading runs autonomously ...
    engine.stop()
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from src.agents.orchestrator import Orchestrator
from src.brokers.paper_broker import PaperBroker
from src.core.config import settings
from src.core.logging import get_logger
from src.data.providers.yfinance_provider import YFinanceProvider
from src.risk.engine import RiskEngine
from src.signals.fusion import SignalFusionEngine
from src.strategies import get_all_strategies
from src.workers.market_monitor import MarketMonitor

logger = get_logger("paper_trading")


class PaperTradingEngine:
    """
    One-line factory to launch autonomous paper trading.

    Wires together all system components and manages the
    background trading loop lifecycle.
    """

    def __init__(
        self,
        watchlist: list[str] | None = None,
        scan_interval: int = 300,
        initial_capital: float | None = None,
    ) -> None:
        self._watchlist = watchlist or ["AAPL", "MSFT", "TSLA", "SPY"]
        self._scan_interval = scan_interval
        self._initial_capital = initial_capital or settings.paper_trading_initial_capital

        # ── Assemble components ──────────────────────────────────
        # 1. Market data provider
        self._data_provider = YFinanceProvider()

        # 2. Paper broker with real price lookups
        self._broker = PaperBroker(
            initial_capital=self._initial_capital,
            data_provider=self._data_provider,
        )

        # 3. Risk engine (independent — AI cannot override)
        self._risk_engine = RiskEngine(self._broker)

        # 4. Signal fusion engine
        self._fusion_engine = SignalFusionEngine()

        # 5. All strategies
        self._strategies = get_all_strategies()

        # 6. AI Orchestrator
        self._orchestrator = Orchestrator(
            strategies=self._strategies,
            data_provider=self._data_provider,
            broker=self._broker,
            risk_engine=self._risk_engine,
            fusion_engine=self._fusion_engine,
        )

        # 7. Market monitor (background loop)
        self._monitor = MarketMonitor(
            orchestrator=self._orchestrator,
            watchlist=self._watchlist,
            interval_seconds=self._scan_interval,
        )

        self._started_at: datetime | None = None

        logger.info(
            "paper_trading_engine_initialized",
            watchlist=self._watchlist,
            scan_interval=self._scan_interval,
            initial_capital=self._initial_capital,
            strategies=[s.name for s in self._strategies],
        )

    # ── Lifecycle ────────────────────────────────────────────────

    def start(self) -> None:
        """Start the autonomous paper trading loop."""
        if self._monitor.is_running:
            logger.warning("paper_trading_already_running")
            return

        self._started_at = datetime.now(timezone.utc)
        self._monitor.start()

        logger.info(
            "paper_trading_started",
            watchlist=self._watchlist,
            interval=self._scan_interval,
            capital=self._initial_capital,
        )

    def stop(self) -> None:
        """Stop the paper trading loop and log final state."""
        if not self._monitor.is_running:
            logger.warning("paper_trading_not_running")
            return

        self._monitor.stop()
        logger.info(
            "paper_trading_stopped",
            ran_since=self._started_at.isoformat() if self._started_at else None,
        )

    @property
    def is_running(self) -> bool:
        return self._monitor.is_running

    # ── Status ──────────────────────────────────────────────────

    async def get_status(self) -> dict[str, Any]:
        """Get current engine status for API / dashboard."""
        account = await self._broker.get_account()
        positions = await self._broker.get_positions()
        open_orders = await self._broker.get_open_orders()

        return {
            "running": self.is_running,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "watchlist": self._watchlist,
            "scan_interval_sec": self._scan_interval,
            "account": account.to_dict(),
            "positions": [p.to_dict() for p in positions],
            "open_orders": len(open_orders),
            "strategies_active": [s.name for s in self._strategies],
            "kill_switch_active": self._risk_engine.kill_switch_active,
            "pnl": {
                "initial_capital": self._initial_capital,
                "current_equity": account.portfolio_value,
                "total_return": round(
                    (account.portfolio_value - self._initial_capital)
                    / self._initial_capital
                    * 100,
                    2,
                ),
            },
        }

    # ── Component access (for API routes) ────────────────────────

    @property
    def broker(self) -> PaperBroker:
        return self._broker

    @property
    def risk_engine(self) -> RiskEngine:
        return self._risk_engine

    @property
    def orchestrator(self) -> Orchestrator:
        return self._orchestrator
