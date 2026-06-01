import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import useAlertStore from "@/stores/alertStore";
import { useTypesStore } from "@/stores/typesStore";
import type {
  ExtensionEvent,
  ExtensionEventsResponse,
} from "@/types/extension-events";
import { isOwnReload } from "./reload-dedup";
import {
  extractTypedErrorList,
  renderTypedErrorList,
} from "./typed-error-formatting";

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

        // Filter out reloads originated by this tab's UI Reload click.
        // The API response handler in bundleHeaderActions.onSuccess already
        // pushed a toast and refreshed types for those; processing the
        // mirrored event again would double-toast and double-refetch.
        const processedEvents = newEvents.filter(
          (event) =>
            !(
              (event.type === "bundle_reloaded" ||
                event.type === "bundle_reload_failed") &&
              isOwnReload(event.payload.reload_id)
            ),
        );

        // When the reload pipeline emits a bundle_reloaded for a bundle it
        // already carries the components_added/removed deltas in the payload.
        // Suppress any standalone delta events in the same batch that target
        // the same bundle to avoid stacking duplicate toasts.
        const reloadedBundlesInBatch = new Set<string>();
        let hasComponentChange = false;
        for (const event of processedEvents) {
          if (event.type === "bundle_reloaded") {
            const bundle = event.payload.bundle;
            if (typeof bundle === "string") {
              reloadedBundlesInBatch.add(bundle);
            }
            hasComponentChange = true;
          } else if (
            event.type === "components_added" ||
            event.type === "components_removed"
          ) {
            hasComponentChange = true;
          }
        }

        // Match the UI Reload onSuccess: clear the cached types snapshot
        // before invalidating React Query so consumers reading directly from
        // useTypesStore don't serve stale templates between the event and
        // the refetch landing. One clear per batch is sufficient.
        if (hasComponentChange) {
          useTypesStore.getState().setTypes({});
        }

        const alert = useAlertStore.getState();
        for (const event of processedEvents) {
          if (event.type === "bundle_reloaded") {
            queryClientRef.current.invalidateQueries({
              queryKey: ["useGetTypes"],
            });
            const bundle =
              typeof event.payload.bundle === "string"
                ? event.payload.bundle
                : "bundle";
            const added = Array.isArray(event.payload.components_added)
              ? event.payload.components_added.length
              : 0;
            const removed = Array.isArray(event.payload.components_removed)
              ? event.payload.components_removed.length
              : 0;
            const changed = Array.isArray(event.payload.components_changed)
              ? event.payload.components_changed.length
              : 0;
            const hasDelta = added > 0 || removed > 0 || changed > 0;
            // Mirror bundleHeaderActions.onSuccess: a warning-bearing reload
            // surfaces the diagnostics both inline on the success toast and
            // as a separate blue notice. Without this branch a tab that
            // picks up the event via the 30s mount-lookback (instead of
            // the API response) sees only the green toast and silently
            // loses the warnings the clicking tab saw.
            const warnings = extractTypedErrorList(event.payload.warnings);
            const warningList = renderTypedErrorList(warnings);
            alert.setSuccessData({
              title: hasDelta
                ? `Reloaded ${bundle} (+${added} / -${removed} / ~${changed} components)`
                : `Reloaded ${bundle} (no source changes detected)`,
              ...(warningList ? { list: warningList.list } : {}),
            });
            if (warningList && warningList.list.length > 0) {
              alert.setNoticeData({
                title: `Reloaded ${bundle} with warnings`,
                list: warningList.list,
              });
            }
          } else if (
            event.type === "components_added" ||
            event.type === "components_removed"
          ) {
            queryClientRef.current.invalidateQueries({
              queryKey: ["useGetTypes"],
            });
            const bundle =
              typeof event.payload.bundle === "string"
                ? event.payload.bundle
                : undefined;
            if (bundle && reloadedBundlesInBatch.has(bundle)) {
              continue;
            }
            const components = Array.isArray(event.payload.components)
              ? (event.payload.components as unknown[]).length
              : 0;
            const sign = event.type === "components_added" ? "+" : "-";
            alert.setNoticeData({
              title: bundle
                ? `${sign}${components} components in ${bundle}`
                : `${sign}${components} components`,
            });
          } else if (
            event.type === "extension_error" ||
            event.type === "bundle_reload_failed"
          ) {
            // bundle_reload_failed carries the full ReloadResult envelope
            // (errors[] from ExtensionError.to_dict()); extension_error
            // emits a flat {message,...} payload. Try both before falling
            // back to the generic fallback.
            let message: string | undefined;
            const errors = event.payload.errors;
            if (Array.isArray(errors) && errors.length > 0) {
              const first = errors[0];
              if (
                first &&
                typeof first === "object" &&
                "message" in first &&
                typeof (first as { message: unknown }).message === "string"
              ) {
                message = (first as { message: string }).message;
              }
            }
            if (!message && typeof event.payload.message === "string") {
              message = event.payload.message;
            }
            alert.setErrorData({
              title: "Extension error",
              list: [message ?? `${event.type}: check server logs for details`],
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
