"""
MCP Trading Server Package
============================

Model Context Protocol server exposing trading tools.

Architecture:
- Every tool has strict input validation via Pydantic schemas
- Authentication via token-based auth
- Rate limiting per tool
- Logging of every tool invocation
- Risk gate middleware prevents unsafe orders
- The LLM NEVER directly accesses broker APIs (Section 27)

Tool Categories:
- Market Data: get_market_data, get_historical_data, get_indicators, etc.
- News: get_latest_news, analyze_news_impact, etc.
- Account: get_account_balance, get_positions, etc.
- Orders: place_paper_order, cancel_paper_order, etc.
- Risk: calculate_position_size, calculate_risk, etc.
- Portfolio: get_portfolio_exposure, get_drawdown, etc.
"""
