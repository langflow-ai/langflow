import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import type { FlowEvent, FlowEventsResponse } from "@/types/flow-events";

const IDLE_INTERVAL = 5000;
const ACTIVE_INTERVAL = 1000;

type UseFlowEventsReturn = {
  isAgentWorking: boolean;
  events: FlowEvent[];
  lastSettledAt: number | null;
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

  const clearInterval_ = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
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
          setIsAgentWorking(true);
          clearInterval_();
          intervalRef.current = setInterval(poll, ACTIVE_INTERVAL);
        }
      }

      if (settled && isActiveRef.current) {
        isActiveRef.current = false;
        setIsAgentWorking(false);
        setLastSettledAt(Date.now() / 1000);
        setEvents([]);
        clearInterval_();
        intervalRef.current = setInterval(poll, IDLE_INTERVAL);
      }
    } catch (error) {
      console.warn("[useFlowEvents] Poll failed:", error);
    } finally {
      isPollingRef.current = false;
    }
  }, [flowId, clearInterval_]);

  useEffect(() => {
    if (!flowId) return;

    mountedRef.current = true;
    cursorRef.current = Date.now() / 1000;
    setEvents([]);
    setIsAgentWorking(false);
    setLastSettledAt(null);
    isActiveRef.current = false;
    isPollingRef.current = false;

    // Poll immediately on mount, then at idle interval
    poll();
    clearInterval_();
    intervalRef.current = setInterval(poll, IDLE_INTERVAL);

    return () => {
      mountedRef.current = false;
      clearInterval_();
    };
  }, [flowId, poll, clearInterval_]);

  return { isAgentWorking, events, lastSettledAt };
}
