import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";
import {
  EnabledModelsResponse,
  useGetEnabledModels,
} from "@/controllers/API/queries/models/use-get-enabled-models";
import { useUpdateEnabledModels } from "@/controllers/API/queries/models/use-update-enabled-models";
import { useDebounce } from "@/hooks/use-debounce";
import { useRefreshModelInputs } from "@/hooks/use-refresh-model-inputs";
import useAlertStore from "@/stores/alertStore";

// Extracted from useProviderConfiguration.ts to keep the toggle-queue
// concerns (overlay buffer, unsent buffer, debounced flush, awaitable
// flush, re-overlay effect, optimistic cache management) in a single
// focused module. The parent hook now owns only variable CRUD and
// provider lifecycle — the two responsibilities no longer share a file.

const getErrorMessage = (error: unknown): string | undefined => {
  const e = error as {
    response?: { data?: { detail?: string } };
    message?: string;
  };
  return e?.response?.data?.detail || e?.message;
};

export interface UseModelToggleQueueOptions {
  /**
   * Provider whose models the user is toggling. ``null`` short-circuits all
   * handlers — useful while the modal is still resolving the selection.
   */
  providerName: string | null | undefined;
}

export interface UseModelToggleQueueReturn {
  handleModelToggle: (modelName: string, enabled: boolean) => void;
  flushPendingChanges: () => Promise<void>;
}

interface ToggleBatch {
  updates: { provider: string; model_id: string; enabled: boolean }[];
  previousData: EnabledModelsResponse | undefined;
  togglesToSend: Record<string, boolean>;
}

/**
 * Coordinated optimistic-update queue for model enable/disable toggles.
 *
 * Two refs back the queue, each with a single responsibility:
 *
 *   - ``overlayToggles`` — the union of every toggle the user has made
 *     whose change has not yet been confirmed by the server. The
 *     re-overlay effect re-applies it whenever ``useGetEnabledModels``
 *     emits new data, so any refetch which lands inside the debounce or
 *     in-flight-mutation window can't overwrite the optimistic cache
 *     with stale server state. Entries are drained per-key on
 *     ``onSettled``/``onError`` — but only when the entry still matches
 *     the value we sent (a user re-toggle mid-flight becomes a fresh
 *     intent and must survive the clear).
 *
 *   - ``unsentToggles`` — the strict subset that has NOT been sent in a
 *     mutation yet (or was re-toggled since the last send). It's drained
 *     immediately at flush time so subsequent flushes don't resend the
 *     same payload — without this split, mutation A's in-flight overlay
 *     entries would be snapshotted into mutation B's payload, producing
 *     duplicate requests with non-deterministic success/failure ordering.
 */
export const useModelToggleQueue = ({
  providerName,
}: UseModelToggleQueueOptions): UseModelToggleQueueReturn => {
  const queryClient = useQueryClient();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutate: updateEnabledModels, mutateAsync: updateEnabledModelsAsync } =
    useUpdateEnabledModels({ retry: 0 });
  const { refreshAllModelInputs } = useRefreshModelInputs();
  const { data: enabledModelsData } = useGetEnabledModels();

  const overlayToggles = useRef<Record<string, boolean>>({});
  const unsentToggles = useRef<Record<string, boolean>>({});
  const fallbackModelData = useRef<EnabledModelsResponse | undefined>(
    undefined,
  );

  // After a mutation settles, remove its entries from the overlay — but
  // only when the current overlay value still matches what we sent. A
  // mismatch means the user re-toggled the same model mid-flight; that
  // entry already sits in ``unsentToggles`` for the next flush and must
  // not be dropped from the overlay until its own mutation settles.
  const clearSentOverlay = useCallback((sent: Record<string, boolean>) => {
    for (const [key, value] of Object.entries(sent)) {
      if (overlayToggles.current[key] === value) {
        delete overlayToggles.current[key];
      }
    }
    if (Object.keys(overlayToggles.current).length === 0) {
      fallbackModelData.current = undefined;
    }
  }, []);

  // Shared flush prelude: builds the mutation payload, snapshots the
  // pre-toggle cache for rollback, and drains ``unsentToggles`` so a
  // follow-up flush triggered by a new user toggle cannot resend what we
  // just sent. Returns null when there's nothing to do so callers can
  // bail symmetrically.
  const buildAndConsumeToggleBatch = useCallback((): ToggleBatch | null => {
    if (!providerName) return null;

    const togglesToSend = { ...unsentToggles.current };
    if (Object.keys(togglesToSend).length === 0) return null;

    const updates = Object.entries(togglesToSend).map(
      ([modelName, enabled]) => ({
        provider: providerName,
        model_id: modelName,
        enabled,
      }),
    );

    const previousData = fallbackModelData.current;
    unsentToggles.current = {};

    return { updates, previousData, togglesToSend };
  }, [providerName]);

  // Shared error-path: drain the overlay BEFORE restoring previousData so
  // the re-overlay effect (triggered by setQueryData below) can't re-apply
  // a stale overlay over the rollback we just performed.
  const rollbackToggleBatch = useCallback(
    (
      togglesToSend: Record<string, boolean>,
      previousData: EnabledModelsResponse | undefined,
      error: unknown,
    ) => {
      clearSentOverlay(togglesToSend);
      if (previousData) {
        queryClient.setQueryData(["useGetEnabledModels"], previousData);
      }
      setErrorData({
        title: "Error updating model status",
        list: [getErrorMessage(error) || "Failed to update model status"],
      });
    },
    [clearSentOverlay, queryClient, setErrorData],
  );

  const flushModelToggles = useDebounce(() => {
    const batch = buildAndConsumeToggleBatch();
    if (!batch) return;
    const { updates, previousData, togglesToSend } = batch;

    updateEnabledModels(
      { updates },
      {
        onError: (error: unknown) => {
          rollbackToggleBatch(togglesToSend, previousData, error);
        },
        onSettled: () => {
          clearSentOverlay(togglesToSend);
          queryClient.invalidateQueries({
            queryKey: ["useGetEnabledModels"],
          });
          queryClient.invalidateQueries({
            queryKey: ["useGetModelProviders"],
          });
          refreshAllModelInputs({ silent: true });
        },
      },
    );
  }, 1000);

  const flushPendingChanges = useCallback(async () => {
    // Cancel the pending debounce timer — we'll send the toggles directly
    flushModelToggles.cancel();

    const batch = buildAndConsumeToggleBatch();
    if (!batch) return;
    const { updates, previousData, togglesToSend } = batch;

    try {
      await updateEnabledModelsAsync({ updates });
      clearSentOverlay(togglesToSend);
      // Invalidate the affected queries inline so callers don't need to
      // bolt this on. The modal's onClose still triggers
      // ``refreshAllModelInputs`` afterwards to repopulate per-node
      // template options, but ``useGetEnabledModels`` consumers no longer
      // depend on the caller for cache freshness.
      queryClient.invalidateQueries({ queryKey: ["useGetEnabledModels"] });
      queryClient.invalidateQueries({ queryKey: ["useGetModelProviders"] });
    } catch (error: unknown) {
      rollbackToggleBatch(togglesToSend, previousData, error);
    }
  }, [
    flushModelToggles,
    buildAndConsumeToggleBatch,
    updateEnabledModelsAsync,
    clearSentOverlay,
    rollbackToggleBatch,
    queryClient,
  ]);

  const handleModelToggle = useCallback(
    (modelName: string, enabled: boolean) => {
      if (!providerName) return;

      // Cancel any in-flight refetch of useGetEnabledModels so its (stale)
      // result cannot overwrite the optimistic cache update below. The
      // re-overlay effect handles refetches that start AFTER this point;
      // ``cancelQueries`` covers the ones already in flight at click time.
      void queryClient.cancelQueries({ queryKey: ["useGetEnabledModels"] });

      if (Object.keys(overlayToggles.current).length === 0) {
        fallbackModelData.current =
          queryClient.getQueryData<EnabledModelsResponse>([
            "useGetEnabledModels",
          ]);
      }

      queryClient.setQueryData<EnabledModelsResponse>(
        ["useGetEnabledModels"],
        (old) => {
          if (!old) return old;
          return {
            ...old,
            enabled_models: {
              ...old.enabled_models,
              [providerName]: {
                ...old.enabled_models[providerName],
                [modelName]: enabled,
              },
            },
          };
        },
      );

      // Track in BOTH buffers: overlay for UI protection across refetches,
      // unsent for the next flush's payload.
      overlayToggles.current[modelName] = enabled;
      unsentToggles.current[modelName] = enabled;
      flushModelToggles();
    },
    [providerName, queryClient, flushModelToggles],
  );

  // Re-overlay effect — protects the pending-toggle window in its entirety,
  // not just the instant of the click. Any refetch (window focus, remount,
  // reconnect, or a stale-time expiry) that lands while ``overlayToggles``
  // has entries will surface the server's pre-toggle state into
  // ``enabledModelsData``; this effect detects the drift and re-applies the
  // pending overlay so the Switch tracks the user's intent through the
  // entire debounce + in-flight window. Once ``clearSentOverlay`` drains
  // the entry on settle, the next data emission is a no-op.
  useEffect(() => {
    if (!providerName) return;
    if (!enabledModelsData) return;
    const overlay = overlayToggles.current;
    if (Object.keys(overlay).length === 0) return;

    const current = enabledModelsData.enabled_models[providerName] ?? {};
    // Loop guard: the ``setQueryData`` below re-emits ``enabledModelsData``
    // and re-runs this effect; ``drifted`` must return false on the second
    // pass for the recursion to terminate. Don't replace this with an
    // unconditional re-apply — the second invocation finds the overlay
    // already applied, ``current[model] === enabled`` for every entry, and
    // bails. Any future refactor that removes the drift check must
    // introduce an equivalent termination condition.
    const drifted = Object.entries(overlay).some(
      ([model, enabled]) => current[model] !== enabled,
    );
    if (!drifted) return;

    queryClient.setQueryData<EnabledModelsResponse>(
      ["useGetEnabledModels"],
      (old) => {
        if (!old) return old;
        return {
          ...old,
          enabled_models: {
            ...old.enabled_models,
            [providerName]: {
              ...(old.enabled_models[providerName] ?? {}),
              ...overlay,
            },
          },
        };
      },
    );
  }, [enabledModelsData, providerName, queryClient]);

  return {
    handleModelToggle,
    flushPendingChanges,
  };
};
