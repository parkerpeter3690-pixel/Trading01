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

async def test_params(tf_adx, tf_ema_f, fusion_min_score, symbol="AAPL"):
    data_provider = YFinanceProvider()
    
    strategies = [
        TrendFollowingStrategy(fast_ema=tf_ema_f, adx_threshold=tf_adx, atr_sl_multiplier=1.5, atr_tp_multiplier=3.0),
        MeanReversionStrategy(rsi_oversold=35, rsi_overbought=65, bb_std=1.8),
        MomentumStrategy(),
        RegimeStrategy(),
        BreakoutStrategy(),
        VolatilityStrategy(),
        EventDrivenStrategy(),
        StatisticalStrategy(),
    ]
    
    fusion = SignalFusionEngine(min_score_buy=fusion_min_score, min_score_sell=-fusion_min_score)
    engine = BacktestEngine(strategies=strategies, data_provider=data_provider, fusion_engine=fusion, initial_capital=100_000.0)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    result = await engine.run(symbol=symbol, start=start_date, end=end_date, timeframe="1d")
    
    if "error" in result:
        return -1
        
    tearsheet = AnalyticsEngine.calculate_tearsheet(
        initial_capital=result["initial_capital"],
        final_equity=result["final_equity"],
        trades=result["trade_history"]
    )
    return tearsheet

async def main():
    symbols = ["NVDA", "BTC-USD"]
    for symbol in symbols:
        print(f"\n--- Optimizing for {symbol} ---")
        best_return = -100
        best_params = None
        
        for adx in [15, 25]:
            for ema_f in [10, 20]:
                for fusion_min in [0.20, 0.40]:
                    print(f"Testing ADX={adx}, EMA_F={ema_f}, FUSION_MIN={fusion_min}...")
                    try:
                        ts = await test_params(adx, ema_f, fusion_min, symbol)
                        ret = ts['total_return_pct']
                        print(f"Return: {ret}% (Trades: {ts['total_trades']})")
                        if ret > best_return:
                            best_return = ret
                            best_params = (adx, ema_f, fusion_min)
                    except Exception as e:
                        print(f"Error: {e}")
                        
        print(f"\nBest Return for {symbol}: {best_return}% with params ADX, EMA_F, FUSION_MIN = {best_params}")

if __name__ == "__main__":
    asyncio.run(main())
