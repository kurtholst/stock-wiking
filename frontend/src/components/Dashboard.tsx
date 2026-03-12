import { useState } from 'react';
import { Area, AreaChart, ResponsiveContainer } from 'recharts';
import { Save, Check } from 'lucide-react';
import type { QuoteData } from '../types';
import { formatPrice, formatPct, formatCompact, getTickerColor } from '../utils';

interface Props {
  tickers: string[];
  quotes: Map<string, QuoteData>;
  dirty: boolean;
  onSave: () => Promise<void>;
}

export function Dashboard({ tickers, quotes, dirty, onSave }: Props) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      {/* Save bar */}
      <div className="flex items-center justify-end mb-4">
        <button
          onClick={handleSave}
          disabled={!dirty || saving}
          className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
            saved
              ? 'bg-green-100 text-green-700'
              : dirty
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed'
          }`}
        >
          {saved ? <Check size={16} /> : <Save size={16} />}
          {saving ? 'Saving...' : saved ? 'Saved' : 'Save tickers'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
      {tickers.map((ticker, i) => {
        const q = quotes.get(ticker);
        if (!q) {
          return (
            <div key={ticker} className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-20 mb-3" />
              <div className="h-8 bg-gray-200 rounded w-32 mb-2" />
              <div className="h-3 bg-gray-200 rounded w-24" />
            </div>
          );
        }

        const color = getTickerColor(ticker, i);
        const isUp = q.change_pct >= 0;
        const sparkData = q.sparkline.map((v, idx) => ({ i: idx, v }));
        const range52 = q.week52_high - q.week52_low;
        const pricePct = range52 > 0 ? ((q.price - q.week52_low) / range52) * 100 : 50;

        return (
          <div key={ticker} className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow">
            {/* Header */}
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                <span className="text-sm font-semibold text-gray-500">{ticker}</span>
              </div>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${isUp ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                {formatPct(q.change_pct)}
              </span>
            </div>

            <div className="text-xs text-gray-400 mb-2 truncate">{q.name}</div>

            {/* Price */}
            <div className="text-2xl font-bold text-gray-900 mb-1">{formatPrice(q.price)}</div>
            <div className={`text-sm mb-3 ${isUp ? 'text-green-600' : 'text-red-600'}`}>
              {q.change >= 0 ? '+' : ''}{formatPrice(q.change)}
            </div>

            {/* Sparkline */}
            {sparkData.length > 0 && (
              <div className="h-12 mb-3">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={sparkData}>
                    <defs>
                      <linearGradient id={`spark-${ticker}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                        <stop offset="100%" stopColor={color} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area
                      type="monotone"
                      dataKey="v"
                      stroke={color}
                      strokeWidth={1.5}
                      fill={`url(#spark-${ticker})`}
                      dot={false}
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* 52w range bar */}
            <div className="mb-2">
              <div className="flex justify-between text-xs text-gray-400 mb-1">
                <span>{formatPrice(q.week52_low)}</span>
                <span className="text-gray-500 font-medium">52w</span>
                <span>{formatPrice(q.week52_high)}</span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full relative">
                <div
                  className="absolute top-0 left-0 h-full rounded-full"
                  style={{ width: `${pricePct}%`, backgroundColor: color, opacity: 0.6 }}
                />
                <div
                  className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full border-2 border-white"
                  style={{ left: `${pricePct}%`, backgroundColor: color, transform: 'translate(-50%, -50%)' }}
                />
              </div>
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-2 gap-x-4 text-xs text-gray-500 mt-3 pt-3 border-t border-gray-100">
              <div>Vol: <span className="text-gray-700 font-medium">{formatCompact(q.volume)}</span></div>
              <div>MCap: <span className="text-gray-700 font-medium">{formatCompact(q.market_cap)}</span></div>
              <div>Hi: <span className="text-gray-700 font-medium">{formatPrice(q.day_high)}</span></div>
              <div>Lo: <span className="text-gray-700 font-medium">{formatPrice(q.day_low)}</span></div>
            </div>
          </div>
        );
      })}
    </div>
    </div>
  );
}
