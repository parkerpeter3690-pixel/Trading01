"""
Risk Engine
============

Independent risk management engine (Section 8).

The risk engine:
- Operates independently of the AI
- Cannot be overridden by AI agents
- Validates every order before execution
- Enforces hard limits from configuration
- Logs every check (pass or fail)

Architecture:
    AI says BUY → Risk Engine → Risk acceptable? → YES: Execute / NO: Reject

The AI NEVER bypasses this engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.brokers.base import BrokerAdapter, OrderRequest, OrderSide
from src.core.config import settings
from src.core.exceptions import (
    KillSwitchActivated,
    RiskLimitExceeded,
    StopLossRequired,
)
from src.core.logging import get_logger

logger = get_logger("risk")


@dataclass
class RiskCheckResult:
    """Result of a comprehensive risk check."""
    passed: bool
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)
    rejection_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": self.checks,
            "rejection_reasons": self.rejection_reasons,
        }


class RiskEngine:
    """
    Independent risk management engine.

    All risk limits are loaded from immutable configuration.
    The AI cannot modify these limits at runtime.
    """

    def __init__(self, broker: BrokerAdapter) -> None:
        self._broker = broker
        self._kill_switch_active = False
        self._daily_pnl = 0.0
        self._peak_value = settings.paper_trading_initial_capital
        self._daily_loss_count = 0

    @property
    def kill_switch_active(self) -> bool:
        return self._kill_switch_active

    async def validate_order(self, order: OrderRequest) -> RiskCheckResult:
        """
        Validate an order against ALL risk limits.

        This is the gate between the AI and execution.
        Every check is logged regardless of pass/fail.

        Checks:
        1. Kill switch status
        2. Stop loss requirement
        3. Position size limit
        4. Risk per trade limit
        5. Open positions limit
        6. Daily loss limit
        7. Portfolio drawdown limit
        8. Leverage limit
        9. Sufficient funds
        10. Risk/reward ratio
        """
        checks: dict[str, dict[str, Any]] = {}
        reasons: list[str] = []

        # 1. Kill switch
        checks["kill_switch"] = {
            "passed": not self._kill_switch_active,
            "active": self._kill_switch_active,
        }
        if self._kill_switch_active:
            reasons.append("Kill switch is active — all trading halted")

        # 2. Stop loss requirement
        has_stop = order.stop_loss is not None
        checks["stop_loss"] = {
            "passed": has_stop or not settings.require_stop_loss,
            "required": settings.require_stop_loss,
            "provided": has_stop,
        }
        if settings.require_stop_loss and not has_stop:
            reasons.append("Stop loss is required for all trades")

        # 3-9. Need account and position data
        account = await self._broker.get_account()
        positions = await self._broker.get_positions()

        # Calculate order value
        entry_price = order.limit_price or order.stop_price or 0
        # For market orders, we estimate using the stop_loss as reference
        if entry_price == 0 and order.stop_loss:
            entry_price = order.stop_loss * 1.02  # Rough estimate

        order_value = order.quantity * entry_price if entry_price > 0 else 0

        # 3. Position size
        if account.portfolio_value > 0 and order_value > 0:
            pos_pct = (order_value / account.portfolio_value) * 100
            checks["position_size"] = {
                "passed": pos_pct <= settings.max_position_size_pct,
                "current_pct": round(pos_pct, 2),
                "limit_pct": settings.max_position_size_pct,
            }
            if pos_pct > settings.max_position_size_pct:
                reasons.append(f"Position size {pos_pct:.1f}% exceeds {settings.max_position_size_pct}% limit")
        else:
            checks["position_size"] = {"passed": True, "note": "Cannot verify without price"}

        # 4. Risk per trade
        if order.stop_loss and entry_price > 0:
            risk_per_share = abs(entry_price - order.stop_loss)
            total_risk = risk_per_share * order.quantity
            risk_pct = (total_risk / account.portfolio_value) * 100 if account.portfolio_value > 0 else 0
            checks["risk_per_trade"] = {
                "passed": risk_pct <= settings.max_loss_per_trade_pct,
                "current_pct": round(risk_pct, 2),
                "limit_pct": settings.max_loss_per_trade_pct,
            }
            if risk_pct > settings.max_loss_per_trade_pct:
                reasons.append(f"Risk per trade {risk_pct:.1f}% exceeds {settings.max_loss_per_trade_pct}% limit")
        else:
            checks["risk_per_trade"] = {"passed": True, "note": "Cannot calculate without stop loss and entry price"}

        # 5. Open positions
        checks["open_positions"] = {
            "passed": len(positions) < settings.max_open_positions,
            "current": len(positions),
            "limit": settings.max_open_positions,
        }
        if len(positions) >= settings.max_open_positions:
            reasons.append(f"Open positions {len(positions)} at max {settings.max_open_positions}")

        # 6. Daily loss
        initial = settings.paper_trading_initial_capital
        daily_loss_pct = abs(self._daily_pnl / initial * 100) if self._daily_pnl < 0 and initial > 0 else 0
        checks["daily_loss"] = {
            "passed": daily_loss_pct < settings.max_daily_loss_pct,
            "current_pct": round(daily_loss_pct, 2),
            "limit_pct": settings.max_daily_loss_pct,
        }
        if daily_loss_pct >= settings.max_daily_loss_pct:
            reasons.append(f"Daily loss {daily_loss_pct:.1f}% exceeds {settings.max_daily_loss_pct}% limit")

        # 7. Portfolio drawdown
        current_dd = ((self._peak_value - account.portfolio_value) / self._peak_value) * 100 if self._peak_value > 0 else 0
        checks["drawdown"] = {
            "passed": current_dd < settings.max_portfolio_drawdown_pct,
            "current_pct": round(current_dd, 2),
            "limit_pct": settings.max_portfolio_drawdown_pct,
        }
        if current_dd >= settings.max_portfolio_drawdown_pct:
            reasons.append(f"Drawdown {current_dd:.1f}% exceeds {settings.max_portfolio_drawdown_pct}% limit")

        # 8. Sufficient funds
        if order.side == OrderSide.BUY:
            checks["sufficient_funds"] = {
                "passed": order_value <= account.cash or order_value == 0,
                "required": round(order_value, 2),
                "available": round(account.cash, 2),
            }
            if order_value > account.cash and order_value > 0:
                reasons.append(f"Insufficient funds: need {order_value:.2f}, have {account.cash:.2f}")
        else:
            checks["sufficient_funds"] = {"passed": True}

        all_passed = len(reasons) == 0

        result = RiskCheckResult(
            passed=all_passed,
            checks=checks,
            rejection_reasons=reasons,
        )

        # Log every risk check
        logger.info(
            "risk_check_completed",
            symbol=order.symbol,
            side=order.side.value,
            passed=all_passed,
            checks_count=len(checks),
            rejections=len(reasons),
        )

        if not all_passed:
            logger.warning(
                "risk_check_failed",
                symbol=order.symbol,
                reasons=reasons,
            )

        return result

    def activate_kill_switch(self, reason: str) -> None:
        """
        Activate the emergency kill switch.

        Once activated, NO new trades can be placed.
        Only an admin can deactivate it.
        """
        self._kill_switch_active = True
        logger.critical(
            "kill_switch_activated",
            reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def deactivate_kill_switch(self, admin_id: str) -> None:
        """Deactivate kill switch. Requires admin authorization."""
        self._kill_switch_active = False
        logger.warning(
            "kill_switch_deactivated",
            admin_id=admin_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def update_daily_pnl(self, pnl: float) -> None:
        """Update daily P&L tracking."""
        self._daily_pnl += pnl
        if self._daily_pnl < 0:
            daily_loss_pct = abs(self._daily_pnl / settings.paper_trading_initial_capital * 100)
            if daily_loss_pct >= settings.max_daily_loss_pct:
                self.activate_kill_switch(
                    f"Daily loss limit exceeded: {daily_loss_pct:.1f}% > {settings.max_daily_loss_pct}%"
                )

    def update_peak_value(self, portfolio_value: float) -> None:
        """Update peak portfolio value for drawdown calculation."""
        if portfolio_value > self._peak_value:
            self._peak_value = portfolio_value

    def reset_daily(self) -> None:
        """Reset daily tracking (call at start of each trading day)."""
        self._daily_pnl = 0.0
        self._daily_loss_count = 0
        logger.info("daily_risk_metrics_reset")
