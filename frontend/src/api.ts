// Client for the trading floor HTTP API.
//
// In dev, VITE_API_BASE resta vuota e i path (es. "/api/traders") sono
// relativi: il proxy in vite.config.ts li inoltra alla FastAPI locale, quindi
// il browser vede una sola origine.
//
// In produzione, quando frontend e API sono due servizi separati (il deploy
// gratuito su Render: Static Site + Web Service), Vite inietta VITE_API_BASE
// a build time e ogni chiamata diventa assoluta, es.
// "https://trading-floor-api.onrender.com/api/traders". Va abbinato a
// ALLOWED_ORIGINS lato backend/api.py, altrimenti il browser blocca la
// risposta per CORS.

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export interface TraderInfo {
  name: string;
  lastname: string;
  model_name: string;
}

export interface Holding {
  symbol: string;
  quantity: number;
  price: number;
  avg_cost: number;
  market_value: number;
  unrealized_pnl: number;
}

export interface Transaction {
  symbol: string;
  quantity: number;
  price: number;
  timestamp: string;
  rationale: string;
}

export interface TimePoint {
  datetime: string;
  value: number;
}

// Mirrors the full backend payload; the dashboard renders a subset of these fields.
export interface TraderDetail extends TraderInfo {
  balance: number;
  strategy: string;
  portfolio_value: number;
  pnl: number;
  holdings: Holding[];
  transactions: Transaction[];
  time_series: TimePoint[];
}

export interface LogRow {
  datetime: string;
  type: string;
  message: string;
  color: string;
}

export interface MarketInfo {
  source: "massive" | "simulator";
  is_market_open: boolean;
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) throw new Error(`${path} failed: ${r.status}`);
  return r.json() as Promise<T>;
}

export function getTraders(): Promise<TraderInfo[]> {
  return get("/api/traders");
}

export function getTrader(name: string): Promise<TraderDetail> {
  return get(`/api/traders/${encodeURIComponent(name)}`);
}

export function getTraderLogs(name: string, lastN = 13): Promise<LogRow[]> {
  return get(`/api/traders/${encodeURIComponent(name)}/logs?last_n=${lastN}`);
}

export function getMarket(): Promise<MarketInfo> {
  return get("/api/market");
}
