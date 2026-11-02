import { useEffect, useRef, useState } from 'react';
import { fetchIpcTitles } from '../api';

export const IPC_SECTIONS: Record<string, string> = {
  A: 'Human necessities (health, food, agriculture)',
  B: 'Performing operations & transporting',
  C: 'Chemistry & metallurgy',
  D: 'Textiles & paper',
  E: 'Fixed constructions',
  F: 'Mechanical engineering, lighting, heating, weapons',
  G: 'Physics (computing, measuring, optics)',
  H: 'Electricity (electronics, power, telecom)',
  Y: 'Cross-sectional technologies (CPC)',
};

// Official titles, shared by every IpcCode on the page. Requests are batched.
const titles = new Map<string, string | null>();
const queued = new Set<string>();
const listeners = new Set<() => void>();
let flushTimer: ReturnType<typeof setTimeout> | null = null;

function request(codes: string[]) {
  codes.filter((c) => !titles.has(c)).forEach((c) => queued.add(c));
  if (queued.size === 0 || flushTimer) return;
  flushTimer = setTimeout(async () => {
    const batch = [...queued];
    queued.clear();
    flushTimer = null;
    batch.forEach((c) => titles.set(c, null)); // null = requested, not (yet) known
    try {
      const result = await fetchIpcTitles(batch);
      batch.forEach((c) => titles.set(c, result[c] ?? '')); // '' = no official title
    } catch {
      batch.forEach((c) => titles.delete(c)); // allow a retry on next hover
    }
    listeners.forEach((l) => l());
  }, 50);
}

function useIpcTitle(code: string) {
  const [, setVersion] = useState(0);
  useEffect(() => {
    const l = () => setVersion((v) => v + 1);
    listeners.add(l);
    request([code, code.slice(0, 3)]);
    return () => { listeners.delete(l); };
  }, [code]);
  return {
    subclass: titles.get(code),
    klass: code.length > 3 ? titles.get(code.slice(0, 3)) : undefined,
  };
}

type Tone = 'new' | 'neutral' | 'plain' | 'theme';

const TONES: Record<Tone, string> = {
  new: 'inline-block px-1.5 py-0.5 mr-1 mb-0.5 rounded border text-[11px] font-mono bg-rose-50 text-rose-700 border-rose-200',
  neutral: 'inline-block px-1.5 py-0.5 mr-1 mb-0.5 rounded border text-[11px] font-mono bg-gray-50 text-gray-600 border-gray-200',
  plain: 'font-mono text-rose-700',
  theme: 'font-mono',
};

/** An IPC code with a hover card: official subclass + class title, section, and an optional AI label. */
export function IpcCode({ code, tone = 'neutral', aiLabel }: { code: string; tone?: Tone; aiLabel?: string }) {
  const { subclass, klass } = useIpcTitle(code);
  const ref = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState<{ x: number; y: number; above: boolean } | null>(null);

  const show = () => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    const above = r.bottom + 160 > window.innerHeight;
    setPos({ x: Math.min(r.left, window.innerWidth - 340), y: above ? r.top - 6 : r.bottom + 6, above });
  };

  return (
    <span
      ref={ref}
      className={`${TONES[tone]} cursor-help underline decoration-dotted decoration-gray-300 underline-offset-2`}
      onMouseEnter={show}
      onMouseLeave={() => setPos(null)}
    >
      {code}
      {pos && (
        <span
          role="tooltip"
          className="fixed z-[1000] w-80 bg-gray-800 text-white rounded-lg shadow-lg px-3 py-2.5 text-[11px] leading-snug font-sans no-underline pointer-events-none"
          style={{ left: pos.x, top: pos.y, transform: pos.above ? 'translateY(-100%)' : undefined }}
        >
          <span className="block font-semibold text-xs mb-1">
            <span className="font-mono">{code}</span>
            {subclass ? ` - ${subclass}` : ''}
          </span>
          {subclass == null && <span className="block text-gray-300 italic mb-1">Loading official title...</span>}
          {klass && <span className="block text-gray-300">Class {code.slice(0, 3)}: {klass}</span>}
          <span className="block text-gray-300">Section {code[0]}: {IPC_SECTIONS[code[0]] ?? 'Unknown'}</span>
          {aiLabel && <span className="block mt-1 text-amber-200">In short: {aiLabel}</span>}
        </span>
      )}
    </span>
  );
}
