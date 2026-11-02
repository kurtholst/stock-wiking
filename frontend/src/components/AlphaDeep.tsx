import { Fragment, useState } from 'react';
import {
  Brain, ChevronDown, ChevronRight, Clock, Lightbulb, ShieldAlert, CheckCircle2, XCircle, Network, AlertTriangle,
  TrendingUp, TrendingDown, Minus, Loader2,
} from 'lucide-react';
import type { AlphaDeepResponse, DeepCompany } from '../types';
import { formatRunAt, timeAgo } from '../utils';
import { IpcCode } from './IpcCode';

const SCORE_PARTS: { key: string; label: string; max: number; tip: string }[] = [
  { key: 'shift', label: 'Mix shift', max: 25, tip: 'Technology-mix change, last 2 quarters vs. earlier quarters (x1.2 if accelerating)' },
  { key: 'novelty', label: 'New classes', max: 20, tip: 'IPC classes with 2+ recent patents and none before' },
  { key: 'velocity', label: 'Velocity', max: 15, tip: 'Recent quarterly filing rate vs. the baseline (doubling = full score)' },
  { key: 'international', label: 'New offices', max: 10, tip: 'Filing offices not used before (WO, US, CN, ...)' },
  { key: 'partners', label: 'New partners', max: 10, tip: 'Co-applicants first seen in the last 2 quarters' },
  { key: 'stars', label: 'Stars', max: 10, tip: 'Latest Stars rating' },
  { key: 'under_reaction', label: 'Under-reaction', max: 10, tip: 'Weak 6M share price despite a strategic change' },
];

function pct(v: number | null | undefined, signed = false): string {
  if (v == null) return '-';
  const n = Math.round(v * 100);
  return `${signed && n > 0 ? '+' : ''}${n}%`;
}

function ScoreBar({ c }: { c: DeepCompany }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex w-28 h-2 rounded-full bg-gray-100 overflow-hidden gap-px" title={SCORE_PARTS.map((p) => `${p.label}: ${c.score_breakdown[p.key] ?? 0}/${p.max}`).join('\n')}>
        <div className="h-full bg-rose-500" style={{ width: `${c.alpha_score}%` }} />
      </div>
      <span className="font-mono text-xs font-semibold text-gray-800 w-8 text-right">{Math.round(c.alpha_score)}</span>
    </div>
  );
}

/** Single-series quarterly bar sparkline (EPO publications), hover shows the values. */
function QuarterBars({ c, height = 28 }: { c: DeepCompany; height?: number }) {
  const max = Math.max(1, ...c.quarters.map((q) => q.total ?? 0));
  return (
    <div className="flex items-end gap-0.5" style={{ height }}>
      {c.quarters.map((q) => (
        <div
          key={q.start}
          title={`${q.label}: ${q.total ?? 'lookup failed'} publications${q.ipc_shift != null ? `, mix shift ${pct(q.ipc_shift)}` : ''}`}
          className={`w-2 rounded-t-sm ${q.total == null ? 'bg-gray-200' : 'bg-blue-400 hover:bg-blue-600'}`}
          style={{ height: `${q.total == null ? 15 : Math.max(6, ((q.total ?? 0) / max) * 100)}%` }}
        />
      ))}
    </div>
  );
}

function Trend({ t }: { t: DeepCompany['shift_trend'] }) {
  if (!t) return <span className="text-gray-300 text-xs">-</span>;
  const Icon = t === 'ACCELERATING' ? TrendingUp : t === 'FADING' ? TrendingDown : Minus;
  const cls = t === 'ACCELERATING' ? 'text-rose-600' : t === 'FADING' ? 'text-gray-400' : 'text-gray-500';
  return <span className={`inline-flex items-center gap-1 text-xs ${cls}`}><Icon size={12} />{t.toLowerCase()}</span>;
}

function List({ icon: Icon, title, items, tone }: { icon: typeof Lightbulb; title: string; items: string[]; tone: string }) {
  if (!items.length) return null;
  return (
    <div>
      <p className={`flex items-center gap-1.5 text-xs font-semibold mb-1 ${tone}`}><Icon size={13} />{title}</p>
      <ul className="space-y-0.5 list-disc pl-5">
        {items.map((x) => <li key={x} className="text-xs text-gray-600 leading-relaxed">{x}</li>)}
      </ul>
    </div>
  );
}

function CompanyDetail({ c, label }: { c: DeepCompany; label: (code: string) => string }) {
  const t = c.thesis;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 py-2">
      <div className="lg:col-span-2 space-y-3">
        {t ? (
          <>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 font-semibold">{t.move_type.replace('_', ' ')}</span>
              <span className="text-gray-600">Conviction <strong>{t.conviction}/5</strong></span>
              <span className="text-gray-300">|</span>
              <span className="text-gray-600">Priced in: <strong>{t.priced_in}</strong></span>
              <span className="text-gray-300">|</span>
              <span className="text-gray-600">Horizon: {t.horizon}</span>
            </div>
            <p className="text-sm text-gray-700 leading-relaxed">{t.hypothesis}</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <List icon={Lightbulb} title="Catalysts" items={t.catalysts} tone="text-amber-700" />
              <List icon={ShieldAlert} title="Risks" items={t.risks} tone="text-red-700" />
              <List icon={CheckCircle2} title="Would confirm" items={t.confirm_signals} tone="text-emerald-700" />
              <List icon={XCircle} title="Would refute" items={t.refute_signals} tone="text-gray-600" />
            </div>
          </>
        ) : (
          <p className="text-xs text-gray-500">No AI thesis: only the top candidates get a deep dive{c.alpha_score > 0 ? ' (theses are written after all companies are scored)' : ''}.</p>
        )}
      </div>
      <div className="space-y-3 text-xs">
        <div>
          <p className="font-semibold text-gray-700 mb-1">Publications per quarter</p>
          <QuarterBars c={c} height={48} />
          <p className="text-gray-400 mt-1">{c.quarters[0]?.label} → {c.quarters[c.quarters.length - 1]?.label}</p>
        </div>
        {(c.top_ipc_baseline.length > 0 || c.top_ipc_recent.length > 0) && (
          <div>
            <p className="font-semibold text-gray-700 mb-1">Top classes before → now</p>
            {c.top_ipc_baseline.map((code) => <IpcCode key={code} code={code} aiLabel={label(code) || undefined} />)}
            <span className="text-gray-300 mx-1">→</span>
            {c.top_ipc_recent.map((code) => <IpcCode key={code} code={code} aiLabel={label(code) || undefined} />)}
          </div>
        )}
        {c.emerging.length > 0 && (
          <div>
            <p className="font-semibold text-gray-700 mb-1">Emerging classes</p>
            {c.emerging.map((e) => (
              <div key={e.code} className="mb-1.5">
                <IpcCode code={e.code} tone="plain" aiLabel={label(e.code) || undefined} />{' '}
                <span className="text-gray-600">{label(e.code)}</span>{' '}
                <span className="text-gray-400">({e.recent_count}, since {e.first_seen})</span>
                <p className="text-gray-500 italic truncate" title={e.examples.join('\n')}>{e.examples[0]}</p>
              </div>
            ))}
          </div>
        )}
        {c.co_applicants.length > 0 && (
          <div>
            <p className="font-semibold text-gray-700 mb-1">Co-applicants</p>
            {c.co_applicants.map((a) => (
              <p key={a.name} className="text-gray-600">
                {a.new && <span className="text-rose-600 font-semibold">NEW </span>}
                {a.name} <span className="text-gray-400">({a.count}, since {a.first_seen})</span>
              </p>
            ))}
          </div>
        )}
        <p className="text-gray-500">
          Share price: 3M {pct(c.return_3m, true)}, 6M {pct(c.return_6m, true)}, {pct(c.from_52w_high)} vs 52w high
        </p>
      </div>
    </div>
  );
}

export function AlphaDeep({ deep }: { deep: AlphaDeepResponse | null }) {
  // deep.in_progress = live results of a run that is still going
  const [open, setOpen] = useState<Set<string>>(new Set());
  if (!deep) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 text-center text-sm text-gray-500">
        <Brain size={28} className="mx-auto mb-2 text-gray-300" />
        No deep analysis yet. Start one above. It studies several quarters of filings per company and writes an AI thesis for the top candidates.
      </div>
    );
  }
  const labels = new Map(deep.ipc_labels.map((l) => [l.code, l.label]));
  const label = (code: string) => labels.get(code) ?? '';
  const toggle = (t: string) => setOpen((prev) => {
    const next = new Set(prev);
    if (next.has(t)) next.delete(t); else next.add(t);
    return next;
  });

  const live = !!deep.in_progress;
  const phaseText: Record<string, string> = {
    data: 'collecting patent history',
    ai: 'writing AI theses for the top candidates',
    memo: 'writing the analyst memo',
  };

  return (
    <div className="space-y-4">
      {live && (
        <div className="bg-violet-50 border border-violet-200 rounded-xl px-4 py-3 text-xs text-violet-800 flex flex-wrap items-center gap-2">
          <Loader2 size={14} className="animate-spin" />
          <strong>Live results</strong> - {deep.companies_done}/{deep.companies_total} companies analysed, now {phaseText[deep.phase ?? 'data']}.
          Rankings will change as more companies arrive. The table updates automatically.
        </div>
      )}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <Brain size={18} className="text-violet-500" />
          <h3 className="text-sm font-semibold text-gray-800">Deep alpha analysis - analyst memo</h3>
          <span className="ml-auto flex items-center gap-1.5 text-xs text-gray-500">
            <Clock size={13} />
            {live ? (
              <>Running since <strong>{formatRunAt(deep.run_at)}</strong> ({Math.round(deep.duration_s / 60)} min so far, {deep.quarters} quarters)</>
            ) : (
              <>Last deep run: <strong>{formatRunAt(deep.finished_at)}</strong> ({timeAgo(deep.finished_at)}, {deep.trigger},{' '}
              {deep.quarters} quarters, {Math.round(deep.duration_s / 60)} min, {deep.model})</>
            )}
          </span>
        </div>
        {deep.memo ? (
          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">{deep.memo}</p>
        ) : (
          <p className="text-sm text-gray-400 italic">The memo is written once every company has been analysed.</p>
        )}
        {deep.themes.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-gray-700 mb-1.5"><Network size={13} />Cross-company themes</p>
            <div className="flex flex-wrap gap-2">
              {deep.themes.map((t) => (
                <span key={t.code} className="text-xs px-2 py-1 rounded-lg bg-violet-50 border border-violet-200 text-violet-800">
                  <IpcCode code={t.code} tone="theme" aiLabel={label(t.code) || undefined} /> {label(t.code)}: {t.companies.join(', ')}
                </span>
              ))}
            </div>
          </div>
        )}
        {deep.warnings.length > 0 && (
          <details className="mt-3 text-xs text-amber-700">
            <summary className="cursor-pointer flex items-center gap-1"><AlertTriangle size={12} />{deep.warnings.length} data warnings</summary>
            <ul className="list-disc pl-5 mt-1">{deep.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          </details>
        )}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200">
          <h3 className="text-sm font-semibold text-gray-800">Alpha Score ranking</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            0-100 composite: {SCORE_PARTS.map((p) => `${p.label.toLowerCase()} ${p.max}`).join(', ')}. Hover the bar for the breakdown, click a row for the thesis.
          </p>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200 text-xs">
              <th className="w-8" />
              <th className="text-left px-3 py-2 font-medium text-gray-600">Company</th>
              <th className="text-left px-3 py-2 font-medium text-gray-600">Alpha Score</th>
              <th className="text-left px-3 py-2 font-medium text-gray-600">Filings / quarter</th>
              <th className="text-right px-3 py-2 font-medium text-gray-600">Velocity</th>
              <th className="text-right px-3 py-2 font-medium text-gray-600">Mix shift</th>
              <th className="text-left px-3 py-2 font-medium text-gray-600">Trend</th>
              <th className="text-left px-3 py-2 font-medium text-gray-600">Move</th>
              <th className="text-right px-4 py-2 font-medium text-gray-600">6M</th>
            </tr>
          </thead>
          <tbody>
            {deep.companies.map((c) => {
              const isOpen = open.has(c.ticker);
              return (
                <Fragment key={c.ticker}>
                  <tr className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer" onClick={() => toggle(c.ticker)}>
                    <td className="pl-3 text-gray-400">{isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</td>
                    <td className="px-3 py-2">
                      <span className="font-medium text-gray-800">{c.name}</span>
                      <span className="text-xs text-gray-400 ml-2">{c.sector}</span>
                      {!c.data_complete && <span title="Some EPO lookups failed" className="ml-1 text-amber-500"><AlertTriangle size={12} className="inline" /></span>}
                    </td>
                    <td className="px-3 py-2"><ScoreBar c={c} /></td>
                    <td className="px-3 py-2"><QuarterBars c={c} /></td>
                    <td className="px-3 py-2 text-right font-mono text-xs text-gray-700">{c.velocity_ratio != null ? `${c.velocity_ratio.toFixed(2)}x` : '-'}</td>
                    <td className="px-3 py-2 text-right font-mono text-xs text-gray-700">{pct(c.recent_shift)}</td>
                    <td className="px-3 py-2"><Trend t={c.shift_trend} /></td>
                    <td className="px-3 py-2 text-xs text-gray-600">
                      {c.thesis ? `${c.thesis.move_type.replace('_', ' ').toLowerCase()} (${c.thesis.conviction}/5)` : '-'}
                    </td>
                    <td className={`px-4 py-2 text-right font-mono text-xs ${(c.return_6m ?? 0) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      {pct(c.return_6m, true)}
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="bg-gray-50 border-b border-gray-100">
                      <td />
                      <td colSpan={8} className="px-3 py-2"><CompanyDetail c={c} label={label} /></td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
