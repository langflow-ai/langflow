import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import type { FlowEvent, FlowEventsResponse } from "@/types/flow-events";

const IDLE_INTERVAL = 5000;
const ACTIVE_INTERVAL = 1000;
const MIN_BANNER_DISPLAY_MS = 2000;

type UseFlowEventsReturn = {
  isAgentWorking: boolean;
  events: FlowEvent[];
  lastSettledAt: number | null;
  clearEvents: () => void;
};

export function useFlowEvents(flowId: string | undefined): UseFlowEventsReturn {
  const [isAgentWorking, setIsAgentWorking] = useState(false);
  const [events, setEvents] = useState<FlowEvent[]>([]);
  const [lastSettledAt, setLastSettledAt] = useState<number | null>(null);

  const cursorRef = useRef<number>(Date.now() / 1000);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isActiveRef = useRef(false);
  const isPollingRef = useRef(false);
  const mountedRef = useRef(true);
  const activeSinceRef = useRef<number>(0);
  const settleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollRef = useRef<() => Promise<void>>();

  const clearInterval_ = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const startIdlePolling = useCallback(() => {
    clearInterval_();
    intervalRef.current = setInterval(() => {
      pollRef.current?.();
    }, IDLE_INTERVAL);
  }, [clearInterval_]);

  const settle = useCallback(() => {
    if (!mountedRef.current) return;
    isActiveRef.current = false;
    setIsAgentWorking(false);
    setLastSettledAt(Date.now() / 1000);
    startIdlePolling();
  }, [startIdlePolling]);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  const poll = useCallback(async () => {
    if (!flowId || isPollingRef.current) return;

    isPollingRef.current = true;
    try {
      const response = await api.get<FlowEventsResponse>(
        `${getURL("FLOWS")}/${flowId}/events`,
        { params: { since: cursorRef.current } },
      );

      if (!mountedRef.current) return;

      const { events: newEvents, settled } = response.data;

      if (newEvents.length > 0) {
        const maxTs = Math.max(...newEvents.map((e) => e.timestamp));
        cursorRef.current = maxTs;

        setEvents((prev) => [...prev, ...newEvents]);

        if (!isActiveRef.current) {
          isActiveRef.current = true;
          activeSinceRef.current = Date.now();
          setIsAgentWorking(true);
          clearInterval_();
          intervalRef.current = setInterval(() => {
            pollRef.current?.();
          }, ACTIVE_INTERVAL);
        }
      }

      if (settled && isActiveRef.current && !settleTimerRef.current) {
        const elapsed = Date.now() - activeSinceRef.current;
        const remaining = MIN_BANNER_DISPLAY_MS - elapsed;

        if (remaining > 0) {
          clearInterval_();
          settleTimerRef.current = setTimeout(() => {
            settleTimerRef.current = null;
            settle();
          }, remaining);
        } else {
          settle();
        }
      }
    } catch (error) {
      console.warn("[useFlowEvents] Poll failed:", error);
    } finally {
      isPollingRef.current = false;
    }
  }, [flowId, clearInterval_, settle]);

  // Keep pollRef current so interval callbacks use latest poll
  pollRef.current = poll;

  useEffect(() => {
    if (!flowId) return;

    mountedRef.current = true;
    cursorRef.current = Date.now() / 1000;
    setEvents([]);
    setIsAgentWorking(false);
    setLastSettledAt(null);
    isActiveRef.current = false;
    isPollingRef.current = false;
    activeSinceRef.current = 0;

    if (settleTimerRef.current) {
      clearTimeout(settleTimerRef.current);
      settleTimerRef.current = null;
    }

    poll();
    startIdlePolling();

    return () => {
      mountedRef.current = false;
      clearInterval_();
      if (settleTimerRef.current) {
        clearTimeout(settleTimerRef.current);
        settleTimerRef.current = null;
      }
    };
  }, [flowId, poll, clearInterval_, startIdlePolling]);

  return { isAgentWorking, events, lastSettledAt, clearEvents };
}
