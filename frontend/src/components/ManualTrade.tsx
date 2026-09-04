import React, { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, ShieldAlert } from 'lucide-react';
import { placeOrder, fetchSystemStatus, type OrderRequest } from '../api/client';
import { useMarketStore } from '../stores/marketStore';

const ManualTrade: React.FC = () => {
  const { activeSymbol, setActiveSymbol } = useMarketStore();
  const [side, setSide] = useState<'buy' | 'sell'>('buy');
  const [quantity, setQuantity] = useState<number>(1);
  const [orderType, setOrderType] = useState<'market' | 'limit'>('market');
  const [limitPrice, setLimitPrice] = useState<number | ''>('');
  const [stopLoss, setStopLoss] = useState<number | ''>('');

  const { data: systemStatus } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: fetchSystemStatus,
  });

  const isPaper = systemStatus?.environment === 'development' || systemStatus?.environment === 'paper';
  
  const mutation = useMutation({
    mutationFn: placeOrder,
    onSuccess: () => {
      setQuantity(1);
      setLimitPrice('');
      setStopLoss('');
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeSymbol || quantity <= 0) return;

    const order: OrderRequest = {
      symbol: activeSymbol.toUpperCase(),
      side,
      quantity,
      order_type: orderType,
      ...(orderType === 'limit' && limitPrice ? { limit_price: Number(limitPrice) } : {}),
      ...(stopLoss ? { stop_loss: Number(stopLoss) } : {})
    };

    mutation.mutate(order);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Trading Environment Banner */}
      <div className={`mb-4 px-3 py-2 rounded-lg border text-xs font-bold uppercase tracking-wider flex items-center justify-between ${
        isPaper 
          ? 'bg-amber-500/10 border-amber-500/30 text-amber-500' 
          : 'bg-red-500/10 border-red-500/30 text-red-500 animate-pulse'
      }`}>
        <div className="flex items-center gap-2">
          {isPaper ? <ShieldAlert className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
          {isPaper ? 'PAPER TRADING' : 'LIVE EXECUTION'}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="flex-1 flex flex-col gap-3">
        
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-[10px] text-muted mb-1 uppercase tracking-wider">Symbol</label>
            <input 
              type="text" 
              value={activeSymbol}
              onChange={(e) => setActiveSymbol(e.target.value.toUpperCase())}
              className="w-full bg-surface/50 border border-border rounded px-2 py-1.5 text-xs font-bold text-slate-200 outline-none focus:border-primary-light uppercase"
              required
            />
          </div>
          <div>
            <label className="block text-[10px] text-muted mb-1 uppercase tracking-wider">Quantity</label>
            <input 
              type="number" 
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              min="0.1"
              step="0.1"
              className="w-full bg-surface/50 border border-border rounded px-2 py-1.5 text-xs font-mono text-slate-200 outline-none focus:border-primary-light"
              required
            />
          </div>
        </div>

        <div className="flex bg-surface/30 p-1 rounded border border-border/50">
          <button
            type="button"
            onClick={() => setSide('buy')}
            className={`flex-1 py-1.5 text-xs font-bold uppercase tracking-wider rounded transition-all ${side === 'buy' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'text-muted hover:text-slate-300'}`}
          >
            Buy
          </button>
          <button
            type="button"
            onClick={() => setSide('sell')}
            className={`flex-1 py-1.5 text-xs font-bold uppercase tracking-wider rounded transition-all ${side === 'sell' ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'text-muted hover:text-slate-300'}`}
          >
            Sell
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-[10px] text-muted mb-1 uppercase tracking-wider">Type</label>
            <select 
              value={orderType}
              onChange={(e) => setOrderType(e.target.value as 'market' | 'limit')}
              className="w-full bg-surface/50 border border-border rounded px-2 py-1.5 text-xs text-slate-200 outline-none focus:border-primary-light"
            >
              <option value="market">Market</option>
              <option value="limit">Limit</option>
            </select>
          </div>
          {orderType === 'limit' && (
            <div>
              <label className="block text-[10px] text-muted mb-1 uppercase tracking-wider">Limit Price</label>
              <input 
                type="number" 
                value={limitPrice}
                onChange={(e) => setLimitPrice(Number(e.target.value))}
                min="0.01"
                step="0.01"
                placeholder="0.00"
                className="w-full bg-surface/50 border border-border rounded px-2 py-1.5 text-xs font-mono text-slate-200 outline-none focus:border-primary-light"
                required
              />
            </div>
          )}
        </div>

        <div>
          <label className="block text-[10px] text-muted mb-1 uppercase tracking-wider">Stop Loss / Take Profit</label>
          <input 
            type="number" 
            value={stopLoss}
            onChange={(e) => setStopLoss(e.target.value ? Number(e.target.value) : '')}
            min="0.01"
            step="0.01"
            placeholder="SL Price (Optional)"
            className="w-full bg-surface/50 border border-border rounded px-2 py-1.5 text-xs font-mono text-slate-200 outline-none focus:border-primary-light"
          />
        </div>

        <div className="mt-auto pt-4">
          {mutation.isError && (
            <div className="mb-2 p-2 bg-red-500/10 border border-red-500/20 rounded flex items-start gap-2">
              <AlertCircle className="w-3 h-3 text-red-400 mt-0.5 shrink-0" />
              <p className="text-[10px] text-red-400 break-words">{mutation.error instanceof Error ? mutation.error.message : 'Error placing order'}</p>
            </div>
          )}
          {mutation.isSuccess && (
            <div className="mb-2 p-2 bg-emerald-500/10 border border-emerald-500/20 rounded flex items-center gap-2">
              <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
              <p className="text-[10px] text-emerald-400">Order confirmed by execution engine</p>
            </div>
          )}

          <button 
            type="submit" 
            disabled={mutation.isPending || !activeSymbol}
            className={`w-full py-2.5 rounded font-bold text-xs uppercase tracking-wider transition-all duration-300 flex items-center justify-center gap-2 ${
              side === 'buy' 
                ? 'bg-emerald-500 hover:bg-emerald-400 text-slate-900 shadow-glow' 
                : 'bg-red-500 hover:bg-red-400 text-slate-900 shadow-glow-sell'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {mutation.isPending ? (
              <span className="animate-pulse">Submitting to broker...</span>
            ) : (
              <>Execute {side}</>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default ManualTrade;
