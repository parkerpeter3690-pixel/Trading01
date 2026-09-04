import asyncio
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from src.strategies.base import MarketContext, MarketRegime
from src.strategies.momentum import MomentumStrategy
from src.strategies.statistical import StatisticalStrategy
from src.strategies.regime import RegimeStrategy

async def test_strategies():
    # Create fake OHLCV data
    dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
    np.random.seed(42)
    closes = np.cumsum(np.random.normal(0, 1, 100)) + 100
    df = pd.DataFrame({
        "open": closes + np.random.normal(0, 0.5, 100),
        "high": closes + np.abs(np.random.normal(0, 1, 100)),
        "low": closes - np.abs(np.random.normal(0, 1, 100)),
        "close": closes,
        "volume": np.random.randint(1000, 10000, 100)
    }, index=dates)

    # Make last price drop significantly to trigger statistical or momentum
    df.loc[df.index[-1], "close"] = df.loc[df.index[-2], "close"] - 5.0
    
    context = MarketContext(
        symbol="BTC/USD",
        timeframe="1d",
        data=df,
        market_regime=MarketRegime.TRENDING,
        current_price=df.iloc[-1]["close"]
    )

    print("Testing Momentum Strategy...")
    mom_strat = MomentumStrategy()
    mom_signals = await mom_strat.generate_signals(context)
    for sig in mom_signals:
        print(f"Momentum Signal: {sig.direction} (Confidence: {sig.confidence})")
        print(f"Reasoning: {sig.reasoning}")

    print("\nTesting Statistical Strategy...")
    stat_strat = StatisticalStrategy()
    stat_signals = await stat_strat.generate_signals(context)
    for sig in stat_signals:
        print(f"Statistical Signal: {sig.direction} (Confidence: {sig.confidence})")
        print(f"Reasoning: {sig.reasoning}")
        
    print("\nTesting Regime Strategy...")
    regime_strat = RegimeStrategy()
    regime_signals = await regime_strat.generate_signals(context)
    for sig in regime_signals:
        print(f"Regime Signal: {sig.direction} (Confidence: {sig.confidence})")
        print(f"Reasoning: {sig.reasoning}")

if __name__ == "__main__":
    asyncio.run(test_strategies())
