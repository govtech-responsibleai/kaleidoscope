"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseVisibilityPollingOptions {
  enabled: boolean;
  intervalMs: number;
  onPoll: () => Promise<void> | void;
  runImmediately?: boolean;
}

const isDocumentActive = (): boolean => {
  if (typeof document === "undefined") {
    return true;
  }
  return document.visibilityState === "visible" && document.hasFocus();
};

export function usePageActivity(): boolean {
  const [isActive, setIsActive] = useState<boolean>(() => isDocumentActive());

  useEffect(() => {
    const updateActivity = () => {
      setIsActive(isDocumentActive());
    };

    updateActivity();
    document.addEventListener("visibilitychange", updateActivity);
    window.addEventListener("focus", updateActivity);
    window.addEventListener("blur", updateActivity);

    return () => {
      document.removeEventListener("visibilitychange", updateActivity);
      window.removeEventListener("focus", updateActivity);
      window.removeEventListener("blur", updateActivity);
    };
  }, []);

  return isActive;
}

export function useVisibilityPolling({
  enabled,
  intervalMs,
  onPoll,
  runImmediately = true,
}: UseVisibilityPollingOptions): void {
  const isActive = usePageActivity();
  const timeoutRef = useRef<number | null>(null);
  const inFlightRef = useRef(false);
  const onPollRef = useRef(onPoll);
  const enabledRef = useRef(enabled);
  const intervalRef = useRef(intervalMs);

  useEffect(() => {
    onPollRef.current = onPoll;
  }, [onPoll]);

  useEffect(() => {
    enabledRef.current = enabled;
  }, [enabled]);

  useEffect(() => {
    intervalRef.current = intervalMs;
  }, [intervalMs]);

  const clearTimer = useCallback(() => {
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!enabled || !isActive) {
      clearTimer();
      return;
    }

    const scheduleNext = () => {
      clearTimer();
      if (!enabledRef.current || !isDocumentActive()) {
        return;
      }

      timeoutRef.current = window.setTimeout(() => {
        void runPoll();
      }, intervalRef.current);
    };

    const runPoll = async () => {
      if (!enabledRef.current || !isDocumentActive() || inFlightRef.current) {
        return;
      }

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
  }, [clearTimer, enabled, isActive, runImmediately]);

  useEffect(() => {
    return () => {
      clearTimer();
    };
  }, [clearTimer]);
}
