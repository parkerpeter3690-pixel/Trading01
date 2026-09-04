import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, CandlestickSeries, HistogramSeries } from 'lightweight-charts';
import type { IChartApi, ISeriesApi, Time } from 'lightweight-charts';
import { useMarketStore } from '../stores/marketStore';

const TradingChart: React.FC = () => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  
  const { activeSymbol, historicalData, latestPrices } = useMarketStore();

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const handleResize = () => {
      chartRef.current?.applyOptions({ width: chartContainerRef.current?.clientWidth });
    };

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#334155' },
        horzLines: { color: '#334155' },
      },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#334155',
      },
      rightPriceScale: {
        borderColor: '#334155',
      },
      crosshair: {
        mode: 1, // Normal mode
        vertLine: { color: '#64748b', labelBackgroundColor: '#1e293b' },
        horzLine: { color: '#64748b', labelBackgroundColor: '#1e293b' },
      }
    });

    chartRef.current = chart;

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });
    seriesRef.current = candlestickSeries;

    // Optional Volume Series (attached to left scale or bottom)
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: '#3b82f6',
      priceFormat: { type: 'volume' },
      priceScaleId: '', // overlay
    });
    volumeSeriesRef.current = volumeSeries;
    
    chart.priceScale('').applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      }
    });

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  // Sync historical data
  useEffect(() => {
    if (seriesRef.current && volumeSeriesRef.current && historicalData[activeSymbol]) {
      const data = historicalData[activeSymbol];
      // Note: lightweight-charts requires strictly ascending time values
      // We assume data is sorted.
      seriesRef.current.setData(data as any);
      
      const volData = data.map(d => ({
        time: d.time as Time,
        value: d.volume || 0,
        color: d.close >= d.open ? '#22c55e55' : '#ef444455'
      }));
      volumeSeriesRef.current.setData(volData);
    } else if (seriesRef.current && volumeSeriesRef.current) {
      seriesRef.current.setData([]);
      volumeSeriesRef.current.setData([]);
    }
  }, [historicalData, activeSymbol]);

  // Sync live tick updates to current candle
  useEffect(() => {
    if (!seriesRef.current || !latestPrices[activeSymbol]) return;
    
    const latestTick = latestPrices[activeSymbol];
    const history = historicalData[activeSymbol];
    if (!history || history.length === 0) return;

    // Get the last candle
    const lastCandle = history[history.length - 1];
    const newPrice = latestTick.price;
    
    const updatedCandle = {
      time: lastCandle.time as Time,
      open: lastCandle.open,
      high: Math.max(lastCandle.high, newPrice),
      low: Math.min(lastCandle.low, newPrice),
      close: newPrice,
    };
    
    // In a real tick aggregation, we would roll over to a new candle based on timestamp.
    // For now, we just update the last candle.
    seriesRef.current.update(updatedCandle);
  }, [latestPrices, activeSymbol, historicalData]);

  return (
    <div className="w-full h-full flex flex-col glass-panel p-4">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          {activeSymbol}
        </h2>
        <div className="flex gap-2">
          {['1m', '5m', '15m', '1h', '1D'].map((tf) => (
            <button 
              key={tf} 
              className={`px-3 py-1 text-xs rounded border transition-colors ${
                tf === '1D' ? 'bg-primary/20 border-primary text-primary-light' : 'bg-surface border-border text-slate-400 hover:text-slate-200'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>
      <div ref={chartContainerRef} className="flex-1 w-full min-h-[400px]" />
    </div>
  );
};

export default TradingChart;
