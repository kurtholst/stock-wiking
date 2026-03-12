import { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Bar, ComposedChart,
} from 'recharts';
import { Loader2 } from 'lucide-react';
import type { HistoryResponse } from '../types';
import { fetchHistory } from '../api';
import { getTickerColor, formatPrice } from '../utils';

const PERIODS = ['5d', '1mo', '3mo', '6mo', '1y', '3y', '5y'] as const;

interface Props {
  tickers: string[];
}

export function PriceCharts({ tickers }: Props) {
  const [period, setPeriod] = useState<string>('1mo');
  const [data, setData] = useState<HistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (tickers.length === 0) return;
    setLoading(true);
    fetchHistory(tickers, period)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [tickers, period]);

  // Build normalized comparison data
  const normalizedData = data
    ? data.dates.map((date, i) => {
        const point: Record<string, string | number> = { date };
        for (const th of data.tickers) {
          point[th.ticker] = th.normalized[i] ?? 0;
        }
        return point;
      })
    : [];

  return (
    <div className="space-y-6">
      {/* Period selector */}
      <div className="flex items-center gap-2">
        {PERIODS.map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              period === p ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {p.toUpperCase()}
          </button>
        ))}
        {loading && <Loader2 size={16} className="animate-spin text-blue-500 ml-2" />}
      </div>

      {/* Normalized comparison chart */}
      {normalizedData.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Normalized Comparison (%)</h3>
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={normalizedData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11 }}
                tickFormatter={(v: string) => v.slice(5)}
              />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={(v: number) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`}
              />
              <Tooltip
                formatter={(value: number) => [`${value > 0 ? '+' : ''}${value.toFixed(2)}%`]}
                labelFormatter={(label: string) => label}
              />
              <Legend />
              {tickers.map((ticker, i) => (
                <Line
                  key={ticker}
                  type="monotone"
                  dataKey={ticker}
                  stroke={getTickerColor(ticker, i)}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Per-ticker price + volume charts */}
      {data?.tickers.map((th, i) => {
        const chartData = th.data.map((row) => ({
          date: row.date,
          close: row.close,
          volume: row.volume,
        }));
        const color = getTickerColor(th.ticker, i);

        return (
          <div key={th.ticker} className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">{th.ticker} — Price & Volume</h3>
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} />
                <YAxis yAxisId="price" tick={{ fontSize: 11 }} tickFormatter={(v: number) => formatPrice(v)} />
                <YAxis yAxisId="vol" orientation="right" tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${(v / 1e6).toFixed(0)}M`} />
                <Tooltip />
                <Bar yAxisId="vol" dataKey="volume" fill="#e5e7eb" barSize={4} />
                <Line yAxisId="price" type="monotone" dataKey="close" stroke={color} strokeWidth={2} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        );
      })}
    </div>
  );
}
