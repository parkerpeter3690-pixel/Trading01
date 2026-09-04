import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchPositions } from '../api/client';
import { useMarketStore } from '../stores/marketStore';
import { Activity, Clock } from 'lucide-react';

const PositionsPanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'positions' | 'orders' | 'history'>('positions');
  const { data: positions = [] } = useQuery({
    queryKey: ['positions'],
    queryFn: fetchPositions,
    refetchInterval: 5000,
  });

  const { setActiveSymbol } = useMarketStore();

  return (
    <div className="flex-1 glass-panel flex flex-col overflow-hidden min-w-0">
      {/* Tabs */}
      <div className="flex border-b border-border/50">
        <button
          className={`px-4 py-3 text-xs font-bold uppercase tracking-wider transition-colors ${
            activeTab === 'positions' ? 'text-primary-light border-b-2 border-primary-light bg-primary/5' : 'text-slate-400 hover:text-slate-200'
          }`}
          onClick={() => setActiveTab('positions')}
        >
          Active Positions {positions.length > 0 && <span className="ml-1 bg-surface-hover px-1.5 py-0.5 rounded text-[10px]">{positions.length}</span>}
        </button>
        <button
          className={`px-4 py-3 text-xs font-bold uppercase tracking-wider transition-colors ${
            activeTab === 'orders' ? 'text-primary-light border-b-2 border-primary-light bg-primary/5' : 'text-slate-400 hover:text-slate-200'
          }`}
          onClick={() => setActiveTab('orders')}
        >
          Open Orders
        </button>
        <button
          className={`px-4 py-3 text-xs font-bold uppercase tracking-wider transition-colors ${
            activeTab === 'history' ? 'text-primary-light border-b-2 border-primary-light bg-primary/5' : 'text-slate-400 hover:text-slate-200'
          }`}
          onClick={() => setActiveTab('history')}
        >
          Execution History
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-2 scrollbar-hide">
        {activeTab === 'positions' && (
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-slate-400 uppercase tracking-wider border-b border-border/30">
              <tr>
                <th className="px-3 py-2 font-medium">Symbol</th>
                <th className="px-3 py-2 font-medium">Side</th>
                <th className="px-3 py-2 font-medium text-right">Quantity</th>
                <th className="px-3 py-2 font-medium text-right">Entry Price</th>
                <th className="px-3 py-2 font-medium text-right">Current Price</th>
                <th className="px-3 py-2 font-medium text-right">Unrealized P&L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {positions.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-6 text-muted font-mono text-xs">No active positions</td>
                </tr>
              ) : (
                positions.map((pos, i) => {
                  const isProfit = pos.unrealized_pnl >= 0;
                  return (
                    <tr 
                      key={i} 
                      className="hover:bg-surface/30 cursor-pointer transition-colors"
                      onClick={() => setActiveSymbol(pos.symbol)}
                    >
                      <td className="px-3 py-2 font-bold text-slate-200">{pos.symbol}</td>
                      <td className="px-3 py-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold ${
                          pos.side.toLowerCase() === 'long' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                        }`}>
                          {pos.side}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right font-mono">{pos.quantity}</td>
                      <td className="px-3 py-2 text-right font-mono">${(pos.avg_entry_price || 0).toFixed(2)}</td>
                      <td className="px-3 py-2 text-right font-mono">${(pos.current_price || 0).toFixed(2)}</td>
                      <td className={`px-3 py-2 text-right font-mono font-bold ${isProfit ? 'text-emerald-400' : 'text-red-400'}`}>
                        {isProfit ? '+' : ''}{(pos.unrealized_pnl || 0).toFixed(2)} ({isProfit ? '+' : ''}{(pos.unrealized_pnl_pct || 0).toFixed(2)}%)
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        )}

        {activeTab === 'orders' && (
          <div className="flex flex-col items-center justify-center h-full text-muted py-6">
            <Activity className="w-6 h-6 mb-2 opacity-20" />
            <span className="text-xs font-mono">No pending orders</span>
          </div>
        )}

        {activeTab === 'history' && (
          <div className="flex flex-col items-center justify-center h-full text-muted py-6">
            <Clock className="w-6 h-6 mb-2 opacity-20" />
            <span className="text-xs font-mono">No recent executions</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default PositionsPanel;
