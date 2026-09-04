import React from 'react';
import { useMarketStore } from '../stores/marketStore';

const Watchlist: React.FC = () => {
  const { watchlist, activeSymbol, setActiveSymbol, latestPrices } = useMarketStore();

  return (
    <div className="glass-panel p-4 flex flex-col h-full overflow-hidden">
      <h2 className="text-sm font-bold text-slate-400 mb-4 uppercase tracking-wider">Watchlist</h2>
      <div className="flex-1 overflow-y-auto pr-2 scrollbar-hide space-y-2">
        {watchlist.map(symbol => {
          const isActive = symbol === activeSymbol;
          const priceInfo = latestPrices[symbol];
          
          return (
            <div 
              key={symbol}
              onClick={() => setActiveSymbol(symbol)}
              className={`p-3 rounded-lg cursor-pointer transition-all border ${
                isActive 
                  ? 'bg-primary/10 border-primary/50 shadow-glow' 
                  : 'bg-surface/50 border-border/50 hover:bg-surface-hover'
              }`}
            >
              <div className="flex justify-between items-center mb-1">
                <span className={`font-bold ${isActive ? 'text-primary-light' : 'text-slate-200'}`}>
                  {symbol}
                </span>
                <span className="text-xs font-mono bg-surface-hover px-1.5 py-0.5 rounded text-slate-400">
                  LIVE
                </span>
              </div>
              
              <div className="flex justify-between items-end">
                <span className="font-mono font-medium text-slate-100">
                  {priceInfo ? `$${priceInfo.price.toLocaleString(undefined, {minimumFractionDigits: 2})}` : '---'}
                </span>
                {/* Placeholder for change % until we calculate it in store */}
                <span className="text-xs font-mono text-emerald-400">
                  +0.00%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Watchlist;
