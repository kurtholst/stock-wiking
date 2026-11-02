import { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';
import type { DkptoSearchResponse } from '../types';
import { searchDkptoPatents } from '../api';

const DATE_RANGES = [
  { label: 'Seneste 1 aar', from: () => String(new Date().getFullYear() - 1), to: () => String(new Date().getFullYear()) },
  { label: 'Seneste 2 aar', from: () => String(new Date().getFullYear() - 2), to: () => String(new Date().getFullYear()) },
  { label: 'Seneste 5 aar', from: () => String(new Date().getFullYear() - 5), to: () => String(new Date().getFullYear()) },
  { label: 'Alle', from: () => undefined, to: () => undefined },
];

export function DkptoSearch() {
  const [applicant, setApplicant] = useState('');
  const [title, setTitle] = useState('');
  const [ipc, setIpc] = useState('');
  const [dateRangeIdx, setDateRangeIdx] = useState(1);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DkptoSearchResponse | null>(null);

  const canSearch = applicant.trim() || title.trim() || ipc.trim();

  const handleSearch = async () => {
    if (!canSearch || loading) return;

    setLoading(true);
    setResult(null);

    try {
      const range = DATE_RANGES[dateRangeIdx];
      const res = await searchDkptoPatents({
        applicant: applicant.trim() || undefined,
        title: title.trim() || undefined,
        ipc: ipc.trim() || undefined,
        date_from: range.from(),
        date_to: range.to(),
      });
      setResult(res);
    } catch {
      setResult({
        patents: [],
        total_found: 0,
        source: 'EPO Espacenet (DK)',
        error: 'Soegningen fejlede. Proev igen.',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Search form */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 font-medium mb-1">Ansoeger (applicant)</label>
            <input
              type="text"
              value={applicant}
              onChange={(e) => setApplicant(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="f.eks. Novo Nordisk, Vestas..."
              className="w-full px-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 font-medium mb-1">Titel (title keywords)</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="f.eks. insulin, wind turbine..."
              className="w-full px-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="flex gap-4 mt-3 items-end">
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 font-medium">IPC-klasse:</label>
            <input
              type="text"
              value={ipc}
              onChange={(e) => setIpc(e.target.value)}
              placeholder="f.eks. A61K"
              className="w-28 px-3 py-1.5 text-xs border border-gray-200 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 font-medium">Periode:</label>
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
          <button
            onClick={handleSearch}
            disabled={loading || !canSearch}
            className="ml-auto px-5 py-2.5 bg-blue-500 text-white text-sm font-medium rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            Soeg danske patenter
          </button>
        </div>
      </div>

      {/* Error */}
      {result?.error && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-3 text-sm text-amber-800">
          {result.error}
        </div>
      )}

      {/* Results header */}
      {result && result.patents.length > 0 && (
        <div className="text-sm text-gray-600">
          <span className="font-semibold text-gray-800">{result.total_found}</span> danske patenter fundet
          <span className="text-xs text-gray-400 ml-2">({result.source})</span>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="bg-white rounded-xl border border-gray-200 flex flex-col items-center justify-center py-20">
          <Loader2 size={32} className="animate-spin text-blue-500 mb-3" />
          <p className="text-sm text-gray-500">Soeger i danske patenter...</p>
        </div>
      )}

      {/* Results table */}
      {result && result.patents.length > 0 && !loading && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-28">Dato</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-36">Patent nr.</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Titel</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-48">Ansoeger</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {result.patents.map((p, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-2 text-xs text-gray-500 font-mono">{p.date || '-'}</td>
                  <td className="px-4 py-2 text-xs text-blue-600 font-mono">{p.patent_number}</td>
                  <td className="px-4 py-2 text-gray-700">{p.title}</td>
                  <td className="px-4 py-2 text-xs text-gray-500">{p.applicant}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty state */}
      {!result && !loading && (
        <div className="bg-white rounded-xl border border-gray-200 flex flex-col items-center justify-center py-20">
          <Search size={40} className="text-gray-200 mb-3" />
          <p className="text-sm text-gray-500 max-w-md text-center">
            Soeg i danske patenter via EPO Espacenet. Udfyld mindst et felt ovenfor - ansoeger, titel eller IPC-klasse.
          </p>
          <div className="flex flex-wrap justify-center gap-2 mt-4">
            {['Novo Nordisk', 'Vestas', 'Coloplast', 'Lundbeck'].map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => setApplicant(suggestion)}
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
