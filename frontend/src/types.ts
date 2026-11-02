export interface QuoteData {
  ticker: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
  day_high: number;
  day_low: number;
  week52_high: number;
  week52_low: number;
  market_cap: number | null;
  volume: number | null;
  sparkline: number[];
}

export interface OHLCVRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  change_pct: number | null;
  ma20: number | null;
  ma50: number | null;
  ma200: number | null;
}

export interface TickerHistory {
  ticker: string;
  data: OHLCVRow[];
  normalized: number[];
}

export interface HistoryResponse {
  tickers: TickerHistory[];
  dates: string[];
}

export interface TechnicalsResponse {
  ticker: string;
  dates: string[];
  close: number[];
  sma20: (number | null)[];
  sma50: (number | null)[];
  ema12: (number | null)[];
  ema26: (number | null)[];
  bb_upper: (number | null)[];
  bb_middle: (number | null)[];
  bb_lower: (number | null)[];
  rsi: (number | null)[];
  macd: (number | null)[];
  macd_signal: (number | null)[];
  macd_hist: (number | null)[];
  volume: number[];
}

export interface RankRow {
  ticker: string;
  price: number;
  pe_ratio: number | null;
  change_1d: number | null;
  change_1w: number | null;
  change_1m: number | null;
  change_3m: number | null;
  rsi14: number | null;
  macd_hist: number | null;
  bb_pct: number | null;
  ma20_dist: number | null;
  ma50_dist: number | null;
  ma200_dist: number | null;
  vol_ratio: number | null;
  atr14: number | null;
  signal: string | null;
  signal_reason: string | null;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponseData {
  reply: string;
  model: string;
}

// Patent AI tab types (per-ticker patent search)

export interface PatentResult {
  patent_number: string;
  title: string;
  applicant: string;
  filing_date: string | null;
  status: string | null;
}

export interface PatentScore {
  patent_number: string;
  title: string;
  score: 'POSITIVE' | 'INSIGNIFICANT' | 'NEGATIVE';
  reasoning: string;
}

export interface PatentSearchResponse {
  ticker: string;
  company_name: string;
  patents: PatentResult[];
  total_found: number;
  source: string;
  error: string | null;
}

export interface PatentAnalyzeRequest {
  ticker: string;
  company_name: string;
  patents: PatentResult[];
}

export interface PatentAnalyzeResponse {
  ticker: string;
  company_name: string;
  scores: PatentScore[];
  summary: string;
  model: string;
}

// Patent discovery types (Company Search tab)

export interface DiscoverPatentResult {
  title: string;
  patent_number: string;
  date: string | null;
  applicant: string;
}

export interface DiscoverRequest {
  query: string;
  ipc?: string;
  date_from?: string;
  date_to?: string;
}

export interface CompanyPatents {
  company: string;
  patent_count: number;
  sample_patents: DiscoverPatentResult[];
}

export interface DiscoverResponse {
  query: string;
  companies: CompanyPatents[];
  total_patents: number;
  source: string;
  error: string | null;
}

export interface CompanyRanking {
  company: string;
  score: string;
  reasoning: string;
  patent_count: number;
}

export interface DiscoverAnalyzeRequest {
  query: string;
  companies: CompanyPatents[];
}

export interface DiscoverAnalyzeResponse {
  query: string;
  rankings: CompanyRanking[];
  summary: string;
  model: string;
}

// DKPTO (Danish patent search) types

export interface DkptoSearchRequest {
  applicant?: string;
  title?: string;
  ipc?: string;
  date_from?: string;
  date_to?: string;
}

export interface DkptoSearchResponse {
  patents: DiscoverPatentResult[];
  total_found: number;
  source: string;
  error: string | null;
}

// Stars (Danish patent screener) types

export interface StarsPatentHit {
  patent_number: string;
  title: string;
  applicant: string;
  filing_date: string | null;
  publication_date: string | null;
  ipc?: string[];
  applicants?: string[];
}

export interface AreaShift {
  baseline_count: number;
  recent_count: number;
  ipc_shift: number | null;
  office_shift: number | null;
  new_ipc: string[];
  new_offices: string[];
  top_ipc_recent: string[];
  top_ipc_baseline: string[];
  flagged: boolean;
  data_complete?: boolean;
}

export interface CompanyStarsResult {
  name: string;
  ticker: string;
  sector: string;
  patent_count: number;
  recent_patents: StarsPatentHit[];
  stars: number | null;
  ai_signal: string | null;
  ai_summary: string | null;
  stock_price: number | null;
  stock_change_pct: number | null;
  area_shift?: AreaShift | null;
}

export interface StarsScanResponse {
  scan_date: string;
  period_days: number;
  companies: CompanyStarsResult[];
  total_patents: number;
  summary: string;
  model: string;
  run_at?: string | null;
  trigger?: 'manual' | 'scheduled' | null;
}

// Background runs (Stars scan / deep alpha analysis)

export type RunKind = 'stars' | 'deep';

export interface RunStatus {
  kind: RunKind | null;
  status: 'idle' | 'running' | 'done' | 'error';
  started_at: string | null;
  finished_at: string | null;
  step: number;
  total: number;
  message: string;
  error: string | null;
  elapsed_s: number | null;
  external_running: boolean;
}

// Deep alpha analysis

export interface QuarterStat {
  label: string;
  start: string;
  end: string;
  total: number | null;
  sample: number;
  ipc_shift: number | null;
}

export interface EmergingArea {
  code: string;
  recent_count: number;
  first_seen: string;
  examples: string[];
}

export interface CoApplicant {
  name: string;
  count: number;
  first_seen: string;
  new: boolean;
}

export interface DeepThesis {
  move_type: string;
  hypothesis: string;
  conviction: number;
  horizon: string;
  priced_in: 'LOW' | 'MEDIUM' | 'HIGH';
  catalysts: string[];
  risks: string[];
  confirm_signals: string[];
  refute_signals: string[];
}

export interface DeepCompany {
  name: string;
  ticker: string;
  sector: string;
  stars: number | null;
  ai_signal: string | null;
  data_complete: boolean;
  quarters: QuarterStat[];
  recent_total: number | null;
  baseline_avg: number | null;
  velocity_ratio: number | null;
  recent_shift: number | null;
  office_shift: number | null;
  shift_trend: 'ACCELERATING' | 'STABLE' | 'FADING' | null;
  top_ipc_recent: string[];
  top_ipc_baseline: string[];
  emerging: EmergingArea[];
  new_offices: string[];
  co_applicants: CoApplicant[];
  return_3m: number | null;
  return_6m: number | null;
  from_52w_high: number | null;
  alpha_score: number;
  score_breakdown: Record<string, number>;
  thesis: DeepThesis | null;
}

export interface AlphaDeepResponse {
  run_at: string;
  finished_at: string;
  duration_s: number;
  trigger: 'manual' | 'scheduled';
  quarters: number;
  companies: DeepCompany[];
  themes: { code: string; companies: string[] }[];
  ipc_labels: { code: string; label: string }[];
  memo: string;
  model: string;
  warnings: string[];
  in_progress?: boolean;
  phase?: 'data' | 'ai' | 'memo' | 'done';
  companies_done?: number;
  companies_total?: number;
}
