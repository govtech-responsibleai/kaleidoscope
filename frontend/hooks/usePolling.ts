"use client";

import { useCallback, useEffect, useRef } from "react";

interface UsePollingOptions {
  enabled: boolean;
  intervalMs: number;
  onPoll: () => Promise<void> | void;
  runImmediately?: boolean;
}

export function usePolling({
  enabled,
  intervalMs,
  onPoll,
  runImmediately = true,
}: UsePollingOptions): void {
  const timeoutRef = useRef<number | null>(null);
  const inFlightRef = useRef(false);
  const onPollRef = useRef(onPoll);
  const enabledRef = useRef(enabled);
  const intervalRef = useRef(intervalMs);

  useEffect(() => { onPollRef.current = onPoll; }, [onPoll]);
  useEffect(() => { enabledRef.current = enabled; }, [enabled]);
  useEffect(() => { intervalRef.current = intervalMs; }, [intervalMs]);

  const clearTimer = useCallback(() => {
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      clearTimer();
      return;
    }

    const scheduleNext = () => {
      clearTimer();
      if (!enabledRef.current) return;
      timeoutRef.current = window.setTimeout(() => { void runPoll(); }, intervalRef.current);
    };

    const runPoll = async () => {
      if (!enabledRef.current || inFlightRef.current) return;
      inFlightRef.current = true;
      try {
        await onPollRef.current();
      } finally {
        inFlightRef.current = false;
        scheduleNext();
      }
    };

    if (runImmediately) {
      void runPoll();
    } else {
      scheduleNext();
    }

    return clearTimer;
  }, [clearTimer, enabled, runImmediately]);

  useEffect(() => () => clearTimer(), [clearTimer]);
}
