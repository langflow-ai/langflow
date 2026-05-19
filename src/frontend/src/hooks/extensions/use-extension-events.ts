import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import useAlertStore from "@/stores/alertStore";
import type {
  ExtensionEvent,
  ExtensionEventsResponse,
} from "@/types/extension-events";

const IDLE_INTERVAL = 5000;
const ACTIVE_INTERVAL = 1000;
const MIN_BANNER_DISPLAY_MS = 2000;

// Look back this many seconds on mount so events that fired just before page
// load (e.g. a bundle_reload_failed during a hot-reload) are not silently
// missed. The service TTL (120s) is larger than this window.
const MOUNT_LOOKBACK_SECONDS = 30;

type UseExtensionEventsReturn = {
  events: ExtensionEvent[];
  isSettled: boolean;
  clearEvents: () => void;
};

export function useExtensionEvents(): UseExtensionEventsReturn {
  const [isSettled, setIsSettled] = useState(true);
  const [events, setEvents] = useState<ExtensionEvent[]>([]);

  const queryClient = useQueryClient();
  // Store in a ref so poll callbacks always have the current instance without
  // needing queryClient in useCallback dependency arrays (which would cause
  // an infinite render loop when the QueryClient reference is unstable, e.g.
  // in test environments).
  const queryClientRef = useRef(queryClient);
  queryClientRef.current = queryClient;

  const cursorRef = useRef<number>(Date.now() / 1000 - MOUNT_LOOKBACK_SECONDS);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isActiveRef = useRef(false);
  const isPollingRef = useRef(false);
  const mountedRef = useRef(true);
  const activeSinceRef = useRef<number>(0);
  const settleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollRef = useRef<(() => Promise<void>) | undefined>(undefined);

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
    setIsSettled(true);
    startIdlePolling();
  }, [startIdlePolling]);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  const poll = useCallback(async () => {
    if (isPollingRef.current) return;

    isPollingRef.current = true;
    try {
      const response = await api.get<ExtensionEventsResponse>(
        `${getURL("EXTENSIONS")}/events`,
        { params: { since: cursorRef.current } },
      );

      if (!mountedRef.current) return;

      const { events: newEvents, settled } = response.data;

      if (newEvents.length > 0) {
        const maxTs = Math.max(...newEvents.map((e) => e.timestamp));
        cursorRef.current = maxTs;

        setEvents((prev) => [...prev, ...newEvents]);

        for (const event of newEvents) {
          if (
            event.type === "bundle_reloaded" ||
            event.type === "components_added" ||
            event.type === "components_removed"
          ) {
            queryClientRef.current.invalidateQueries({ queryKey: ["useGetTypes"] });
          } else if (
            event.type === "extension_error" ||
            event.type === "bundle_reload_failed"
          ) {
            useAlertStore.getState().setErrorData({
              title: "Extension error",
              list: [
                typeof event.payload.message === "string"
                  ? event.payload.message
                  : `${event.type}: check server logs for details`,
              ],
            });
          }
          // flow_migrated: no-op for Phase 1; future tickets wire to canvas
        }

        if (!isActiveRef.current) {
          isActiveRef.current = true;
          activeSinceRef.current = Date.now();
          setIsSettled(false);
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
      const status = (error as { response?: { status?: number } } | undefined)
        ?.response?.status;
      if (status === 401 || status === 403) {
        console.error(
          "[useExtensionEvents] Terminal error, stopping poll:",
          status,
        );
        clearInterval_();
        if (isActiveRef.current) {
          isActiveRef.current = false;
          setIsSettled(true);
        }
        if (settleTimerRef.current) {
          clearTimeout(settleTimerRef.current);
          settleTimerRef.current = null;
        }
        return;
      }
      console.warn("[useExtensionEvents] Poll failed (will retry):", error);
    } finally {
      isPollingRef.current = false;
    }
  }, [clearInterval_, settle]);

  pollRef.current = poll;

  useEffect(() => {
    mountedRef.current = true;
    cursorRef.current = Date.now() / 1000 - MOUNT_LOOKBACK_SECONDS;
    setEvents([]);
    setIsSettled(true);
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
  }, [poll, clearInterval_, startIdlePolling]);

  return { events, isSettled, clearEvents };
}
