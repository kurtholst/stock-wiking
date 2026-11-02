import { useCallback, useEffect, useRef, useState } from 'react';
import type { RunKind, RunStatus } from './types';
import { fetchRunStatus, startRun } from './api';

/**
 * Tracks the server's background run (Stars scan / deep analysis).
 * Polls while something is running and calls onFinished(kind) when a run completes.
 */
export function useRunStatus(onFinished?: (kind: RunKind | null) => void) {
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const wasRunning = useRef(false);
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;

  const poll = useCallback(async () => {
    try {
      const s = await fetchRunStatus();
      setStatus(s);
      const running = s.status === 'running' || s.external_running;
      if (wasRunning.current && !running) onFinishedRef.current?.(s.kind);
      wasRunning.current = running;
    } catch {
      // Keep the last known status on transient errors
    }
  }, []);

  const busy = status?.status === 'running' || !!status?.external_running;

  useEffect(() => {
    poll();
    const id = setInterval(poll, busy ? 3000 : 30_000);
    return () => clearInterval(id);
  }, [poll, busy]);

  const start = useCallback(async (kind: RunKind, opts: { period_days?: number; quarters?: number } = {}) => {
    setStartError(null);
    try {
      const s = await startRun(kind, opts);
      setStatus(s);
      wasRunning.current = true;
    } catch (e) {
      setStartError(e instanceof Error ? e.message : 'Could not start run');
    }
  }, []);

  return { status, busy, start, startError };
}
