import { create } from 'zustand';

export interface MarketTick {
  symbol: string;
  timestamp: number;
  price: number;
  bid?: number;
  ask?: number;
  volume?: number;
}

export interface Candle {
  time: number | string; // Lightweight charts uses unix timestamp or string date
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface MarketState {
  activeSymbol: string;
  setActiveSymbol: (symbol: string) => void;
  
  watchlist: string[];
  setWatchlist: (symbols: string[]) => void;
  
  // Latest prices for the watchlist
  latestPrices: Record<string, MarketTick>;
  updateTick: (tick: MarketTick) => void;
  
  // Historical data for charts
  historicalData: Record<string, Candle[]>;
  setHistoricalData: (symbol: string, data: Candle[]) => void;
}

export const useMarketStore = create<MarketState>((set) => ({
  activeSymbol: 'BTC-USD',
  setActiveSymbol: (symbol) => set({ activeSymbol: symbol }),
  
  watchlist: ['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'TSLA', 'NVDA'],
  setWatchlist: (symbols) => set({ watchlist: symbols }),
  
  latestPrices: {},
  updateTick: (tick) => set((state) => ({
    latestPrices: {
      ...state.latestPrices,
      [tick.symbol]: tick
    }
  })),
  
  historicalData: {},
  setHistoricalData: (symbol, data) => set((state) => ({
    historicalData: {
      ...state.historicalData,
      [symbol]: data
    }
  }))
}));
