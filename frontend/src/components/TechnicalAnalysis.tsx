import { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Bar, ComposedChart, Legend,
  Area,
} from 'recharts';
import { Loader2 } from 'lucide-react';
import type { TechnicalsResponse } from '../types';
import { fetchTechnicals } from '../api';

const PERIODS = ['3mo', '6mo', '1y', '2y', '3y', '5y'] as const;

interface Props {
  tickers: string[];
}

export function TechnicalAnalysis({ tickers }: Props) {
  const [selectedTicker, setSelectedTicker] = useState(tickers[0] ?? '');
  const [period, setPeriod] = useState<string>('3y');
  const [data, setData] = useState<TechnicalsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (tickers.length > 0 && !tickers.includes(selectedTicker)) {
      setSelectedTicker(tickers[0]);
    }
  }, [tickers, selectedTicker]);

  useEffect(() => {
    if (!selectedTicker) return;
    setLoading(true);
    fetchTechnicals(selectedTicker, period)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [selectedTicker, period]);

  if (!selectedTicker) {
    return <div className="text-gray-400 text-center py-12">No tickers selected</div>;
  }

  // Build chart data arrays
  const priceData = data
    ? data.dates.map((date, i) => ({
        date,
        close: data.close[i],
        sma20: data.sma20[i],
        sma50: data.sma50[i],
        bb_upper: data.bb_upper[i],
        bb_lower: data.bb_lower[i],
      }))
    : [];

  const rsiData = data
    ? data.dates.map((date, i) => ({ date, rsi: data.rsi[i] }))
    : [];

  const macdData = data
    ? data.dates.map((date, i) => ({
        date,
        macd: data.macd[i],
        signal: data.macd_signal[i],
        histogram: data.macd_hist[i],
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex items-center gap-4 flex-wrap">
        <select
          value={selectedTicker}
          onChange={(e) => setSelectedTicker(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {tickers.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <div className="flex gap-1">
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
        </div>
        {loading && <Loader2 size={16} className="animate-spin text-blue-500" />}
      </div>

      {data && (
        <>
          {/* Price + MAs + Bollinger Bands */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">
              {selectedTicker} — Price, Moving Averages & Bollinger Bands
            </h3>
            <ResponsiveContainer width="100%" height={320}>
              <ComposedChart data={priceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} />
                <YAxis tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
                <Tooltip />
                <Legend />
                <Area type="monotone" dataKey="bb_upper" stroke="none" fill="#e0e7ff" fillOpacity={0.4} name="BB Upper" />
                <Area type="monotone" dataKey="bb_lower" stroke="none" fill="#e0e7ff" fillOpacity={0.4} name="BB Lower" />
                <Line type="monotone" dataKey="close" stroke="#1f2937" strokeWidth={2} dot={false} name="Close" />
                <Line type="monotone" dataKey="sma20" stroke="#3b82f6" strokeWidth={1.5} dot={false} name="SMA 20" strokeDasharray="4 2" />
                <Line type="monotone" dataKey="sma50" stroke="#f59e0b" strokeWidth={1.5} dot={false} name="SMA 50" strokeDasharray="4 2" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* RSI */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">{selectedTicker} — RSI (14)</h3>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={rsiData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip />
                <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="3 3" label={{ value: 'Overbought', position: 'right', fontSize: 10, fill: '#ef4444' }} />
                <ReferenceLine y={30} stroke="#22c55e" strokeDasharray="3 3" label={{ value: 'Oversold', position: 'right', fontSize: 10, fill: '#22c55e' }} />
                <ReferenceLine y={50} stroke="#9ca3af" strokeDasharray="2 4" />
                <Line type="monotone" dataKey="rsi" stroke="#8b5cf6" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* MACD */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">{selectedTicker} — MACD (12, 26, 9)</h3>
            <ResponsiveContainer width="100%" height={220}>
              <ComposedChart data={macdData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <ReferenceLine y={0} stroke="#9ca3af" />
                <Bar dataKey="histogram" name="Histogram" fill="#93c5fd" barSize={3} />
                <Line type="monotone" dataKey="macd" stroke="#2563eb" strokeWidth={1.5} dot={false} name="MACD" />
                <Line type="monotone" dataKey="signal" stroke="#dc2626" strokeWidth={1.5} dot={false} name="Signal" strokeDasharray="4 2" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
