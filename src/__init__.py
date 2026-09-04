"""
Autonomous Agentic Trading System — Source Package
===================================================

This is the root package for the entire trading system.
All modules are organized into logical subsystems:

- core/       : Shared infrastructure (config, database, redis, logging, auth)
- models/     : SQLAlchemy ORM models for all database tables
- api/        : FastAPI REST endpoints and WebSocket handlers
- mcp/        : MCP Trading Server with tool definitions
- data/       : Market data and news providers (adapter pattern)
- brokers/    : Broker adapters (paper, Alpaca, extensible)
- strategies/ : Independent trading strategy implementations
- signals/    : Signal fusion, calibration, and decision protocol
- risk/       : Independent risk engine with kill switch
- agents/     : AI agent layer (market, news, portfolio, execution, orchestrator)
- paper_trading/ : Realistic paper trading simulation engine
- backtesting/   : Event-driven backtesting framework
- workers/       : Background workers for continuous market monitoring
"""

__version__ = "0.1.0"
