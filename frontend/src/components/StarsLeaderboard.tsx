import { useState } from 'react';
import { Star, Loader2, ChevronDown, ChevronRight, Sparkles, TrendingUp, TrendingDown } from 'lucide-react';
import type { CompanyStarsResult, StarsScanResponse } from '../types';
import { runStarsScan } from '../api';

interface Props {
  onAddTicker: (ticker: string) => void;
}

function StarRating({ stars }: { stars: number | null }) {
  if (stars == null) return <span className="text-gray-300 text-xs">-</span>;
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          size={14}
          className={i <= stars ? 'fill-amber-400 text-amber-400' : 'text-gray-300'}
        />
      ))}
    </div>
  );
}

function SignalBadge({ signal }: { signal: string | null }) {
  if (!signal) return <span className="text-gray-300 text-xs">-</span>;
  const colors: Record<string, string> = {
    STRONG: 'bg-amber-100 text-amber-800 border-amber-200',
    MODERATE: 'bg-blue-100 text-blue-800 border-blue-200',
    WEAK: 'bg-gray-100 text-gray-600 border-gray-200',
    NONE: 'bg-gray-50 text-gray-400 border-gray-200',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${colors[signal] ?? colors.NONE}`}>
      {signal}
    </span>
  );
}

export function StarsLeaderboard({ onAddTicker }: Props) {
  const [periodDays, setPeriodDays] = useState(90);
  const [scanResult, setScanResult] = useState<StarsScanResponse | null>(null);
  const [scanning, setScanning] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const handleScan = async () => {
    setScanning(true);
    setScanResult(null);
    setExpandedRows(new Set());
    try {
      const result = await runStarsScan(periodDays);
      setScanResult(result);
    } catch (e) {
      setScanResult({
        scan_date: new Date().toISOString().split('T')[0],
        period_days: periodDays,
        companies: [],
        total_patents: 0,
        summary: e instanceof Error ? e.message : 'Scan fejlede',
        model: '',
      });
    } finally {
      setScanning(false);
    }
  };

  const toggleRow = (ticker: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(ticker)) next.delete(ticker);
      else next.add(ticker);
      return next;
    });
  };

  return (
    <div className="space-y-4 max-w-6xl">
      {/* Controls */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={periodDays}
            onChange={(e) => setPeriodDays(Number(e.target.value))}
            className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
          >
            <option value={30}>30 dage</option>
            <option value={60}>60 dage</option>
            <option value={90}>90 dage</option>
          </select>

          <button
            onClick={handleScan}
            disabled={scanning}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-amber-500 rounded-lg hover:bg-amber-600 disabled:opacity-50 transition-colors"
          >
            {scanning ? <Loader2 size={16} className="animate-spin" /> : <Star size={16} />}
            Scan danske patenter
          </button>

          {scanResult && (
            <div className="ml-auto flex items-center gap-2 text-xs text-gray-500">
              <span>Dato: {scanResult.scan_date}</span>
              <span className="text-gray-300">|</span>
              <span>{scanResult.total_patents} patenter fundet</span>
              {scanResult.model && (
                <>
                  <span className="text-gray-300">|</span>
                  <span>Model: {scanResult.model}</span>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* AI Market Summary */}
      {scanResult && scanResult.summary && (
        <div className="bg-gradient-to-r from-amber-50 to-yellow-50 border border-amber-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles size={16} className="text-amber-500" />
            <h3 className="text-sm font-semibold text-gray-800">Dansk patentmarked - AI-vurdering</h3>
          </div>
          <p className="text-sm text-gray-700 leading-relaxed">{scanResult.summary}</p>
        </div>
      )}

      {/* Leaderboard table */}
      {scanResult && scanResult.companies.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 font-medium text-gray-600 w-8">#</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600 w-8"></th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Stjerner</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Virksomhed</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Sektor</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">Patenter</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Signal</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">Kurs</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">1D %</th>
                <th className="text-center px-4 py-3 font-medium text-gray-600 w-8"></th>
              </tr>
            </thead>
            <tbody>
              {scanResult.companies.map((company, idx) => {
                const isExpanded = expandedRows.has(company.ticker);
                return (
                  <CompanyRow
                    key={company.ticker}
                    rank={idx + 1}
                    company={company}
                    isExpanded={isExpanded}
                    onToggle={() => toggleRow(company.ticker)}
                    onAddTicker={onAddTicker}
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty state */}
      {!scanResult && !scanning && (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <Star size={40} className="mx-auto mb-3 text-gray-300" />
          <p className="text-gray-500 text-sm">
            Klik "Scan danske patenter" for at analysere OMX Copenhagen-virksomheder
          </p>
          <p className="text-gray-400 text-xs mt-2">
            Scanner ~20 danske virksomheder for nylige patentansogninger og AI-vurderer dem
          </p>
        </div>
      )}

      {/* Loading state */}
      {scanning && (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <Loader2 size={32} className="mx-auto mb-3 text-amber-500 animate-spin" />
          <p className="text-gray-500 text-sm">Scanner danske virksomheder...</p>
          <p className="text-gray-400 text-xs mt-1">
            Henter patenter fra EPO, scorer med AI og beriger med aktiekurser.
            <br />
            Dette kan tage 1-2 minutter.
          </p>
        </div>
      )}
    </div>
  );
}

function CompanyRow({
  rank,
  company,
  isExpanded,
  onToggle,
  onAddTicker,
}: {
  rank: number;
  company: CompanyStarsResult;
  isExpanded: boolean;
  onToggle: () => void;
  onAddTicker: (ticker: string) => void;
}) {
  const hasDetails = company.ai_summary || company.recent_patents.length > 0;

  return (
    <>
      <tr
        className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors"
        onClick={onToggle}
      >
        <td className="px-4 py-3 text-gray-400 text-xs">{rank}</td>
        <td className="px-4 py-3 text-gray-400">
          {hasDetails ? (
            isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
          ) : (
            <span className="w-3.5" />
          )}
        </td>
        <td className="px-4 py-3"><StarRating stars={company.stars} /></td>
        <td className="px-4 py-3">
          <div>
            <span className="font-medium text-gray-800">{company.name}</span>
            <span className="text-xs text-gray-400 ml-2">{company.ticker}</span>
          </div>
        </td>
        <td className="px-4 py-3 text-gray-500 text-xs">{company.sector}</td>
        <td className="px-4 py-3 text-right font-mono text-gray-700">{company.patent_count}</td>
        <td className="px-4 py-3"><SignalBadge signal={company.ai_signal} /></td>
        <td className="px-4 py-3 text-right font-mono text-gray-700">
          {company.stock_price != null ? company.stock_price.toFixed(2) : '-'}
        </td>
        <td className="px-4 py-3 text-right">
          {company.stock_change_pct != null ? (
            <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${
              company.stock_change_pct >= 0 ? 'text-emerald-600' : 'text-red-600'
            }`}>
              {company.stock_change_pct >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              {company.stock_change_pct >= 0 ? '+' : ''}{company.stock_change_pct.toFixed(2)}%
            </span>
          ) : (
            <span className="text-gray-300 text-xs">-</span>
          )}
        </td>
        <td className="px-4 py-3 text-center">
          <button
            onClick={(e) => { e.stopPropagation(); onAddTicker(company.ticker); }}
            className="text-xs text-blue-500 hover:text-blue-700 font-medium"
            title="Tilfoej til portefolje"
          >
            +
          </button>
        </td>
      </tr>
      {isExpanded && hasDetails && (
        <tr className="bg-gray-50">
          <td></td>
          <td colSpan={9} className="px-4 py-3">
            {company.ai_summary && (
              <div className="flex items-start gap-2 mb-3">
                <Sparkles size={14} className="text-amber-500 shrink-0 mt-0.5" />
                <p className="text-sm text-gray-600 leading-relaxed">{company.ai_summary}</p>
              </div>
            )}
            {company.recent_patents.length > 0 && (
              <div className="mt-2">
                <p className="text-xs font-medium text-gray-500 mb-1">Nylige patenter:</p>
                <ul className="space-y-1">
                  {company.recent_patents.map((p) => (
                    <li key={p.patent_number} className="text-xs text-gray-600 flex gap-2">
                      <span className="font-mono text-gray-400 shrink-0">{p.patent_number}</span>
                      <span>{p.title}</span>
                      {p.publication_date && (
                        <span className="text-gray-400 shrink-0 ml-auto">{p.publication_date}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
