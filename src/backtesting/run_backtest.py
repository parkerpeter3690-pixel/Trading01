"""
Run Backtest
============

CLI script to run historical simulations and generate tear sheets.
"""

import asyncio
from datetime import datetime, timedelta

from src.backtesting.engine import BacktestEngine
from src.backtesting.analytics import AnalyticsEngine
from src.data.providers.yfinance_provider import YFinanceProvider
from src.signals.fusion import SignalFusionEngine
from src.strategies.trend_following import TrendFollowingStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.momentum import MomentumStrategy
from src.strategies.regime import RegimeStrategy
from src.strategies.breakout import BreakoutStrategy
from src.strategies.volatility import VolatilityStrategy
from src.strategies.event_driven import EventDrivenStrategy
from src.strategies.statistical import StatisticalStrategy


async def main():
    print("Initializing components...")
    
    # 1. Data Provider
    data_provider = YFinanceProvider()
    
    # 2. Strategies
    strategies = [
        TrendFollowingStrategy(),
        MeanReversionStrategy(),
        MomentumStrategy(),
        RegimeStrategy(),
        BreakoutStrategy(),
        VolatilityStrategy(),
        EventDrivenStrategy(),
        StatisticalStrategy(),
    ]
    
    # 3. Fusion Engine
    fusion = SignalFusionEngine()
    
    # 4. Backtest Engine
    engine = BacktestEngine(
        strategies=strategies,
        data_provider=data_provider,
        fusion_engine=fusion,
        initial_capital=100_000.0
    )
    
    # Date range: 1 year ending today
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    symbol = "AAPL"
    print(f"\nRunning backtest for {symbol} from {start_date.date()} to {end_date.date()}...")
    
    # Run simulation
    result = await engine.run(
        symbol=symbol,
        start=start_date,
        end=end_date,
        timeframe="1d"
    )
    
    if "error" in result:
        print(f"Backtest Failed: {result['error']}")
        return
        
    print("\nProcessing Analytics...")
    
    # Generate Tearsheet
    tearsheet = AnalyticsEngine.calculate_tearsheet(
        initial_capital=result["initial_capital"],
        final_equity=result["final_equity"],
        trades=result["trade_history"]
    )
    
    # Print Output
    print("\n" + "="*50)
    print("BACKTEST PERFORMANCE TEAR SHEET")
    print("="*50)
    print(f"Symbol:           {symbol}")
    print(f"Period:           {start_date.date()} to {end_date.date()}")
    print("-" * 50)
    print(f"Initial Capital:  ${tearsheet['initial_capital']:,.2f}")
    print(f"Final Equity:     ${tearsheet['final_equity']:,.2f}")
    print(f"Total Return:     {tearsheet['total_return_pct']}%")
    print("-" * 50)
    print(f"Total Trades:     {tearsheet['total_trades']}")
    print(f"Win Rate:         {tearsheet['win_rate']}%")
    print(f"Profit Factor:    {tearsheet['profit_factor']}")
    print(f"Max Drawdown:     {tearsheet['max_drawdown_pct']}%")
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
