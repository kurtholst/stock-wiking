import { useEffect, useState } from 'react';
import { BellRing, Check, Loader2 } from 'lucide-react';
import { fetchAlertsStatus, sendTestAlert, type SentAlert } from '../api';
import { formatRunAt } from '../utils';

const LEVEL_STYLE: Record<SentAlert['level'], string> = {
  critical: 'bg-red-100 text-red-700',
  notable: 'bg-amber-100 text-amber-700',
  digest: 'bg-gray-100 text-gray-600',
};

/** ntfy phone-alert status, test button and the most recent alerts sent. */
export function AlertsPanel({ refreshKey }: { refreshKey: unknown }) {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [recent, setRecent] = useState<SentAlert[]>([]);
  const [testState, setTestState] = useState<'idle' | 'sending' | 'sent' | string>('idle');

  useEffect(() => {
    fetchAlertsStatus()
      .then((s) => { setConfigured(s.configured); setRecent(s.recent); })
      .catch(() => setConfigured(false));
  }, [refreshKey]);

  const test = async () => {
    setTestState('sending');
    try {
      await sendTestAlert();
      setTestState('sent');
      setTimeout(() => setTestState('idle'), 3000);
    } catch (e) {
      setTestState(e instanceof Error ? e.message : 'failed');
    }
  };

  return (
    <details className="bg-white rounded-xl border border-gray-200 px-4 py-3 group">
      <summary className="flex items-center gap-2 cursor-pointer text-sm list-none">
        <BellRing size={16} className={configured ? 'text-emerald-500' : 'text-gray-300'} />
        <span className="font-semibold text-gray-800">Phone alerts</span>
        <span className="text-xs text-gray-500">
          {configured == null ? '' : configured ? 'on (ntfy) - critical signals for all 20 companies' : 'not configured'}
        </span>
        <span className="ml-auto text-xs text-gray-400">{recent.length ? `last: ${formatRunAt(recent[0].sent_at)}` : 'none sent yet'}</span>
      </summary>
      <div className="mt-3 space-y-3 text-xs text-gray-600">
        <p className="leading-relaxed">
          <strong className="text-red-700">Critical</strong> (urgent push): a 4-5★ company newly flagged with a shift into a new IPC class,
          or a deep-analysis Alpha Score of 60+ with AI conviction 4-5/5 that is not priced in.{' '}
          <strong className="text-amber-700">Notable</strong> (normal push): an accelerating shift with a score of 40+, or 2+ companies moving into the same class.{' '}
          <strong>Digest</strong> (quiet): after each Sunday deep run. Each signal is sent once and can repeat after 60 days.
        </p>
        <button
          onClick={test}
          disabled={!configured || testState === 'sending'}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 font-medium rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-50"
        >
          {testState === 'sending' ? <Loader2 size={13} className="animate-spin" /> : testState === 'sent' ? <Check size={13} /> : <BellRing size={13} />}
          {testState === 'sent' ? 'Sent - check your phone' : 'Send test alert'}
        </button>
        {!['idle', 'sending', 'sent'].includes(testState) && <span className="ml-2 text-red-600">{testState}</span>}
        {recent.length > 0 && (
          <ul className="space-y-1.5 pt-2 border-t border-gray-100">
            {recent.map((a) => (
              <li key={a.key} className="flex gap-2">
                <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${LEVEL_STYLE[a.level]}`}>{a.level}</span>
                <span className="text-gray-400 shrink-0">{formatRunAt(a.sent_at)}</span>
                <span><strong className="text-gray-700">{a.title}</strong> - {a.message}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </details>
  );
}
