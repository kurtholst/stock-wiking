import type {
  QuoteData, HistoryResponse, TechnicalsResponse, ChatResponseData, RankRow,
  PatentSearchResponse, PatentAnalyzeRequest, PatentAnalyzeResponse,
  DiscoverRequest, DiscoverResponse, DiscoverAnalyzeRequest, DiscoverAnalyzeResponse,
  DkptoSearchRequest, DkptoSearchResponse,
  StarsScanResponse,
} from './types';

export async function fetchTickers(): Promise<{ tickers: string[] }> {
  const res = await fetch('/stock/api/tickers');
  if (!res.ok) throw new Error('Failed to fetch tickers');
  return res.json();
}

export async function saveTickers(tickers: string[]): Promise<void> {
  await fetch('/stock/api/tickers', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tickers }),
  });
}

export async function fetchQuote(ticker: string): Promise<QuoteData> {
  const res = await fetch(`/stock/api/quote/${encodeURIComponent(ticker)}`);
  if (!res.ok) throw new Error(`Failed to fetch quote for ${ticker}`);
  return res.json();
}

export async function validateTicker(ticker: string): Promise<{ ticker: string; valid: boolean }> {
  const res = await fetch(`/stock/api/validate/${encodeURIComponent(ticker)}`);
  if (!res.ok) throw new Error(`Failed to validate ${ticker}`);
  return res.json();
}

export async function fetchHistory(tickers: string[], period: string): Promise<HistoryResponse> {
  const res = await fetch('/stock/api/history', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tickers, period }),
  });
  if (!res.ok) throw new Error('Failed to fetch history');
  return res.json();
}

export async function fetchTechnicals(ticker: string, period: string): Promise<TechnicalsResponse> {
  const res = await fetch('/stock/api/technicals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, period }),
  });
  if (!res.ok) throw new Error('Failed to fetch technicals');
  return res.json();
}

export async function fetchRank(tickers: string[]): Promise<RankRow[]> {
  const res = await fetch('/stock/api/rank', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tickers }),
  });
  if (!res.ok) throw new Error('Failed to fetch rank data');
  return res.json();
}

export async function sendChatMessage(
  messages: { role: string; content: string }[],
  tickerContext?: { tickers: string[]; quotes?: Record<string, unknown>[] },
): Promise<ChatResponseData> {
  const res = await fetch('/stock/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, ticker_context: tickerContext }),
  });
  if (!res.ok) throw new Error('Chat request failed');
  return res.json();
}

// --- Patent AI (per-ticker) ---

export async function fetchPatents(ticker: string): Promise<PatentSearchResponse> {
  const res = await fetch(`/stock/api/patents/${encodeURIComponent(ticker)}`);
  if (!res.ok) throw new Error(`Failed to fetch patents for ${ticker}`);
  return res.json();
}

export async function analyzePatents(request: PatentAnalyzeRequest): Promise<PatentAnalyzeResponse> {
  const res = await fetch('/stock/api/patents/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error('Patent analysis failed');
  return res.json();
}

// --- Company Search (discovery) ---

export async function discoverPatents(request: DiscoverRequest): Promise<DiscoverResponse> {
  const res = await fetch('/stock/api/patents/discover', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error('Patent discovery failed');
  return res.json();
}

export async function analyzeDiscovery(request: DiscoverAnalyzeRequest): Promise<DiscoverAnalyzeResponse> {
  const res = await fetch('/stock/api/patents/discover/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error('Discovery analysis failed');
  return res.json();
}

// --- Company AI (search by any company name) ---

export async function searchCompanyPatents(companyName: string): Promise<PatentSearchResponse> {
  const res = await fetch('/stock/api/patents/company', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ company_name: companyName }),
  });
  if (!res.ok) throw new Error('Company patent search failed');
  return res.json();
}

// --- DKPTO (Danish patent search) ---

export async function searchDkptoPatents(request: DkptoSearchRequest): Promise<DkptoSearchResponse> {
  const res = await fetch('/stock/api/patents/dkpto', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) throw new Error('DKPTO search failed');
  return res.json();
}

// --- Stars (Danish patent screener) ---

export async function runStarsScan(periodDays: number = 90): Promise<StarsScanResponse> {
  const res = await fetch('/stock/api/stars/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ period_days: periodDays }),
  });
  if (!res.ok) throw new Error('Stars scan failed');
  return res.json();
}
