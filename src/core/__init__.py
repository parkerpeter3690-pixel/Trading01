"""
Core Configuration Module
=========================

Centralized, type-safe configuration using Pydantic Settings.
All settings are loaded from environment variables / .env file.

Design Decisions:
- Risk limits are defined here but CANNOT be modified at runtime by AI agents.
- Broker credentials are loaded but never exposed through API/MCP responses.
- LLM provider is pluggable — switch by changing LLM_PROVIDER env var.

Usage:
    from src.core.config import settings
    print(settings.database_url)
"""

from __future__ import annotations

import json
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Application environment."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    GEMINI = "gemini"
    OLLAMA = "ollama"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings have sensible defaults for development.
    Production deployments MUST override security-sensitive values.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────
    app_name: str = "AutonomousTradingAgent"
    app_env: Environment = Environment.DEVELOPMENT
    app_debug: bool = True
    app_log_level: str = "DEBUG"
    app_secret_key: SecretStr = SecretStr("change-me-to-a-random-secret-key-at-least-32-chars")

    # ── API Server ───────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    # ── PostgreSQL ───────────────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "trading_agent"
    postgres_user: str = "trading"
    postgres_password: SecretStr = SecretStr("trading_secret_2024")

    @property
    def database_url(self) -> str:
        """Async PostgreSQL connection URL for SQLAlchemy."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}"
            f":{self.postgres_password.get_secret_value()}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Sync PostgreSQL connection URL for Alembic migrations."""
        return (
            f"postgresql://{self.postgres_user}"
            f":{self.postgres_password.get_secret_value()}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )

    # ── Redis ────────────────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: SecretStr = SecretStr("redis_secret_2024")

    @property
    def redis_url(self) -> str:
        """Redis connection URL."""
        return (
            f"redis://:{self.redis_password.get_secret_value()}"
            f"@{self.redis_host}:{self.redis_port}/0"
        )

    # ── LLM Provider ────────────────────────────────────────────────────
    llm_provider: LLMProvider = LLMProvider.OLLAMA
    llm_model: str = "llama3.1:8b"

    # OpenAI
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 4096

    # Gemini
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-2.0-flash"
    gemini_max_tokens: int = 4096

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # ── Market Data Providers ────────────────────────────────────────────
    alpha_vantage_api_key: SecretStr = SecretStr("")
    finnhub_api_key: SecretStr = SecretStr("")
    polygon_api_key: SecretStr = SecretStr("")

    # ── Broker: Alpaca ───────────────────────────────────────────────────
    alpaca_api_key: SecretStr = SecretStr("")
    alpaca_secret_key: SecretStr = SecretStr("")
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_url: str = "https://data.alpaca.markets"

    # ── Risk Management Limits ───────────────────────────────────────────
    # CRITICAL: These are HARD LIMITS. The AI CANNOT override them.
    # They can only be changed by modifying environment variables
    # and restarting the application.
    max_position_size_pct: float = Field(5.0, description="Max % of portfolio per position")
    max_portfolio_leverage: float = Field(1.0, description="Max leverage (1.0 = no leverage)")
    max_daily_loss_pct: float = Field(2.0, description="Max daily loss as % of portfolio")
    max_portfolio_drawdown_pct: float = Field(10.0, description="Max drawdown as % of peak")
    max_correlated_exposure_pct: float = Field(15.0, description="Max correlated asset exposure")
    max_open_positions: int = Field(10, description="Max concurrent open positions")
    max_loss_per_trade_pct: float = Field(1.0, description="Max loss per individual trade")
    require_stop_loss: bool = Field(True, description="Every trade MUST have a stop loss")
    min_risk_reward_ratio: float = Field(1.5, description="Minimum reward/risk ratio")

    # ── Paper Trading ────────────────────────────────────────────────────
    paper_trading_initial_capital: float = 100_000.0
    paper_trading_commission_pct: float = 0.1
    paper_trading_slippage_pct: float = 0.05
    paper_trading_spread_pct: float = 0.02

    # ── MCP Server ───────────────────────────────────────────────────────
    mcp_server_name: str = "TradingMCPServer"
    mcp_auth_token: SecretStr = SecretStr("change-me-to-a-secure-token")

    # ── Dashboard ────────────────────────────────────────────────────────
    dashboard_port: int = 5173

    # ── Monitoring ───────────────────────────────────────────────────────
    enable_kill_switch: bool = True
    kill_switch_check_interval_sec: int = 30
    heartbeat_interval_sec: int = 60

    # ── Convenience Properties ───────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.app_env == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.app_env == Environment.DEVELOPMENT


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Settings are loaded once and cached for the lifetime of the process.
    To reload, restart the application.
    """
    return Settings()


# Convenience alias
settings = get_settings()
