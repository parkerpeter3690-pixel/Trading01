import React from 'react';
import { Wallet, TrendingUp, AlertTriangle, Target } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { fetchPnL, fetchPositions } from '../api/client';

const Vitals: React.FC = () => {
  const { data: pnlData, isLoading: isLoadingPnL } = useQuery({
    queryKey: ['pnl'],
    queryFn: fetchPnL,
    refetchInterval: 5000,
  });

  const { data: positions, isLoading: isLoadingPositions } = useQuery({
    queryKey: ['positions'],
    queryFn: fetchPositions,
    refetchInterval: 5000,
  });

  const formatter = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  });

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      {/* Portfolio Value */}
      <div className="glass-panel p-5 relative overflow-hidden group">
        <div className="absolute top-0 right-0 w-32 h-32 bg-primary-light/10 rounded-full blur-3xl group-hover:bg-primary-light/20 transition-all"></div>
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-primary/20 rounded-lg">
            <Wallet className="w-5 h-5 text-primary-light" />
          </div>
          <h3 className="text-sm font-medium text-muted">Total Value</h3>
        </div>
        <div className="mt-4 flex items-end gap-3">
          <span className="text-3xl font-bold font-mono">
            {isLoadingPnL ? '...' : formatter.format(pnlData?.portfolio_value || 0)}
          </span>
          <span className={`text-sm font-medium mb-1 flex items-center ${
            (pnlData?.total_pnl_pct || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
          }`}>
            {isLoadingPnL ? '' : `${pnlData?.total_pnl_pct! >= 0 ? '+' : ''}${pnlData?.total_pnl_pct?.toFixed(2)}%`}
          </span>
        </div>
      </div>

      {/* Daily PnL */}
      <div className="glass-panel p-5 relative overflow-hidden group">
        <div className={`absolute top-0 right-0 w-32 h-32 rounded-full blur-3xl transition-all ${
          (pnlData?.total_pnl || 0) >= 0 ? 'bg-emerald-500/10 group-hover:bg-emerald-500/20' : 'bg-red-500/10 group-hover:bg-red-500/20'
        }`}></div>
        <div className="flex items-center gap-3 mb-2">
          <div className={`p-2 rounded-lg ${
            (pnlData?.total_pnl || 0) >= 0 ? 'bg-emerald-500/20' : 'bg-red-500/20'
          }`}>
            <TrendingUp className={`w-5 h-5 ${
              (pnlData?.total_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
            }`} />
          </div>
          <h3 className="text-sm font-medium text-muted">Total P&L</h3>
        </div>
        <div className="mt-4 flex items-end gap-3">
          <span className={`text-3xl font-bold font-mono ${
            (pnlData?.total_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
          }`}>
            {isLoadingPnL ? '...' : `${pnlData?.total_pnl! >= 0 ? '+' : ''}${formatter.format(pnlData?.total_pnl || 0)}`}
          </span>
        </div>
      </div>

      {/* Market Regime */}
      <div className="glass-panel p-5 relative overflow-hidden group">
        <div className="absolute top-0 right-0 w-32 h-32 bg-amber-500/10 rounded-full blur-3xl group-hover:bg-amber-500/20 transition-all"></div>
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-amber-500/20 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
          </div>
          <h3 className="text-sm font-medium text-muted">Market Regime</h3>
        </div>
        <div className="mt-4">
          <span className="text-xl font-bold text-amber-400">WAITING DATA</span>
          <p className="text-xs text-muted mt-1">Regime detection pending stream...</p>
        </div>
      </div>

      {/* Active Positions */}
      <div className="glass-panel p-5 relative overflow-hidden group">
        <div className="absolute top-0 right-0 w-32 h-32 bg-accent/10 rounded-full blur-3xl group-hover:bg-accent/20 transition-all"></div>
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-accent/20 rounded-lg">
            <Target className="w-5 h-5 text-accent" />
          </div>
          <h3 className="text-sm font-medium text-muted">Active Positions</h3>
        </div>
        <div className="mt-4 flex items-end gap-3">
          <span className="text-3xl font-bold font-mono">
            {isLoadingPositions ? '...' : (positions?.length || 0)}
          </span>
          <span className="text-muted text-sm font-medium mb-1">/ 10 Max</span>
        </div>
      </div>
    </div>
  );
};

export default Vitals;
