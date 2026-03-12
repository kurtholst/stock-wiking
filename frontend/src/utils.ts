export const TICKER_COLORS: Record<string, string> = {
  SAP: '#0070C0',
  AAPL: '#555555',
  AMZN: '#FF9900',
  'NOVO-B.CO': '#D0021B',
};

const FALLBACK_COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300', '#00C49F', '#FFBB28', '#FF8042'];

export function getTickerColor(ticker: string, index: number): string {
  return TICKER_COLORS[ticker] ?? FALLBACK_COLORS[index % FALLBACK_COLORS.length];
}

export function formatPrice(value: number): string {
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

export function formatCompact(value: number | null | undefined): string {
  if (value == null) return 'N/A';
  if (value >= 1e12) return `${(value / 1e12).toFixed(1)}T`;
  if (value >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(0);
}
