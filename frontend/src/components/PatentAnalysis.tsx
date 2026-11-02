import { useState } from 'react';
import { Search, Sparkles, Loader2, ChevronDown, ChevronRight, AlertTriangle, ExternalLink } from 'lucide-react';
import type { PatentResult, PatentScore, PatentSearchResponse, PatentAnalyzeResponse } from '../types';
import { fetchPatents, analyzePatents } from '../api';

interface Props {
  tickers: string[];
}

function ScoreBadge({ score }: { score: string }) {
  const colors: Record<string, string> = {
    POSITIVE: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    INSIGNIFICANT: 'bg-gray-100 text-gray-600 border-gray-200',
    NEGATIVE: 'bg-red-100 text-red-800 border-red-200',
  };
  const labels: Record<string, string> = {
    POSITIVE: 'Positiv',
    INSIGNIFICANT: 'Ubetydelig',
    NEGATIVE: 'Negativ',
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${colors[score] ?? colors.INSIGNIFICANT}`}>
      {labels[score] ?? score}
    </span>
  );
}

export function PatentAnalysis({ tickers }: Props) {
  const [selectedTicker, setSelectedTicker] = useState(tickers[0] ?? '');
  const [searchResult, setSearchResult] = useState<PatentSearchResponse | null>(null);
  const [analysisResult, setAnalysisResult] = useState<PatentAnalyzeResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const handleScan = async () => {
    if (!selectedTicker) return;
    setSearching(true);
    setSearchResult(null);
    setAnalysisResult(null);
    setExpandedRows(new Set());
    try {
      const result = await fetchPatents(selectedTicker);
      setSearchResult(result);
    } catch (e) {
      setSearchResult({
        ticker: selectedTicker,
        company_name: selectedTicker,
        patents: [],
        total_found: 0,
        source: 'EPO Espacenet',
        error: e instanceof Error ? e.message : 'Ukendt fejl',
      });
    } finally {
      setSearching(false);
    }
  };

  const handleAnalyze = async () => {
    if (!searchResult || searchResult.patents.length === 0) return;
    setAnalyzing(true);
    setAnalysisResult(null);
    try {
      const result = await analyzePatents({
        ticker: searchResult.ticker,
        company_name: searchResult.company_name,
        patents: searchResult.patents,
      });
      setAnalysisResult(result);
    } catch {
      setAnalysisResult({
        ticker: searchResult.ticker,
        company_name: searchResult.company_name,
        scores: [],
        summary: 'AI-analyse fejlede. Tjek at GEMINI_API_KEY er konfigureret.',
        model: 'gemini-2.5-flash',
      });
    } finally {
      setAnalyzing(false);
    }
  };

  const toggleRow = (patentNumber: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(patentNumber)) next.delete(patentNumber);
      else next.add(patentNumber);
      return next;
    });
  };

  // Build a lookup from patent_number -> score
  const scoreMap = new Map<string, PatentScore>();
  if (analysisResult) {
    for (const s of analysisResult.scores) {
      scoreMap.set(s.patent_number, s);
    }
  }

  return (
    <div className="space-y-4 max-w-5xl">
      {/* Controls bar */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={selectedTicker}
            onChange={(e) => setSelectedTicker(e.target.value)}
            className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {tickers.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>

          <button
            onClick={handleScan}
            disabled={searching || !selectedTicker}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-500 rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors"
          >
            {searching ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            Scan Patents
          </button>

          {searchResult && searchResult.patents.length > 0 && (
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-amber-500 rounded-lg hover:bg-amber-600 disabled:opacity-50 transition-colors"
            >
              {analyzing ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              Analyze with AI
            </button>
          )}

          {searchResult && (
            <div className="ml-auto flex items-center gap-2 text-xs text-gray-500">
              <span>Kilde: {searchResult.source}</span>
              <span className="text-gray-300">|</span>
              <span>{searchResult.total_found} patenter fundet</span>
            </div>
          )}
        </div>
      </div>

      {/* Error / warning */}
      {searchResult?.error && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex gap-3">
          <AlertTriangle size={20} className="text-amber-500 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-800">Patent-soegning begranset</p>
            <p className="text-sm text-amber-700 mt-1">{searchResult.error}</p>
            <a
              href="https://onlineweb.dkpto.dk/pvsonline/Patent"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-amber-600 hover:text-amber-800 mt-2"
            >
              Soeg manuelt pa DKPTO <ExternalLink size={12} />
            </a>
          </div>
        </div>
      )}

      {/* AI Summary */}
      {analysisResult && (
        <div className="bg-gradient-to-r from-amber-50 to-emerald-50 border border-amber-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles size={16} className="text-amber-500" />
            <h3 className="text-sm font-semibold text-gray-800">AI-vurdering</h3>
            <span className="text-xs text-gray-400 ml-auto">Model: {analysisResult.model}</span>
          </div>
          <p className="text-sm text-gray-700 leading-relaxed">{analysisResult.summary}</p>
        </div>
      )}

      {/* Patent results table */}
      {searchResult && searchResult.patents.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 font-medium text-gray-600 w-8"></th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Dato</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Patent nr.</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Titel</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">AI Score</th>
              </tr>
            </thead>
            <tbody>
              {searchResult.patents.map((patent: PatentResult, idx: number) => {
                const score = scoreMap.get(patent.patent_number);
                const isExpanded = expandedRows.has(patent.patent_number);
                return (
                  <PatentRow
                    key={patent.patent_number || idx}
                    patent={patent}
                    score={score}
                    isExpanded={isExpanded}
                    onToggle={() => toggleRow(patent.patent_number)}
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty state */}
      {!searchResult && !searching && (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <Search size={40} className="mx-auto mb-3 text-gray-300" />
          <p className="text-gray-500 text-sm">
            Vaelg en ticker og klik "Scan Patents" for at soege efter patentansogninger
          </p>
          <p className="text-gray-400 text-xs mt-2">
            Data hentes fra EPO Espacenet (European Patent Office)
          </p>
        </div>
      )}

      {/* Loading state */}
      {searching && (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <Loader2 size={32} className="mx-auto mb-3 text-blue-500 animate-spin" />
          <p className="text-gray-500 text-sm">Soeger patenter for {selectedTicker}...</p>
          <p className="text-gray-400 text-xs mt-1">Kontakter EPO Espacenet</p>
        </div>
      )}

      {analyzing && (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <Loader2 size={32} className="mx-auto mb-3 text-amber-500 animate-spin" />
          <p className="text-gray-500 text-sm">Analyserer patenter med AI...</p>
          <p className="text-gray-400 text-xs mt-1">Gemini 2.5 Flash vurderer investeringsrelevans</p>
        </div>
      )}
    </div>
  );
}

function PatentRow({
  patent,
  score,
  isExpanded,
  onToggle,
}: {
  patent: PatentResult;
  score?: PatentScore;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors"
        onClick={onToggle}
      >
        <td className="px-4 py-3 text-gray-400">
          {score ? (
            isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
          ) : (
            <span className="w-3.5" />
          )}
        </td>
        <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{patent.filing_date ?? '-'}</td>
        <td className="px-4 py-3 font-mono text-xs text-gray-700">{patent.patent_number}</td>
        <td className="px-4 py-3 text-gray-800">{patent.title}</td>
        <td className="px-4 py-3 text-gray-500">{patent.status ?? '-'}</td>
        <td className="px-4 py-3">
          {score ? <ScoreBadge score={score.score} /> : <span className="text-gray-300 text-xs">-</span>}
        </td>
      </tr>
      {isExpanded && score && (
        <tr className="bg-gray-50">
          <td></td>
          <td colSpan={5} className="px-4 py-3">
            <div className="flex items-start gap-2">
              <Sparkles size={14} className="text-amber-500 shrink-0 mt-0.5" />
              <p className="text-sm text-gray-600 leading-relaxed">{score.reasoning}</p>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
