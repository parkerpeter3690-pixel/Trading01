"""
FastAPI Application Factory
============================

Main entry point for the REST API server.

Provides:
- REST endpoints for dashboard data
- WebSocket endpoints for real-time updates
- Health checks and system status
- CORS configuration for dashboard access
- Structured error handling
- Lifespan management (startup/shutdown)

Usage:
    uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.core.database import close_db, init_db
from src.core.exceptions import (
    KillSwitchActivated,
    OrderValidationError,
    RiskLimitExceeded,
    TradingSystemError,
)
from src.core.logging import configure_logging, get_logger
from src.core.redis_client import close_redis

logger = get_logger("system")

# ── Paper Trading Engine (module-level singleton) ────────────────────────
# Imported lazily in lifespan() to avoid circular import with market_monitor
paper_engine: Any = None

# ── Lifespan ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application startup and shutdown.

    Startup:
    - Configure structured logging
    - Initialize database connection pool
    - Initialize Redis connection
    - Log system start event

    Shutdown:
    - Close database connections
    - Close Redis connections
    - Log system stop event
    """
    # Startup
    configure_logging()
    logger.info(
        "system_starting",
        app_name=settings.app_name,
        environment=settings.app_env.value,
        api_port=settings.api_port,
    )

    await init_db()
    logger.info("database_connected")

    # Start paper trading engine (lazy import to avoid circular dependency)
    global paper_engine
    from src.paper_trading.engine import PaperTradingEngine
    from src.api.dependencies import set_engine
    paper_engine = PaperTradingEngine(watchlist=["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"])
    set_engine(paper_engine)

    # Wire WebSocket broadcast into the market monitor
    paper_engine._monitor.set_broadcast(ws_manager.broadcast)

    paper_engine.start()
    logger.info("paper_trading_engine_started")

    yield

    # Shutdown
    logger.info("system_stopping")
    if paper_engine and paper_engine.is_running:
        paper_engine.stop()
    await close_db()
    await close_redis()
    logger.info("system_stopped")


# ── App Factory ──────────────────────────────────────────────────────────

app = FastAPI(
    title="Autonomous Trading Agent API",
    description=(
        "REST API for the Autonomous Agentic Trading System. "
        "Provides market data, portfolio management, strategy control, "
        "risk monitoring, and AI agent coordination."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# ── CORS ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Exception Handlers ──────────────────────────────────────────────────

@app.exception_handler(TradingSystemError)
async def trading_error_handler(
    request: Request, exc: TradingSystemError
) -> JSONResponse:
    """Convert trading system exceptions to structured HTTP responses."""
    status_code = 400

    if isinstance(exc, RiskLimitExceeded):
        status_code = 422
    elif isinstance(exc, KillSwitchActivated):
        status_code = 503
    elif isinstance(exc, OrderValidationError):
        status_code = 422

    logger.error(
        "trading_error",
        error_type=exc.__class__.__name__,
        message=exc.message,
        **exc.context,
    )

    return JSONResponse(
        status_code=status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all error handler."""
    logger.error("unhandled_error", error=str(exc), type=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"error_type": "InternalError", "message": "Internal server error"},
    )


# ── Health & Status ──────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check() -> dict[str, Any]:
    """
    Health check endpoint.

    Returns system status including database and Redis connectivity.
    """
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.app_env.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/status", tags=["System"])
async def system_status() -> dict[str, Any]:
    """
    Detailed system status.

    Returns component health, active strategies, and risk status.
    """
    return {
        "status": "operational",
        "environment": settings.app_env.value,
        "kill_switch_enabled": settings.enable_kill_switch,
        "risk_limits": {
            "max_position_size_pct": settings.max_position_size_pct,
            "max_daily_loss_pct": settings.max_daily_loss_pct,
            "max_drawdown_pct": settings.max_portfolio_drawdown_pct,
            "max_open_positions": settings.max_open_positions,
            "require_stop_loss": settings.require_stop_loss,
            "min_risk_reward": settings.min_risk_reward_ratio,
        },
        "llm_provider": settings.llm_provider.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/system/kill", tags=["System"])
async def trigger_kill_switch() -> dict[str, Any]:
    """
    Emergency Kill Switch.
    Halts trading engine immediately and cancels all pending orders.
    """
    settings.enable_kill_switch = True
    
    if paper_engine and paper_engine.is_running:
        paper_engine.stop()
        
    logger.critical("KILL_SWITCH_ACTIVATED", source="api")
    return {"status": "halted", "message": "Global Kill Switch activated."}


# ── WebSocket for Real-Time Updates ─────────────────────────────────────

class ConnectionManager:
    """Manages WebSocket connections for real-time dashboard updates."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("websocket_connected", total=len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)
        logger.info("websocket_disconnected", total=len(self.active_connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast a message to all connected clients."""
        disconnected: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.active_connections.remove(conn)


ws_manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time dashboard updates.

    Streams:
    - Price updates
    - New trades and orders
    - Agent decisions
    - Risk events
    - Kill switch status
    - News alerts
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; server pushes updates via broadcast
            data = await websocket.receive_text()
            # Client can send subscription preferences
            logger.debug("ws_message_received", data=data)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ── API Routes ───────────────────────────────────────────────────────────
# Import and register route modules

from src.api.routes import market, portfolio, strategies, trading

app.include_router(market.router, prefix="/api/v1/market", tags=["Market Data"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["Portfolio"])
app.include_router(strategies.router, prefix="/api/v1/strategies", tags=["Strategies"])
app.include_router(trading.router, prefix="/api/v1/trading", tags=["Trading"])


# ── Paper Trading Status ─────────────────────────────────────────────────

@app.get("/api/v1/paper-trading/status", tags=["Paper Trading"])
async def paper_trading_status() -> dict:
    """Get the current paper trading engine status."""
    if paper_engine is None:
        raise HTTPException(status_code=503, detail="Paper trading engine not initialized")
    return await paper_engine.get_status()


@app.post("/api/v1/paper-trading/stop", tags=["Paper Trading"])
async def stop_paper_trading() -> dict:
    """Stop the paper trading engine."""
    if paper_engine is None or not paper_engine.is_running:
        raise HTTPException(status_code=400, detail="Paper trading is not running")
    paper_engine.stop()
    return {"status": "stopped"}


@app.post("/api/v1/paper-trading/start", tags=["Paper Trading"])
async def start_paper_trading() -> dict:
    """Start the paper trading engine."""
    if paper_engine is None:
        raise HTTPException(status_code=503, detail="Paper trading engine not initialized")
    if paper_engine.is_running:
        raise HTTPException(status_code=400, detail="Paper trading is already running")
    paper_engine.start()
    return {"status": "started"}
