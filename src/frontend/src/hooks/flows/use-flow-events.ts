import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import type { FlowEvent, FlowEventsResponse } from "@/types/flow-events";

const IDLE_INTERVAL = 5000;
const ACTIVE_INTERVAL = 1000;
const MIN_BANNER_DISPLAY_MS = 2000;
// Seeding the cursor with "now" drops every event posted between the route
// committing and this hook mounting with the new flow id -- the API only returns
// events strictly newer than `since`, so a dropped event never comes back. Start
// the cursor in the past instead and let the server's `settled` flag decide
// whether what we catch up on is still worth showing.
const INITIAL_LOOKBACK_SECONDS = 10;

const startingCursor = () => Date.now() / 1000 - INITIAL_LOOKBACK_SECONDS;

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

  const cursorRef = useRef<number>(startingCursor());
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isActiveRef = useRef(false);
  const isCatchUpPollRef = useRef(true);
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

    const isCatchUpPoll = isCatchUpPollRef.current;
    isCatchUpPollRef.current = false;

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

        // The catch-up poll reaches back before mount, so it can surface work
        // that is already over. Advance the cursor past it but stay quiet --
        // flashing a banner (and re-fetching the flow on the settle that
        // follows) for finished work is worse than showing nothing.
        const isFinishedWork = isCatchUpPoll && settled && !isActiveRef.current;

        if (!isFinishedWork) {
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
      const status = (error as { response?: { status?: number } } | undefined)
        ?.response?.status;
      if (status === 401 || status === 403 || status === 404) {
        console.error("[useFlowEvents] Terminal error, stopping poll:", status);
        clearInterval_();
        // Clear agent-working state so the UI doesn't stay locked
        if (isActiveRef.current) {
          isActiveRef.current = false;
          setIsAgentWorking(false);
        }
        if (settleTimerRef.current) {
          clearTimeout(settleTimerRef.current);
          settleTimerRef.current = null;
        }
        return;
      }
      console.warn("[useFlowEvents] Poll failed (will retry):", error);
    } finally {
      isPollingRef.current = false;
    }
  }, [flowId, clearInterval_, settle]);

  // Keep pollRef current so interval callbacks use latest poll
  pollRef.current = poll;

  useEffect(() => {
    if (!flowId) return;

    mountedRef.current = true;
    cursorRef.current = startingCursor();
    setEvents([]);
    setIsAgentWorking(false);
    setLastSettledAt(null);
    isActiveRef.current = false;
    isCatchUpPollRef.current = true;
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
