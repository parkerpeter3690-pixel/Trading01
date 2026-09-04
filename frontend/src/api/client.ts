const API_BASE_URL = 'http://localhost:8000/api/v1';
const WS_BASE_URL = 'ws://localhost:8000/ws';

export interface PnLData {
  portfolio_value: number;
  initial_capital: number;
  total_pnl: number;
  total_pnl_pct: number;
  unrealized_pnl: number;
  cash: number;
}

export interface SystemStatus {
  status: string;
  environment: string;
  kill_switch_enabled: boolean;
  llm_provider: string;
  timestamp: string;
}

export interface Position {
  symbol: string;
  side: string;
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

export const fetchPnL = async (): Promise<PnLData> => {
  const response = await fetch(`${API_BASE_URL}/portfolio/pnl`);
  if (!response.ok) throw new Error('Failed to fetch PnL');
  return response.json();
};

export const fetchSystemStatus = async (): Promise<SystemStatus> => {
  const response = await fetch(`${API_BASE_URL}/status`);
  if (!response.ok) throw new Error('Failed to fetch System Status');
  return response.json();
};

export const systemKill = async () => {
  const response = await fetch(`${API_BASE_URL}/system/kill`, { method: 'POST' });
  if (!response.ok) throw new Error('Failed to trigger kill switch');
  return response.json();
};

export const fetchPositions = async (): Promise<Position[]> => {
  const response = await fetch(`${API_BASE_URL}/portfolio/positions`);
  if (!response.ok) throw new Error('Failed to fetch Positions');
  return response.json();
};

export const fetchMarketHistory = async (symbol: string, timeframe: string = '1d', days: number = 30) => {
  const response = await fetch(`${API_BASE_URL}/market/history/${symbol}?timeframe=${timeframe}&days=${days}`);
  if (!response.ok) throw new Error('Failed to fetch Market History');
  return response.json();
};

export const getWebSocketUrl = () => WS_BASE_URL;

export interface OrderRequest {
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  order_type: 'market' | 'limit';
  limit_price?: number;
  stop_loss?: number;
  take_profit?: number;
}

export const placeOrder = async (order: OrderRequest) => {
  const response = await fetch(`${API_BASE_URL}/trading/orders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(order),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const detail = errorData.detail;
    const msg = Array.isArray(detail) ? detail[0]?.msg : detail;
    throw new Error(msg || errorData.message || 'Failed to place order');
  }
  const data = await response.json();
  if (data.status === 'rejected') {
    throw new Error(data.reason || data.rejection_reason || 'Order rejected by risk engine or broker');
  }
  return data;
};
