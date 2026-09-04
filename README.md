# Autonomous Agentic Trading System

An autonomous AI trading research and execution platform with MCP integration, multi-strategy engine, signal fusion, risk management, paper trading, and adaptive learning.

## 🏗️ Architecture

```
                    ┌──────────────────────────┐
                    │    DASHBOARD (React)      │
                    └────────────┬─────────────┘
                                 │ WebSocket + REST
                    ┌────────────▼─────────────┐
                    │    FastAPI + MCP Server   │
                    └────────────┬─────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
          ▼                      ▼                      ▼
   Market Agent          News Agent           Portfolio Agent
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 ▼
                    ┌──────────────────────────┐
                    │   8 STRATEGY ENGINE       │
                    │   (Independent signals)   │
                    └────────────┬─────────────┘
                                 ▼
                    ┌──────────────────────────┐
                    │   SIGNAL FUSION ENGINE    │
                    │   (Weighted combination)  │
                    └────────────┬─────────────┘
                                 ▼
                    ┌──────────────────────────┐
                    │   RISK ENGINE             │
                    │   (Independent, immutable)│
                    └────────────┬─────────────┘
                                 ▼
                    ┌──────────────────────────┐
                    │   PAPER / LIVE BROKER     │
                    └──────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Docker & Docker Compose
- Node.js 20+ (for dashboard)

### 1. Clone & Configure
```bash
cp .env.example .env
# Edit .env with your API keys (optional for dev)
```

### 2. Start Infrastructure
```bash
docker-compose up -d
```

### 3. Install Dependencies
```bash
pip install -e ".[dev]"
```

### 4. Initialize Database
```bash
python -c "import asyncio; from src.core.database import init_db; asyncio.run(init_db())"
```

### 5. Start API Server
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Start MCP Server (Development)
```bash
uv run mcp dev src/mcp/server.py
```

## 📁 Project Structure

```
src/
├── core/           # Config, database, Redis, logging, auth, exceptions
├── models/         # 16 SQLAlchemy ORM models (20+ database tables)
├── api/            # FastAPI REST + WebSocket endpoints
├── mcp/            # MCP Trading Server with 15+ tools
├── data/           # Market data providers (yfinance, Alpha Vantage, Finnhub)
├── brokers/        # Broker adapters (Paper, Alpaca)
├── strategies/     # 8 independent trading strategies
├── signals/        # Signal fusion engine
├── risk/           # Independent risk engine with kill switch
├── agents/         # AI agents + LLM providers (OpenAI, Gemini, Ollama)
├── paper_trading/  # Realistic paper trading simulation
├── backtesting/    # Event-driven backtesting framework
└── workers/        # Background market monitoring
```

## 🧠 Key Design Principles

1. **AI reasons, code calculates**: LLM handles interpretation and hypothesis generation. Deterministic code handles risk, position sizing, validation, and execution.

2. **No single indicator trades**: The Signal Fusion Engine combines 8 independent strategies. No single signal can trigger a trade.

3. **Risk engine is independent**: The AI CANNOT override risk limits, disable kill switches, or increase leverage.

4. **Everything is auditable**: Every decision stores the full reasoning chain, answering "Why did you take this trade?" and "What did you learn?"

5. **Capital preservation first**: The system is designed to identify when NOT to trade, not to trade constantly.

## 📊 Strategies

| Strategy | Type | Supported Regimes |
|:---|:---|:---|
| Trend Following | EMA crossovers, ADX | Trending |
| Mean Reversion | Bollinger, RSI, Z-score | Ranging, Low Vol |
| Momentum | ROC, MACD, volume | Trending, Risk On |
| Breakout | S/R breaks, vol expansion | Ranging, Low Vol |
| Volatility | ATR, vol regime | High/Low Vol |
| Event Driven | Economic calendar | Event Driven |
| Statistical | Z-score, correlation | All |
| Regime | Market classification | All (classifier) |

## 🔐 Risk Limits (from .env)

| Limit | Default | Description |
|:---|:---|:---|
| MAX_POSITION_SIZE_PCT | 5% | Max portfolio % per position |
| MAX_DAILY_LOSS_PCT | 2% | Max daily loss |
| MAX_PORTFOLIO_DRAWDOWN_PCT | 10% | Max total drawdown |
| MAX_OPEN_POSITIONS | 10 | Concurrent positions |
| REQUIRE_STOP_LOSS | true | Every trade needs a stop |
| MIN_RISK_REWARD_RATIO | 1.5 | Minimum R:R ratio |

## 📄 License

MIT
