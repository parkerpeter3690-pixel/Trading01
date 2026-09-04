import React, { useState, useEffect, useRef } from 'react';
import { ShieldAlert, Cpu, Wifi, Activity } from 'lucide-react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { fetchSystemStatus, getWebSocketUrl, fetchMarketHistory, systemKill } from '../api/client';
import { useMarketStore } from '../stores/marketStore';

import Watchlist from './Watchlist';
import TradingChart from './TradingChart';
import ManualTrade from './ManualTrade';
import Vitals from './Vitals';
import PositionsPanel from './PositionsPanel';

interface LogEntry {
  time: string;
  type: string;
  title: string;
  text: string;
}

const MAX_LOGS = 100;

const Dashboard: React.FC = () => {
  const [killSwitch, setKillSwitch] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const { activeSymbol, setHistoricalData } = useMarketStore();

  const { data: systemStatus } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: fetchSystemStatus,
    refetchInterval: 10000,
  });

  const killMutation = useMutation({
    mutationFn: systemKill,
    onSuccess: () => setKillSwitch(true)
  });

  // Fetch chart history when active symbol changes
  useEffect(() => {
    fetchMarketHistory(activeSymbol, '1d', 30).then(data => {
      if (data.data) {
        const formatted = Object.entries(data.data).map(([time, vals]: any) => {
          // ensure valid date parsing
          const date = new Date(time);
          // For daily data, lightweight charts prefers YYYY-MM-DD string
          const dateStr = date.toISOString().split('T')[0];
          return {
            time: dateStr,
            open: vals.open,
            high: vals.high,
            low: vals.low,
            close: vals.close,
            volume: vals.volume
          };
        }).sort((a: any, b: any) => a.time.localeCompare(b.time));
        
        setHistoricalData(activeSymbol, formatted as any);
      }
    }).catch(err => console.error("Failed to load chart history", err));
  }, [activeSymbol, setHistoricalData]);

  // ── WebSocket with auto-reconnect ──────────────────────────────
  useEffect(() => {
    let isMounted = true;

    function connect() {
      if (!isMounted) return;

      const ws = new WebSocket(getWebSocketUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMounted) return;
        setWsConnected(true);
        setLogs(prev => [{
          time: new Date().toLocaleTimeString(),
          type: 'SYSTEM',
          title: 'Connection Established',
          text: 'WebSocket connected to AI Orchestrator'
        }, ...prev].slice(0, MAX_LOGS));
      };

      ws.onclose = () => {
        if (!isMounted) return;
        setWsConnected(false);
        reconnectTimeout.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const data = JSON.parse(event.data);

          // Simulate extracting price tick from broadcast for now if it's a trade or analysis
          if (data.type === 'TRADE' || data.type === 'ANALYSIS') {
            // Ideally backend sends MarketTick events explicitly. 
            // For now we just append to logs.
          }

          const entry: LogEntry = {
            time: data.time || new Date().toLocaleTimeString(),
            type: data.type || 'SYSTEM',
            title: data.title || 'Event',
            text: data.text || JSON.stringify(data),
          };

          setLogs(prev => [entry, ...prev].slice(0, MAX_LOGS));
        } catch {
          setLogs(prev => [{
            time: new Date().toLocaleTimeString(),
            type: 'SYSTEM',
            title: 'Message',
            text: String(event.data),
          }, ...prev].slice(0, MAX_LOGS));
        }
      };
    }

    connect();

    return () => {
      isMounted = false;
      clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
    };
  }, []);

  const typeBadge = (type: string) => {
    switch (type) {
      case 'TRADE': return 'bg-emerald-500/20 text-emerald-400';
      case 'DEBATE': return 'bg-purple-500/20 text-purple-400';
      case 'ANALYSIS': return 'bg-blue-500/20 text-blue-400';
      case 'RISK': return 'bg-red-500/20 text-red-400';
      case 'SYSTEM':
      default: return 'bg-amber-500/20 text-amber-400';
    }
  };

  return (
    <div className="h-screen w-full bg-background flex flex-col p-2 gap-2 overflow-hidden text-slate-200">
      {/* Header */}
      <header className="flex items-center justify-between glass-panel p-2 px-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="p-1.5 bg-primary/20 rounded-md">
            <Cpu className="text-primary-light w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-100 leading-tight">Adaptive Trading Terminal</h1>
            <p className="text-[10px] text-muted flex items-center gap-1.5 uppercase tracking-wide">
              <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${wsConnected ? 'bg-emerald-500' : 'bg-red-500'}`}></span>
              {wsConnected ? 'Terminal Online' : 'Reconnecting...'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right mr-4 text-xs text-muted flex gap-4">
            <p>LLM: <span className="font-mono text-primary-light">{systemStatus?.llm_provider || 'Loading...'}</span></p>
            <p>Env: <span className="font-mono text-emerald-400 font-bold">{systemStatus?.environment?.toUpperCase() || '...'}</span></p>
          </div>
          <button 
            onClick={() => {
              if (window.confirm("EMERGENCY STOP: Are you sure you want to halt the system and cancel all orders?")) {
                killMutation.mutate();
              }
            }}
            disabled={killSwitch || killMutation.isPending}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg font-bold text-xs uppercase tracking-wider transition-all shadow-glass ${
              killSwitch 
                ? 'bg-red-500/20 text-red-500 border border-red-500/50 cursor-not-allowed' 
                : 'bg-surface hover:bg-red-500 hover:text-slate-900 border border-border text-red-400'
            }`}
          >
            <ShieldAlert className={`w-4 h-4 ${killSwitch ? 'animate-pulse' : ''}`} />
            {killSwitch ? 'SYSTEM HALTED' : 'KILL SWITCH'}
          </button>
        </div>
      </header>

      {/* Main Terminal Grid */}
      <div className="flex-1 flex flex-col gap-2 min-h-0">
        
        {/* Top Row: Watchlist, Chart, Order Entry */}
        <div className="flex-1 flex gap-2 min-h-0">
          {/* Watchlist - Left Panel */}
          <div className="w-64 shrink-0">
            <Watchlist />
          </div>

          {/* Chart - Center Panel */}
          <div className="flex-1 min-w-0">
            <TradingChart />
          </div>

          {/* Order Entry - Right Panel */}
          <div className="w-72 shrink-0 glass-panel p-4 flex flex-col overflow-y-auto">
            <h2 className="text-sm font-bold text-slate-400 mb-4 uppercase tracking-wider border-b border-border pb-2">
              Order Entry ({activeSymbol})
            </h2>
            <ManualTrade />
          </div>
        </div>

        {/* Bottom Row: Positions, Activity, Agent Graph */}
        <div className="h-64 shrink-0 flex gap-2">
          
          {/* Vitals / Account - Left */}
          <div className="w-64 shrink-0 glass-panel p-4 overflow-y-auto">
            <h2 className="text-sm font-bold text-slate-400 mb-2 uppercase tracking-wider">Account</h2>
            <div className="scale-90 origin-top-left">
              <Vitals />
            </div>
          </div>

          {/* Activity Logs - Center */}
          <div className="flex-1 glass-panel p-4 flex flex-col min-w-0">
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                <Activity className="w-4 h-4" /> Agent Telemetry
              </h2>
              {wsConnected && <Wifi className="w-3 h-3 text-emerald-500 animate-pulse" />}
            </div>
            
            <div className="flex-1 overflow-y-auto scrollbar-hide space-y-2">
              {logs.map((log, i) => (
                <div key={i} className="px-3 py-2 bg-surface/30 rounded border border-border/30 text-xs flex gap-3 items-start">
                  <span className="font-mono text-muted shrink-0 mt-0.5">{log.time}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold shrink-0 ${typeBadge(log.type)}`}>
                    {log.type}
                  </span>
                  <div>
                    <span className="font-bold mr-2 text-slate-200">{log.title}</span>
                    <span className="text-slate-400">{log.text}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Positions / Orders - Right (takes more space now) */}
          <PositionsPanel />

        </div>

      </div>
    </div>
  );
};

export default Dashboard;
