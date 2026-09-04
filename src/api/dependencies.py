"""
Shared Dependencies
====================

Provides access to the shared PaperTradingEngine components.

All API routes MUST use these functions instead of creating
their own PaperBroker/FinnhubProvider instances. This ensures
the dashboard reflects actual trading state.

The paper trading engine is initialized during FastAPI lifespan
and stored here as a module-level singleton.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.brokers.paper_broker import PaperBroker
    from src.data.providers.yfinance_provider import YFinanceProvider
    from src.paper_trading.engine import PaperTradingEngine
    from src.risk.engine import RiskEngine
    from src.agents.orchestrator import Orchestrator

# Module-level reference — set by lifespan in main.py
_engine: PaperTradingEngine | None = None


def set_engine(engine: PaperTradingEngine) -> None:
    """Called once during app startup to register the engine."""
    global _engine
    _engine = engine


def get_engine() -> PaperTradingEngine:
    """Get the shared paper trading engine."""
    if _engine is None:
        raise RuntimeError("PaperTradingEngine not initialized — app not started")
    return _engine


def get_broker() -> PaperBroker:
    """Get the shared paper broker (same instance used by the engine)."""
    return get_engine().broker


def get_data_provider() -> YFinanceProvider:
    """Get the shared market data provider."""
    return get_engine()._data_provider


def get_risk_engine() -> RiskEngine:
    """Get the shared risk engine."""
    return get_engine().risk_engine


def get_orchestrator() -> Orchestrator:
    """Get the shared AI orchestrator."""
    return get_engine().orchestrator
