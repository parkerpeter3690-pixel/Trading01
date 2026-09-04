"""
Paper Trading CLI
==================

Standalone script to run paper trading outside the API server.

Usage:
    python -m src.paper_trading.start_paper_trading
    python -m src.paper_trading.start_paper_trading --watchlist AAPL,MSFT,TSLA --interval 300
    python -m src.paper_trading.start_paper_trading --capital 50000
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys

from src.core.logging import configure_logging, get_logger
from src.paper_trading.engine import PaperTradingEngine

logger = get_logger("paper_trading")


async def main(
    watchlist: list[str],
    interval: int,
    capital: float,
) -> None:
    """Run the paper trading engine until interrupted."""
    configure_logging()

    engine = PaperTradingEngine(
        watchlist=watchlist,
        scan_interval=interval,
        initial_capital=capital,
    )

    # Handle graceful shutdown
    stop_event = asyncio.Event()

    def _shutdown(sig: signal.Signals) -> None:
        logger.info("shutdown_signal_received", signal=sig.name)
        engine.stop()
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown, sig)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    # Start trading
    engine.start()

    print(f"\n{'='*60}")
    print(f"  Paper Trading Engine Started")
    print(f"  Watchlist:  {', '.join(watchlist)}")
    print(f"  Interval:   {interval}s")
    print(f"  Capital:    ${capital:,.2f}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    try:
        # Keep running until shutdown signal
        await stop_event.wait()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt")
        engine.stop()

    # Print final status
    status = await engine.get_status()
    print(f"\n{'='*60}")
    print(f"  Paper Trading Stopped")
    print(f"  Final Equity: ${status['account']['portfolio_value']:,.2f}")
    print(f"  Total Return: {status['pnl']['total_return']:.2f}%")
    print(f"{'='*60}\n")


def cli() -> None:
    """Parse CLI arguments and run."""
    parser = argparse.ArgumentParser(
        description="Start the autonomous paper trading engine",
    )
    parser.add_argument(
        "--watchlist",
        type=str,
        default="AAPL,MSFT,TSLA,SPY",
        help="Comma-separated symbols to trade (default: AAPL,MSFT,TSLA,SPY)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Seconds between scan cycles (default: 300)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100_000.0,
        help="Initial paper trading capital (default: 100000)",
    )
    args = parser.parse_args()

    watchlist = [s.strip().upper() for s in args.watchlist.split(",")]

    asyncio.run(main(
        watchlist=watchlist,
        interval=args.interval,
        capital=args.capital,
    ))


if __name__ == "__main__":
    cli()
