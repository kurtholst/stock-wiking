import { useCallback, useEffect, useState } from 'react';
import {
  Radar, Clock, Loader2, Star, AlertTriangle, Compass, Globe2, Users, Gauge, Layers, Timer, Scale, Play, Brain,
} from 'lucide-react';
import type { AlphaDeepResponse, CompanyStarsResult, RunKind, StarsScanResponse } from '../types';
import { fetchLatestDeep, fetchLatestStars, fetchPartialDeep } from '../api';
import { useRunStatus } from '../useRunStatus';
import { AlphaDeep } from './AlphaDeep';
import { IpcCode } from './IpcCode';
import { AlertsPanel } from './AlertsPanel';
import { formatRunAt, timeAgo } from '../utils';

const OFFICES: Record<string, string> = {
  EP: 'European Patent Office', WO: 'PCT / WIPO (international)', US: 'United States', CN: 'China',
  JP: 'Japan', KR: 'South Korea', DK: 'Denmark', DE: 'Germany', GB: 'United Kingdom', AU: 'Australia',
  CA: 'Canada', IN: 'India', BR: 'Brazil', MX: 'Mexico', TW: 'Taiwan',
};

const GUIDE: { icon: typeof Compass; title: string; text: string }[] = [
  {
    icon: Compass,
    title: 'Entry into a new technology class',
    text: 'First filings in IPC subclasses the company has never used before (e.g. a pharma company filing in G16H health informatics or A61M devices). Often an early sign of a new product line, platform or pivot, months before it shows up in guidance.',
  },
  {
    icon: Layers,
    title: 'Change in concentration',
    text: 'The share of filings moves away from the core area. A broadening mix points to diversification or acquired IP. A sudden narrowing means the company is concentrating R&D on one programme, which often happens ahead of a pivotal trial or launch.',
  },
  {
    icon: Gauge,
    title: 'Filing velocity in the new area',
    text: 'One patent in a new class is noise. A cluster of 3+ related filings within a single quarter is a deliberate programme. Watch the acceleration, not the absolute count.',
  },
  {
    icon: Globe2,
    title: 'New filing offices (jurisdiction shift)',
    text: 'New WO/PCT filings show intent to protect internationally. First filings in US, CN, JP or KR usually precede market entry, local manufacturing or licensing deals. If a company drops an office, it may be exiting that market.',
  },
  {
    icon: Users,
    title: 'New co-applicants and applicant entities',
    text: 'Joint filings with universities, start-ups or large partners signal collaborations, JVs and M&A targets. A new subsidiary appearing as applicant often follows an acquisition or a carve-out.',
  },
  {
    icon: Timer,
    title: 'Mind the publication lag',
    text: 'Applications publish ~18 months after the priority date, so a "sudden" shift reflects decisions made 1.5-2 years ago. The alpha comes from the market not yet pricing those decisions, so compare with recent price action and analyst coverage.',
  },
  {
    icon: Scale,
    title: 'Confirm before acting',
    text: 'Cross-check against job postings in the new field, capex and R&D guidance, clinical-trial registries, partnership news and insider trades. Defensive filings, small samples and patents inherited through acquisitions can all produce false positives.',
  },
];

function pct(v: number | null | undefined): string {
  return v == null ? '-' : `${Math.round(v * 100)}%`;
}

function maxShift(c: CompanyStarsResult): number {
  const s = c.area_shift;
  if (!s) return -1;
  return Math.max(s.ipc_shift ?? -1, s.office_shift ?? -1);
}

function ShiftBar({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-gray-300 text-xs">n/a</span>;
  const color = value >= 0.4 ? 'bg-rose-500' : value >= 0.25 ? 'bg-amber-400' : 'bg-gray-300';
  return (
    <div className="flex items-center gap-2 justify-end">
      <div className="w-16 h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${Math.min(value, 1) * 100}%` }} />
      </div>
      <span className="font-mono text-xs text-gray-700 w-9 text-right">{pct(value)}</span>
    </div>
  );
}

function Stars({ n }: { n: number | null }) {
  if (n == null) return <span className="text-gray-300 text-xs">-</span>;
  return (
    <span className="inline-flex gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} size={12} className={i <= n ? 'fill-amber-400 text-amber-400' : 'text-gray-300'} />
      ))}
    </span>
  );
}

function Chip({ code, title, tone }: { code: string; title?: string; tone: 'new' | 'neutral' }) {
  const cls = tone === 'new' ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-gray-50 text-gray-600 border-gray-200';
  return (
    <span title={title} className={`inline-block px-1.5 py-0.5 mr-1 mb-0.5 rounded border text-[11px] font-mono cursor-help ${cls}`}>
      {code}
    </span>
  );
}

function Tile({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-2xl font-semibold text-gray-800 mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

export function AlphaSignals() {
  const [scan, setScan] = useState<StarsScanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deep, setDeep] = useState<AlphaDeepResponse | null>(null);
  const [quarters, setQuarters] = useState(8);
  const [focus] = useState(() => new URLSearchParams(window.location.search).get('focus'));

  const load = useCallback((kind?: RunKind | null) => {
    if (kind !== 'deep') {
      fetchLatestStars()
        .then(setScan)
        .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
        .finally(() => setLoading(false));
    }
    if (kind !== 'stars') fetchLatestDeep().then(setDeep).catch(() => {});
  }, []);

  useEffect(() => load(), [load]);

  const { status, busy, start, startError } = useRunStatus((kind) => {
    setLiveDeep(null);
    load(kind);
  });

  // While a deep run is going, show its results as they arrive
  const [liveDeep, setLiveDeep] = useState<AlphaDeepResponse | null>(null);
  const deepRunning = busy && (status?.kind === 'deep' || !!status?.external_running);
  useEffect(() => {
    if (!deepRunning) return;
    const poll = () => fetchPartialDeep().then((p) => p && setLiveDeep(p)).catch(() => {});
    poll();
    const id = setInterval(poll, 10_000);
    return () => clearInterval(id);
  }, [deepRunning]);
  const progressPct = status?.total ? Math.round(((status.step + 0.5) / status.total) * 100) : 5;

  const companies = scan?.companies ?? [];
  const withShift = companies.filter((c) => c.area_shift);
  const flagged = withShift.filter((c) => c.area_shift!.flagged);
  const highStars = companies.filter((c) => (c.stars ?? 0) >= 4);
  const candidates = companies.filter((c) => (c.stars ?? 0) >= 4 && c.area_shift?.flagged);
  const shiftRows = [...withShift].sort((a, b) => maxShift(b) - maxShift(a));

  const sectors = Object.values(
    companies.reduce<Record<string, { sector: string; n: number; patents: number; starSum: number; rated: number; strong: number; shifts: number }>>(
      (acc, c) => {
        const s = (acc[c.sector] ??= { sector: c.sector, n: 0, patents: 0, starSum: 0, rated: 0, strong: 0, shifts: 0 });
        s.n += 1;
        s.patents += c.patent_count;
        if (c.stars != null) { s.starSum += c.stars; s.rated += 1; }
        if (c.ai_signal === 'STRONG') s.strong += 1;
        if (c.area_shift?.flagged) s.shifts += 1;
        return acc;
      },
      {},
    ),
  ).sort((a, b) => b.patents - a.patents);

  const signalCounts = ['STRONG', 'MODERATE', 'WEAK', 'NONE'].map((sig) => ({
    sig,
    n: companies.filter((c) => (c.ai_signal ?? 'NONE') === sig).length,
  }));

  return (
    <div className="space-y-4 max-w-6xl">
      {/* Header + last run */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-wrap items-center gap-3">
        <Radar size={20} className="text-rose-500" />
        <div>
          <h2 className="text-base font-semibold text-gray-800">Alpha-signals</h2>
          <p className="text-xs text-gray-500">Patent submission-area shifts and an aggregate view of the latest Stars scan</p>
        </div>
        <div className="ml-auto flex items-center gap-2 text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
          <Clock size={14} className="text-gray-400" />
          {loading ? (
            <span>Loading...</span>
          ) : scan?.run_at ? (
            <span>
              Stars last run: <strong>{formatRunAt(scan.run_at)}</strong> ({timeAgo(scan.run_at)},{' '}
              {scan.trigger === 'scheduled' ? 'scheduled' : 'manual'}, {scan.period_days}-day window)
            </span>
          ) : scan ? (
            <span>Stars last run: <strong>{scan.scan_date}</strong></span>
          ) : (
            <span>Stars has not run yet. Scheduled daily at 06:00 (Copenhagen).</span>
          )}
        </div>
      </div>

      {/* Run controls */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => start('stars', { period_days: scan?.period_days ?? 90 })}
            disabled={busy}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-amber-500 rounded-lg hover:bg-amber-600 disabled:opacity-50 transition-colors"
          >
            <Play size={15} />
            Run Stars now
          </button>
          <div className="flex items-center gap-2">
            <button
              onClick={() => start('deep', { quarters })}
              disabled={busy}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-violet-600 rounded-lg hover:bg-violet-700 disabled:opacity-50 transition-colors"
              title="Multi-quarter patent history, co-applicants, velocity, price context and AI theses (Gemini Flash with a large thinking budget, free tier)"
            >
              <Brain size={15} />
              Deep analysis
            </button>
            <select
              value={quarters}
              onChange={(e) => setQuarters(Number(e.target.value))}
              disabled={busy}
              className="px-2 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
            >
              <option value={4}>4 quarters (~20 min)</option>
              <option value={8}>8 quarters (~40 min)</option>
              <option value={12}>12 quarters (~60 min)</option>
            </select>
          </div>
          <p className="text-xs text-gray-400 ml-auto">Scheduled: Stars daily 06:00, deep analysis Sundays 07:00</p>
        </div>

        {busy && status && (
          <div className="mt-3">
            <div className="flex items-center gap-2 text-xs text-gray-600 mb-1">
              <Loader2 size={13} className="animate-spin text-violet-500" />
              {status.external_running ? (
                <span>A scheduled run is in progress on the server...</span>
              ) : (
                <span>
                  {status.kind === 'deep' ? 'Deep analysis' : 'Stars scan'}: {status.message}
                  {status.total > 0 && ` (step ${status.step + 1}/${status.total})`}
                  {status.elapsed_s != null && `, ${Math.floor(status.elapsed_s / 60)}m ${status.elapsed_s % 60}s elapsed`}
                </span>
              )}
            </div>
            {!status.external_running && (
              <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                <div className={`h-full transition-all ${status.kind === 'deep' ? 'bg-violet-500' : 'bg-amber-400'}`} style={{ width: `${progressPct}%` }} />
              </div>
            )}
          </div>
        )}
        {status?.status === 'error' && !busy && (
          <p className="mt-2 text-xs text-red-600">Last {status.kind} run failed: {status.error}</p>
        )}
        {startError && <p className="mt-2 text-xs text-red-600">{startError}</p>}
      </div>

      <AlertsPanel refreshKey={`${scan?.run_at}-${deep?.finished_at}`} />

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl p-3">{error}</div>
      )}

      {loading && (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <Loader2 size={28} className="mx-auto text-rose-500 animate-spin" />
        </div>
      )}

      {!loading && scan && (
        <>
          {/* KPI tiles */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Tile label="Companies scanned" value={companies.length} sub={`${scan.period_days}-day window`} />
            <Tile label="Patents published" value={scan.total_patents} sub="in the scan window" />
            <Tile label="Rated 4-5 stars" value={highStars.length} sub={highStars.map((c) => c.name).slice(0, 3).join(', ') || '-'} />
            <Tile label="Area shifts flagged" value={flagged.length} sub={`of ${withShift.length} with enough history`} />
          </div>

          {/* Alpha candidates */}
          <div className="bg-gradient-to-r from-rose-50 to-amber-50 border border-rose-200 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle size={16} className="text-rose-500" />
              <h3 className="text-sm font-semibold text-gray-800">Alpha candidates: high Stars rating + submission-area shift</h3>
            </div>
            {candidates.length === 0 ? (
              <p className="text-sm text-gray-600">
                No company combines 4-5 stars with a flagged area shift in this scan.
                {flagged.length > 0 && ` Flagged shifts: ${flagged.map((c) => c.name).join(', ')}.`}
              </p>
            ) : (
              <ul className="space-y-1.5">
                {candidates.map((c) => (
                  <li key={c.ticker} className="text-sm text-gray-700 flex flex-wrap items-center gap-2">
                    <span className="font-medium">{c.name}</span>
                    <span className="text-xs text-gray-400">{c.ticker}</span>
                    <Stars n={c.stars} />
                    <span className="text-xs text-gray-500">
                      tech shift {pct(c.area_shift!.ipc_shift)}, office shift {pct(c.area_shift!.office_shift)}
                      {c.area_shift!.new_ipc.length > 0 && <>, new: {c.area_shift!.new_ipc.map((code) => <IpcCode key={code} code={code} tone="new" />)}</>}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Shift radar table */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200">
              <h3 className="text-sm font-semibold text-gray-800">Submission-area shift radar</h3>
              <p className="text-xs text-gray-500 mt-0.5">
                Patent mix in the {scan.period_days}-day scan window vs. the 12 months before it. Shift = total variation
                distance (0% = same mix, 100% = completely new areas). Flagged at 40% or more, with at least 3 recent and 5 baseline patents.
              </p>
            </div>
            {shiftRows.length === 0 ? (
              <p className="p-4 text-sm text-gray-500">
                This scan has no shift data. It was run before shift detection was added, so it will appear after the next Stars run.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200 text-xs">
                    <th className="text-left px-4 py-2 font-medium text-gray-600">Company</th>
                    <th className="text-left px-3 py-2 font-medium text-gray-600">Stars</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">Recent / base</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">Tech shift</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">Office shift</th>
                    <th className="text-left px-3 py-2 font-medium text-gray-600">Top IPC before → now</th>
                    <th className="text-left px-3 py-2 font-medium text-gray-600">New areas / offices</th>
                    <th className="text-right px-4 py-2 font-medium text-gray-600">1D %</th>
                  </tr>
                </thead>
                <tbody>
                  {shiftRows.map((c) => {
                    const s = c.area_shift!;
                    return (
                      <tr
                        key={c.ticker}
                        id={`shift-${c.ticker}`}
                        className={`border-b border-gray-100 ${c.ticker === focus ? 'bg-amber-50 ring-1 ring-inset ring-amber-300' : s.flagged ? 'bg-rose-50/50' : ''}`}
                      >
                        <td className="px-4 py-2">
                          <span className="font-medium text-gray-800">{c.name}</span>
                          <span className="text-xs text-gray-400 ml-2">{c.sector}</span>
                          {s.data_complete === false && (
                            <span title="Some EPO lookups failed - counts are lower bounds" className="ml-1 text-amber-500">
                              <AlertTriangle size={12} className="inline" />
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2"><Stars n={c.stars} /></td>
                        <td className="px-3 py-2 text-right font-mono text-xs text-gray-600">{s.recent_count} / {s.baseline_count}</td>
                        <td className="px-3 py-2"><ShiftBar value={s.ipc_shift} /></td>
                        <td className="px-3 py-2"><ShiftBar value={s.office_shift} /></td>
                        <td className="px-3 py-2 text-xs">
                          {s.top_ipc_baseline.map((code) => <IpcCode key={code} code={code} />)}
                          {(s.top_ipc_baseline.length > 0 || s.top_ipc_recent.length > 0) && <span className="text-gray-300 mx-1">→</span>}
                          {s.top_ipc_recent.map((code) => <IpcCode key={code} code={code} />)}
                        </td>
                        <td className="px-3 py-2 text-xs">
                          {s.new_ipc.map((code) => <IpcCode key={code} code={code} tone="new" />)}
                          {s.new_offices.map((o) => <Chip key={o} code={o} title={OFFICES[o] ?? o} tone="new" />)}
                          {s.new_ipc.length === 0 && s.new_offices.length === 0 && <span className="text-gray-300">-</span>}
                        </td>
                        <td className={`px-4 py-2 text-right font-mono text-xs ${
                          (c.stock_change_pct ?? 0) >= 0 ? 'text-emerald-600' : 'text-red-600'
                        }`}>
                          {c.stock_change_pct != null ? `${c.stock_change_pct >= 0 ? '+' : ''}${c.stock_change_pct.toFixed(2)}%` : '-'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* Stars aggregation */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-200">
                <h3 className="text-sm font-semibold text-gray-800">Stars by sector</h3>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200 text-xs">
                    <th className="text-left px-4 py-2 font-medium text-gray-600">Sector</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">Companies</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">Patents</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">Avg stars</th>
                    <th className="text-right px-3 py-2 font-medium text-gray-600">STRONG</th>
                    <th className="text-right px-4 py-2 font-medium text-gray-600">Shifts</th>
                  </tr>
                </thead>
                <tbody>
                  {sectors.map((s) => (
                    <tr key={s.sector} className="border-b border-gray-100">
                      <td className="px-4 py-2 text-gray-700">{s.sector}</td>
                      <td className="px-3 py-2 text-right font-mono text-gray-600">{s.n}</td>
                      <td className="px-3 py-2 text-right font-mono text-gray-600">{s.patents}</td>
                      <td className="px-3 py-2 text-right font-mono text-gray-600">{s.rated ? (s.starSum / s.rated).toFixed(1) : '-'}</td>
                      <td className="px-3 py-2 text-right font-mono text-gray-600">{s.strong || '-'}</td>
                      <td className="px-4 py-2 text-right font-mono text-gray-600">{s.shifts || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <h3 className="text-sm font-semibold text-gray-800 mb-3">AI signal distribution</h3>
              <div className="space-y-2">
                {signalCounts.map(({ sig, n }) => (
                  <div key={sig} className="flex items-center gap-2 text-xs">
                    <span className="w-20 text-gray-600">{sig}</span>
                    <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
                      <div
                        className={sig === 'STRONG' ? 'h-full bg-amber-400' : sig === 'MODERATE' ? 'h-full bg-blue-400' : 'h-full bg-gray-300'}
                        style={{ width: `${companies.length ? (n / companies.length) * 100 : 0}%` }}
                      />
                    </div>
                    <span className="w-6 text-right font-mono text-gray-700">{n}</span>
                  </div>
                ))}
              </div>
              {scan.summary && (
                <p className="text-xs text-gray-600 leading-relaxed mt-4 pt-3 border-t border-gray-100">{scan.summary}</p>
              )}
            </div>
          </div>
        </>
      )}

      {!loading && !scan && !error && (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-sm text-gray-500">
          No Stars data yet. Run a scan in the Stars tab or wait for the scheduled run.
        </div>
      )}

      {!loading && <AlphaDeep deep={deepRunning && liveDeep ? liveDeep : deep} focus={focus} />}

      {/* Signal guide */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-800">What to look for when a company suddenly changes its patent submission area</h3>
        <p className="text-xs text-gray-500 mt-0.5 mb-4">
          A change in where and in what a company files patents is one of the earliest public traces of strategy. It is useful when the market has not noticed it yet.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {GUIDE.map(({ icon: Icon, title, text }) => (
            <div key={title} className="flex gap-3">
              <Icon size={18} className="text-rose-500 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-gray-800">{title}</p>
                <p className="text-xs text-gray-600 leading-relaxed mt-0.5">{text}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 pt-3 border-t border-gray-100 text-xs text-gray-500 leading-relaxed">
          <strong className="text-gray-700">Strongest setups:</strong> a 4-5 star company whose new filings cluster in a class adjacent
          to a large addressable market, filed in new offices (WO + US/CN), with a flat or negative share price. A shift with
          low stars and few filings is usually noise. A high-stars company with no shift means its existing strategy is being executed, not a new one.
        </div>
      </div>
    </div>
  );
}
