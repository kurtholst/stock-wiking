import { useEffect, useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, Loader2 } from 'lucide-react';
import type { RankRow } from '../types';
import { fetchRank } from '../api';
import { formatPrice, formatPct, getTickerColor } from '../utils';

type SortKey = keyof RankRow;

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'ticker', label: 'Ticker' },
  { key: 'price', label: 'Price' },
  { key: 'change_1d', label: '1D %' },
  { key: 'change_1w', label: '1W %' },
  { key: 'change_1m', label: '1M %' },
  { key: 'change_3m', label: '3M %' },
  { key: 'rsi14', label: 'RSI 14' },
  { key: 'macd_hist', label: 'MACD Hist' },
  { key: 'bb_pct', label: 'BB %B' },
  { key: 'ma20_dist', label: 'MA 20 %' },
  { key: 'ma50_dist', label: 'MA 50 %' },
  { key: 'ma200_dist', label: 'MA 200 %' },
  { key: 'vol_ratio', label: 'Vol Ratio' },
  { key: 'atr14', label: 'ATR 14' },
];

interface Props {
  tickers: string[];
}

export function RankTable({ tickers }: Props) {
  const [data, setData] = useState<RankRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>('ticker');
  const [sortAsc, setSortAsc] = useState(true);

  useEffect(() => {
    if (tickers.length === 0) return;
    setLoading(true);
    fetchRank(tickers)
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [tickers]);

  const sorted = useMemo(() => {
    return [...data].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === 'string' && typeof bv === 'string')
        return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      return sortAsc ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
  }, [data, sortKey, sortAsc]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortKey !== col) return <ArrowUpDown size={12} className="text-gray-300" />;
    return sortAsc ? <ArrowUp size={12} /> : <ArrowDown size={12} />;
  };

  const pctColor = (v: number | null) => {
    if (v == null) return 'text-gray-300';
    return v >= 0 ? 'text-green-600' : 'text-red-600';
  };

  const rsiColor = (v: number | null) => {
    if (v == null) return 'text-gray-300';
    if (v >= 70) return 'text-red-600 font-semibold';
    if (v <= 30) return 'text-green-600 font-semibold';
    return 'text-gray-700';
  };

  const bbColor = (v: number | null) => {
    if (v == null) return 'text-gray-300';
    if (v >= 100) return 'text-red-600 font-semibold';
    if (v <= 0) return 'text-green-600 font-semibold';
    return 'text-gray-700';
  };

  const renderCell = (row: RankRow, col: SortKey) => {
    const v = row[col];
    switch (col) {
      case 'ticker':
        return (
          <div className="flex items-center gap-1.5">
            <div
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: getTickerColor(row.ticker, tickers.indexOf(row.ticker)) }}
            />
            <span className="font-medium text-gray-800">{row.ticker}</span>
          </div>
        );
      case 'price':
        return <span className="font-medium text-gray-900 tabular-nums">{formatPrice(v as number)}</span>;
      case 'change_1d':
      case 'change_1w':
      case 'change_1m':
      case 'change_3m':
        return v == null
          ? <span className="text-gray-300">--</span>
          : <span className={pctColor(v as number)}>{formatPct(v as number)}</span>;
      case 'rsi14':
        return v == null
          ? <span className="text-gray-300">--</span>
          : <span className={rsiColor(v as number)}>{(v as number).toFixed(1)}</span>;
      case 'macd_hist':
        return v == null
          ? <span className="text-gray-300">--</span>
          : <span className={pctColor(v as number)}>{(v as number).toFixed(4)}</span>;
      case 'bb_pct':
        return v == null
          ? <span className="text-gray-300">--</span>
          : <span className={bbColor(v as number)}>{(v as number).toFixed(1)}%</span>;
      case 'ma20_dist':
      case 'ma50_dist':
      case 'ma200_dist':
        return v == null
          ? <span className="text-gray-300">--</span>
          : <span className={pctColor(v as number)}>{formatPct(v as number)}</span>;
      case 'vol_ratio':
        return v == null
          ? <span className="text-gray-300">--</span>
          : <span className={`tabular-nums ${(v as number) >= 1.5 ? 'text-blue-600 font-semibold' : 'text-gray-700'}`}>{(v as number).toFixed(2)}x</span>;
      case 'atr14':
        return v == null
          ? <span className="text-gray-300">--</span>
          : <span className="text-gray-700 tabular-nums">{(v as number).toFixed(2)}</span>;
      default:
        return <span className="text-gray-700">{String(v)}</span>;
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <h2 className="text-sm font-semibold text-gray-700">Rank Overview</h2>
        {loading && <Loader2 size={16} className="animate-spin text-blue-500" />}
        <span className="text-xs text-gray-400 ml-auto">{sorted.length} tickers</span>
      </div>

      {loading && data.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 flex flex-col items-center justify-center py-20">
          <Loader2 size={32} className="animate-spin text-blue-500 mb-3" />
          <p className="text-sm text-gray-500">Computing indicators for {tickers.length} tickers...</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  {COLUMNS.map(({ key, label }) => (
                    <th
                      key={key}
                      onClick={() => handleSort(key)}
                      className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700 select-none whitespace-nowrap"
                    >
                      <div className="flex items-center gap-1">
                        {label} <SortIcon col={key} />
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {sorted.map((row) => (
                  <tr key={row.ticker} className="hover:bg-gray-50">
                    {COLUMNS.map(({ key }) => (
                      <td key={key} className="px-4 py-2 whitespace-nowrap tabular-nums">
                        {renderCell(row, key)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
