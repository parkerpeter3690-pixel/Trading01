"""
Database Models Package
=======================

All SQLAlchemy ORM models for the trading system.

Table Reference:
- MarketData        : OHLCV market data snapshots
- NewsEvent         : Financial news with impact analysis
- EconomicEvent     : Scheduled economic releases (CPI, GDP, etc.)
- Signal            : Individual strategy signals
- Strategy          : Strategy definitions
- StrategyVersion   : Versioned strategy parameters
- Trade             : Completed trades (paper + live)
- Order             : Order lifecycle tracking
- Position          : Current open positions
- PortfolioSnapshot : Point-in-time portfolio state
- RiskEvent         : Risk limit breaches, kill switch activations
- AgentDecision     : Every AI decision with full reasoning
- AgentExperience   : Post-trade learning records
- Backtest          : Backtest run results
- StrategyPromotion : Strategy promotion/demotion audit trail
- SystemEvent       : Application lifecycle events
"""

from src.models.market_data import MarketData
from src.models.news import EconomicEvent, NewsEvent
from src.models.signals import Signal
from src.models.strategies import Strategy, StrategyVersion
from src.models.trades import Trade
from src.models.orders import Order
from src.models.positions import Position
from src.models.portfolio import PortfolioSnapshot
from src.models.risk_events import RiskEvent
from src.models.agent_decisions import AgentDecision
from src.models.experiences import AgentExperience
from src.models.system_events import Backtest, StrategyPromotion, SystemEvent

__all__ = [
    "MarketData",
    "NewsEvent",
    "EconomicEvent",
    "Signal",
    "Strategy",
    "StrategyVersion",
    "Trade",
    "Order",
    "Position",
    "PortfolioSnapshot",
    "RiskEvent",
    "AgentDecision",
    "AgentExperience",
    "Backtest",
    "StrategyPromotion",
    "SystemEvent",
]
