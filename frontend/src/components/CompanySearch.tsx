import { useState } from 'react';
import { Search, Loader2, Sparkles, ChevronDown, ChevronRight } from 'lucide-react';
import type { DiscoverResponse, CompanyPatents, CompanyRanking, DiscoverAnalyzeResponse } from '../types';
import { discoverPatents, analyzeDiscovery } from '../api';

const DATE_RANGES = [
  { label: 'Last 1 year', from: () => String(new Date().getFullYear() - 1), to: () => String(new Date().getFullYear()) },
  { label: 'Last 2 years', from: () => String(new Date().getFullYear() - 2), to: () => String(new Date().getFullYear()) },
  { label: 'Last 5 years', from: () => String(new Date().getFullYear() - 5), to: () => String(new Date().getFullYear()) },
  { label: 'All time', from: () => undefined, to: () => undefined },
];

const SCORE_STYLES: Record<string, string> = {
  'STRONG BUY': 'bg-blue-100 text-blue-700 font-semibold',
  'INTERESTING': 'bg-emerald-100 text-emerald-700',
  'NEUTRAL': 'bg-gray-100 text-gray-600',
  'WEAK': 'bg-amber-100 text-amber-700',
};

export function CompanySearch() {
  const [query, setQuery] = useState('');
  const [ipc, setIpc] = useState('');
  const [dateRangeIdx, setDateRangeIdx] = useState(1); // default: last 2 years
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DiscoverResponse | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<DiscoverAnalyzeResponse | null>(null);
  const [expandedCompany, setExpandedCompany] = useState<string | null>(null);

  const handleSearch = async () => {
    const q = query.trim();
    if (!q || loading) return;

    setLoading(true);
    setResult(null);
    setAnalysis(null);
    setExpandedCompany(null);

    try {
      const range = DATE_RANGES[dateRangeIdx];
      const res = await discoverPatents({
        query: q,
        ipc: ipc.trim() || undefined,
        date_from: range.from(),
        date_to: range.to(),
      });
      setResult(res);
    } catch {
      setResult({
        query: q,
        companies: [],
        total_patents: 0,
        source: 'EPO Espacenet',
        error: 'Soegningen fejlede. Proev igen.',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async () => {
    if (!result || result.companies.length === 0 || analyzing) return;
    setAnalyzing(true);
    try {
      const res = await analyzeDiscovery({
        query: result.query,
        companies: result.companies,
      });
      setAnalysis(res);
    } catch {
      setAnalysis(null);
    } finally {
      setAnalyzing(false);
    }
  };

  const getRanking = (company: string): CompanyRanking | undefined => {
    return analysis?.rankings.find((r) => r.company === company);
  };

  const toggleExpand = (company: string) => {
    setExpandedCompany(expandedCompany === company ? null : company);
  };

  return (
    <div className="space-y-4">
      {/* Search bar */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="flex gap-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search technology keywords (e.g. solid state battery, GLP-1, quantum computing)..."
            className="flex-1 px-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            className="px-5 py-2.5 bg-blue-500 text-white text-sm font-medium rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            Search
          </button>
        </div>

        {/* Filters row */}
        <div className="flex gap-4 mt-3 items-center">
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 font-medium">IPC Class:</label>
            <input
              type="text"
              value={ipc}
              onChange={(e) => setIpc(e.target.value)}
              placeholder="e.g. H01M"
              className="w-28 px-3 py-1.5 text-xs border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 font-medium">Period:</label>
            <select
              value={dateRangeIdx}
              onChange={(e) => setDateRangeIdx(Number(e.target.value))}
              className="px-3 py-1.5 text-xs border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-400"
            >
              {DATE_RANGES.map((r, i) => (
                <option key={i} value={i}>{r.label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Error */}
      {result?.error && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-3 text-sm text-amber-800">
          {result.error}
        </div>
      )}

      {/* Results header + AI button */}
      {result && result.companies.length > 0 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600">
            <span className="font-semibold text-gray-800">{result.total_patents}</span> patents found for{' '}
            <span className="font-semibold text-gray-800">"{result.query}"</span>
            {' - '}{result.companies.length} companies
            <span className="text-xs text-gray-400 ml-2">({result.source})</span>
          </div>
          <button
            onClick={handleAnalyze}
            disabled={analyzing || !!analysis}
            className="px-4 py-2 bg-purple-500 text-white text-sm font-medium rounded-lg hover:bg-purple-600 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {analyzing ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
            {analysis ? 'Ranked' : 'Rank with AI'}
          </button>
        </div>
      )}

      {/* AI Summary */}
      {analysis && (
        <div className="bg-purple-50 border border-purple-200 rounded-xl px-5 py-4">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles size={16} className="text-purple-600" />
            <h3 className="text-sm font-semibold text-purple-800">AI Investment Summary</h3>
            <span className="text-xs text-purple-400 ml-auto">{analysis.model}</span>
          </div>
          <p className="text-sm text-purple-900 leading-relaxed">{analysis.summary}</p>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="bg-white rounded-xl border border-gray-200 flex flex-col items-center justify-center py-20">
          <Loader2 size={32} className="animate-spin text-blue-500 mb-3" />
          <p className="text-sm text-gray-500">Searching EPO patent database...</p>
        </div>
      )}

      {/* Company results table */}
      {result && result.companies.length > 0 && !loading && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-8"></th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Company</th>
                <th className="px-4 py-2.5 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Patents</th>
                {analysis && (
                  <th className="px-4 py-2.5 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Score</th>
                )}
                <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Key Patents</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {result.companies.map((c: CompanyPatents) => {
                const ranking = getRanking(c.company);
                const isExpanded = expandedCompany === c.company;

                return (
                  <tr key={c.company} className="group">
                    <td colSpan={analysis ? 5 : 4} className="p-0">
                      {/* Main row */}
                      <div
                        className="flex items-center cursor-pointer hover:bg-gray-50 px-4 py-2.5"
                        onClick={() => toggleExpand(c.company)}
                      >
                        <div className="w-8 shrink-0">
                          {isExpanded
                            ? <ChevronDown size={14} className="text-gray-400" />
                            : <ChevronRight size={14} className="text-gray-400" />
                          }
                        </div>
                        <div className="flex-1 font-medium text-gray-800">{c.company}</div>
                        <div className="w-20 text-right tabular-nums text-gray-700 font-medium">{c.patent_count}</div>
                        {analysis && (
                          <div className="w-28 text-center">
                            {ranking ? (
                              <span className={`inline-block px-2 py-0.5 rounded text-xs ${SCORE_STYLES[ranking.score] ?? 'bg-gray-100 text-gray-600'}`}>
                                {ranking.score}
                              </span>
                            ) : (
                              <span className="text-gray-300 text-xs">--</span>
                            )}
                          </div>
                        )}
                        <div className="flex-1 text-gray-500 text-xs truncate ml-4">
                          {c.sample_patents.slice(0, 2).map((p) => p.title).join(' | ')}
                        </div>
                      </div>

                      {/* Expanded details */}
                      {isExpanded && (
                        <div className="bg-gray-50 px-12 py-3 border-t border-gray-100">
                          {ranking?.reasoning && (
                            <p className="text-sm text-purple-800 mb-3 italic">{ranking.reasoning}</p>
                          )}
                          <div className="space-y-1.5">
                            {c.sample_patents.map((p, i) => (
                              <div key={i} className="flex items-baseline gap-3 text-xs">
                                <span className="text-gray-400 font-mono shrink-0">{p.patent_number}</span>
                                <span className="text-gray-700">{p.title}</span>
                                {p.date && <span className="text-gray-400 shrink-0">{p.date}</span>}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty state */}
      {!result && !loading && (
        <div className="bg-white rounded-xl border border-gray-200 flex flex-col items-center justify-center py-20">
          <Search size={40} className="text-gray-200 mb-3" />
          <p className="text-sm text-gray-400">Search by technology keyword to discover which companies are filing patents</p>
          <div className="flex flex-wrap justify-center gap-2 mt-4">
            {['solid state battery', 'GLP-1', 'quantum computing', 'carbon capture'].map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => { setQuery(suggestion); }}
                className="text-xs px-3 py-1.5 bg-gray-100 text-gray-600 rounded-full hover:bg-gray-200 transition-colors"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
