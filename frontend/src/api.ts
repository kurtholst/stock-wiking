import type { QuoteData, HistoryResponse, TechnicalsResponse, ChatResponseData, RankRow } from './types';

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
