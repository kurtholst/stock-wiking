import { useEffect, useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, Loader2 } from 'lucide-react';
import type { HistoryResponse, OHLCVRow } from '../types';
import { fetchHistory } from '../api';
import { formatPrice, formatPct, getTickerColor } from '../utils';

const PERIODS = ['5d', '1mo', '3mo', '6mo', '1y', '3y'] as const;

type SortKey = 'date' | 'ticker' | 'open' | 'high' | 'low' | 'close' | 'volume' | 'change_pct' | 'ma20' | 'ma50' | 'ma200';

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'date', label: 'date' },
  { key: 'ticker', label: 'ticker' },
  { key: 'open', label: 'open' },
  { key: 'high', label: 'high' },
  { key: 'low', label: 'low' },
  { key: 'close', label: 'close' },
  { key: 'change_pct', label: '% chg' },
  { key: 'volume', label: 'volume' },
  { key: 'ma20', label: 'ma 20' },
  { key: 'ma50', label: 'ma 50' },
  { key: 'ma200', label: 'ma 200' },
];

interface TableRow extends OHLCVRow {
  ticker: string;
}

interface Props {
  tickers: string[];
}

export function DataTable({ tickers }: Props) {
  const [period, setPeriod] = useState<string>('1mo');
  const [filterTicker, setFilterTicker] = useState<string>('all');
  const [data, setData] = useState<HistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>('date');
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    if (tickers.length === 0) return;
    setLoading(true);
    fetchHistory(tickers, period)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [tickers, period]);

  const rows: TableRow[] = useMemo(() => {
    if (!data) return [];
    const all: TableRow[] = [];
    for (const th of data.tickers) {
      for (const row of th.data) {
        all.push({ ...row, ticker: th.ticker });
      }
    }
    return all;
  }, [data]);

  const filtered = useMemo(() => {
    let result = filterTicker === 'all' ? rows : rows.filter((r) => r.ticker === filterTicker);
    result = [...result].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      // Nulls sort last
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === 'string' && typeof bv === 'string') return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      return sortAsc ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return result;
  }, [rows, filterTicker, sortKey, sortAsc]);

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

  const renderCell = (row: TableRow, col: SortKey) => {
    switch (col) {
      case 'date':
        return <span className="text-gray-600 whitespace-nowrap">{row.date}</span>;
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
      case 'change_pct': {
        if (row.change_pct == null) return <span className="text-gray-300">—</span>;
        const isUp = row.change_pct >= 0;
        return <span className={isUp ? 'text-green-600' : 'text-red-600'}>{formatPct(row.change_pct)}</span>;
      }
      case 'ma20':
      case 'ma50':
      case 'ma200': {
        const v = row[col];
        if (v == null) return <span className="text-gray-300">—</span>;
        return <span className="text-gray-600">{formatPrice(v)}</span>;
      }
      case 'volume':
        return <span className="text-gray-600 tabular-nums">{row.volume.toLocaleString()}</span>;
      case 'close':
        return <span className="font-medium text-gray-900 tabular-nums">{formatPrice(row.close)}</span>;
      default:
        return <span className="text-gray-700 tabular-nums">{formatPrice(row[col] as number)}</span>;
    }
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-4 flex-wrap">
        <select
          value={filterTicker}
          onChange={(e) => setFilterTicker(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="all">All Tickers</option>
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
        <span className="text-xs text-gray-400 ml-auto">{filtered.length} rows</span>
      </div>

      {/* Table */}
      {loading && filtered.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 flex flex-col items-center justify-center py-20">
          <Loader2 size={32} className="animate-spin text-blue-500 mb-3" />
          <p className="text-sm text-gray-500">Loading data for {tickers.length} tickers...</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
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
                {filtered.map((row, i) => (
                  <tr key={`${row.ticker}-${row.date}-${i}`} className="hover:bg-gray-50">
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
