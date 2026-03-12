import { useState } from 'react';
import { Plus, X, Loader2, AlertCircle } from 'lucide-react';
import type { QuoteData } from '../types';
import { validateTicker } from '../api';
import { formatPrice, formatPct, getTickerColor } from '../utils';

interface Props {
  tickers: string[];
  quotes: Map<string, QuoteData>;
  onAdd: (ticker: string) => void;
  onRemove: (ticker: string) => void;
}

export function TickerSidebar({ tickers, quotes, onAdd, onRemove }: Props) {
  const [input, setInput] = useState('');
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState('');

  const handleAdd = async () => {
    const ticker = input.trim().toUpperCase();
    if (!ticker || tickers.includes(ticker)) {
      setError(tickers.includes(ticker) ? 'Already added' : '');
      return;
    }
    setValidating(true);
    setError('');
    try {
      const result = await validateTicker(ticker);
      if (result.valid) {
        onAdd(ticker);
        setInput('');
      } else {
        setError('Invalid ticker');
      }
    } catch {
      setError('Validation failed');
    } finally {
      setValidating(false);
    }
  };

  return (
    <div className="p-4 space-y-4">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">Tickers</h2>

      {/* Add ticker */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => { setInput(e.target.value); setError(''); }}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
          placeholder="Add ticker..."
          className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={handleAdd}
          disabled={validating}
          className="p-1.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
        >
          {validating ? <Loader2 size={16} className="animate-spin" /> : <Plus size={16} />}
        </button>
      </div>
      {error && (
        <div className="flex items-center gap-1 text-xs text-red-500">
          <AlertCircle size={12} /> {error}
        </div>
      )}

      {/* Ticker badges */}
      <div className="space-y-2">
        {tickers.map((ticker, i) => {
          const q = quotes.get(ticker);
          const color = getTickerColor(ticker, i);
          return (
            <div key={ticker} className="flex items-center gap-2 p-2 bg-gray-50 rounded-lg group">
              <div className="w-1 h-8 rounded-full" style={{ backgroundColor: color }} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-800 truncate">{ticker}</div>
                {q ? (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-gray-600">{formatPrice(q.price)}</span>
                    <span className={q.change_pct >= 0 ? 'text-green-600' : 'text-red-600'}>
                      {formatPct(q.change_pct)}
                    </span>
                  </div>
                ) : (
                  <div className="text-xs text-gray-400">Loading...</div>
                )}
              </div>
              <button
                onClick={() => onRemove(ticker)}
                className="p-1 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-opacity"
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
