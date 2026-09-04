# Architecture Documentation

## System Overview

The Autonomous Agentic Trading System is an AI-powered trading research and execution platform built around four core principles:

1. **Separation of Reasoning and Execution**: AI handles interpretation, hypothesis generation, and coordination. Deterministic code handles calculations, risk management, validation, and order execution.

2. **Multi-Strategy Independence**: Eight independent strategies generate signals without knowledge of each other. The Signal Fusion Engine combines them.

3. **Risk Independence**: The Risk Engine operates independently of the AI. Risk limits are immutable at runtime and cannot be overridden by any agent.

4. **Complete Auditability**: Every decision, signal, order, and outcome is stored with full reasoning chains.

---

## Data Flow

```
Market Data Providers (yfinance / Alpha Vantage / Finnhub)
    │
    ▼
┌─────────────────────────────────────────────────┐
│  AI ORCHESTRATOR                                │
│                                                 │
│  1. Fetch market data + news                    │
│  2. Run 8 strategies → generate signals         │
│  3. Classify market regime                      │
│  4. Signal Fusion → weighted combination        │
│  5. 15-question Trading Decision Protocol       │
│  6. Multi-agent debate (Bull/Bear/Tech/Risk)    │
│  7. Generate trade proposal                     │
│                                                 │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  RISK ENGINE (Independent — AI cannot override) │
│                                                 │
│  ✓ Position size limit                          │
│  ✓ Daily loss limit                             │
│  ✓ Portfolio drawdown                           │
│  ✓ Stop loss requirement                        │
│  ✓ Risk/reward ratio                            │
│  ✓ Open positions limit                         │
│  ✓ Leverage limit                               │
│  ✓ Kill switch check                            │
│                                                 │
│  → APPROVE or REJECT                            │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  BROKER ADAPTER (Paper or Live)                 │
│                                                 │
│  Paper: Spread, slippage, commissions, fills    │
│  Live: Alpaca API (US stocks + crypto)          │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │  DATABASE      │
              │  (PostgreSQL)  │
              │                │
              │  Full audit    │
              │  trail stored  │
              └────────────────┘
```

---

## Signal Fusion Architecture

The Signal Fusion Engine prevents any single strategy from forcing a trade.

### Default Weights (adjusted by regime)

| Strategy | Weight | Trending Modifier | Ranging Modifier |
|:---|:---|:---|:---|
| Trend Following | 20% | 1.5x | 0.5x |
| Momentum | 18% | 1.3x | 0.6x |
| Mean Reversion | 15% | 0.5x | 1.5x |
| Breakout | 12% | 0.8x | 1.2x |
| Event Driven | 10% | 1.0x | 1.0x |
| Statistical | 10% | 1.0x | 1.3x |
| Volatility | 8% | 1.0x | 1.0x |
| Regime | 7% | 1.0x | 1.0x |

### Decision Thresholds

- Combined score > +0.30 AND confidence > 0.50 → **BUY**
- Combined score < -0.30 AND confidence > 0.50 → **SELL**
- |Combined score| < 0.10 → **NO TRADE**
- Otherwise → **HOLD**

---

## MCP Tool Architecture

All AI interactions with market data, orders, and portfolio go through the MCP server. The AI never directly accesses broker APIs.

### Tool Categories

| Category | Tools | Description |
|:---|:---|:---|
| Market Data | `get_market_data`, `get_historical_data`, `get_indicators`, `get_volatility` | Price, OHLCV, technical indicators |
| Account | `get_account_balance`, `get_positions`, `get_open_orders` | Portfolio state |
| Risk | `calculate_position_size`, `calculate_risk` | Risk calculations |
| Orders | `place_paper_order`, `cancel_paper_order`, `get_execution_status` | Order management |
| Portfolio | `get_portfolio_exposure`, `get_pnl` | Portfolio analytics |

---

## Database Schema

### Core Tables (20+)

| Table | Purpose |
|:---|:---|
| `market_data` | OHLCV data with computed indicators |
| `news_events` | Financial news with AI impact analysis |
| `economic_events` | Scheduled economic releases |
| `signals` | Strategy signals (individual + fused) |
| `strategies` | Strategy definitions |
| `strategy_versions` | Immutable versioned parameters |
| `trades` | Completed trades with full audit trail |
| `orders` | Order lifecycle tracking |
| `positions` | Current open positions |
| `portfolio_snapshots` | Point-in-time portfolio state |
| `risk_events` | Risk limit breaches, kill switch events |
| `agent_decisions` | AI decisions with 15-question protocol |
| `agent_experiences` | Post-trade learning records |
| `backtests` | Backtest results with metrics |
| `strategy_promotions` | Strategy promotion/demotion audit |
| `system_events` | Application lifecycle events |

---

## Safety Architecture (Section 27)

```
AI Agent
    │
    ▼ (Proposal only)
Risk Engine
    │
    ▼ (Validated)
Permission Layer
    │
    ▼ (Authorized)
Execution
```

The AI CANNOT:
- Change risk limits
- Disable kill switches
- Increase leverage
- Access broker credentials
- Bypass validation
- Promote itself to live trading
- Modify execution permissions
- Delete trading history

---

## LLM Provider Architecture

The system is provider-agnostic via the `BaseLLMProvider` interface:

```python
# Switch provider by changing LLM_PROVIDER env variable
LLM_PROVIDER=ollama     # Free, local
LLM_PROVIDER=openai     # GPT-4o / GPT-4o-mini
LLM_PROVIDER=gemini     # Gemini 2.0 Flash
```

All providers implement:
- `complete()` — Chat completion
- `analyze()` — Single-turn structured analysis
- `health_check()` — Provider availability
- JSON mode for structured output

---

## Strategy Versioning (Section 13)

Every strategy has immutable versioned snapshots:

```
GoldTrend_v1.0 → v1.1 → v1.2 → v2.0 (rejected) → v1.2 restored
```

Each version stores: parameters, training period, validation period, performance metrics, regime performance, and validation status.

## Strategy Promotion (Section 14)

```
Level 0: Backtest
Level 1: Historical Replay
Level 2: Paper Trading
Level 3: Shadow Trading
Level 4: Micro Capital
Level 5: Limited Live
Level 6: Production (requires human approval)
```

Each level has objective promotion criteria. The system recommends PROMOTE, HOLD, DEMOTE, or DISABLE. Live activation requires explicit admin approval.
