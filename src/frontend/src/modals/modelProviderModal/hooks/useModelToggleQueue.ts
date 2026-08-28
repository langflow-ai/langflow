import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { ProviderScopeParams } from "@/controllers/API/helpers/provider-scope";
import { isSettledSuccessfulQuery } from "@/controllers/API/helpers/query-cache";
import {
  EnabledModelsResponse,
  getEnabledModelsQueryKey,
  useGetEnabledModels,
} from "@/controllers/API/queries/models/use-get-enabled-models";
import {
  ModelStatusUpdate,
  useUpdateEnabledModels,
} from "@/controllers/API/queries/models/use-update-enabled-models";
import { useDebounce } from "@/hooks/use-debounce";
import { useRefreshModelInputs } from "@/hooks/use-refresh-model-inputs";
import useAlertStore from "@/stores/alertStore";
import type { ModelType } from "@/types/models";

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

type ToggleMap = Map<string, ModelStatusUpdate>;

const getToggleContextIdentity = (
  providerName: string | null | undefined,
  flowId?: string,
  projectId?: string,
): string =>
  JSON.stringify([providerName ?? null, flowId ?? null, projectId ?? null]);

const getToggleIdentity = (
  contextIdentity: string,
  providerName: string,
  modelName: string,
  modelType: ModelType,
): string =>
  JSON.stringify([contextIdentity, providerName, modelType, modelName]);

const getToggleEnabled = (
  data: EnabledModelsResponse,
  update: ModelStatusUpdate,
): boolean => {
  const typedProvider = data.enabled_models_by_type?.[update.provider];
  if (typedProvider !== undefined) {
    return typedProvider[update.model_type]?.[update.model_id] ?? false;
  }
  return data.enabled_models[update.provider]?.[update.model_id] ?? false;
};

const applyToggleToEnabledModels = (
  data: EnabledModelsResponse,
  update: ModelStatusUpdate,
): EnabledModelsResponse => {
  const {
    provider,
    model_id: modelName,
    model_type: modelType,
    enabled,
  } = update;
  const typedProvider = data.enabled_models_by_type?.[provider];

  // A provider without a typed map is using the legacy response contract even
  // if another provider in the same response is typed. Preserve its flat
  // optimistic update while still sending model_type to the mutation endpoint.
  if (typedProvider === undefined) {
    return {
      ...data,
      enabled_models: {
        ...data.enabled_models,
        [provider]: {
          ...(data.enabled_models[provider] ?? {}),
          [modelName]: enabled,
        },
      },
    };
  }

  const otherType: ModelType = modelType === "llm" ? "embeddings" : "llm";
  const nextTypedProvider = {
    ...typedProvider,
    [modelType]: {
      ...(typedProvider[modelType] ?? {}),
      [modelName]: enabled,
    },
  };
  const flatEnabled =
    enabled || (nextTypedProvider[otherType]?.[modelName] ?? false);

  return {
    ...data,
    enabled_models: {
      ...data.enabled_models,
      [provider]: {
        ...(data.enabled_models[provider] ?? {}),
        [modelName]: flatEnabled,
      },
    },
    enabled_models_by_type: {
      ...data.enabled_models_by_type,
      [provider]: nextTypedProvider,
    },
  };
};

const applyToggleMap = (
  data: EnabledModelsResponse,
  toggles: ToggleMap,
): EnabledModelsResponse => {
  let nextData = data;
  for (const update of toggles.values()) {
    nextData = applyToggleToEnabledModels(nextData, update);
  }
  return nextData;
};

export interface UseModelToggleQueueOptions extends ProviderScopeParams {
  /**
   * Provider whose models the user is toggling. ``null`` short-circuits all
   * handlers — useful while the modal is still resolving the selection.
   */
  providerName: string | null | undefined;
}

export interface UseModelToggleQueueReturn {
  handleModelToggle: (
    modelName: string,
    enabled: boolean,
    modelType: ModelType,
  ) => void;
  flushPendingChanges: () => Promise<void>;
}

interface ToggleBatch {
  updates: ModelStatusUpdate[];
  previousData: EnabledModelsResponse | undefined;
  togglesToSend: ToggleMap;
  queryKey: ReturnType<typeof getEnabledModelsQueryKey>;
  flowId?: string;
  projectId?: string;
}

interface ActiveToggleContext {
  identity: string;
  queryKey: ReturnType<typeof getEnabledModelsQueryKey>;
  flowId?: string;
  projectId?: string;
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
  flowId,
  projectId,
}: UseModelToggleQueueOptions): UseModelToggleQueueReturn => {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutate: updateEnabledModels, mutateAsync: updateEnabledModelsAsync } =
    useUpdateEnabledModels({ retry: 0 });
  const { refreshAllModelInputs } = useRefreshModelInputs();
  const providerScope = {
    flowId,
    projectId,
    purpose: "configure" as const,
  };
  const enabledModelsQueryKey = getEnabledModelsQueryKey(providerScope);
  const currentContextIdentity = getToggleContextIdentity(
    providerName,
    flowId,
    projectId,
  );
  const {
    data: enabledModelsData,
    isSuccess: isEnabledModelsSuccess,
    isFetching: isEnabledModelsFetching,
    isFetchedAfterMount: isEnabledModelsFetchedAfterMount,
    fetchStatus: enabledModelsFetchStatus,
  } = useGetEnabledModels(providerScope);
  const enabledModelsQueryIsFresh =
    !!enabledModelsData &&
    isEnabledModelsSuccess &&
    !isEnabledModelsFetching &&
    isEnabledModelsFetchedAfterMount &&
    enabledModelsFetchStatus === "idle";
  const enabledModelsIncludeProvider =
    !!providerName &&
    !!enabledModelsData &&
    Object.hasOwn(enabledModelsData.enabled_models, providerName);

  const canMutateEnabledModels = useCallback(
    () =>
      enabledModelsQueryIsFresh &&
      enabledModelsIncludeProvider &&
      isSettledSuccessfulQuery(queryClient, enabledModelsQueryKey),
    [
      enabledModelsQueryIsFresh,
      enabledModelsIncludeProvider,
      queryClient,
      enabledModelsQueryKey,
    ],
  );

  const overlayToggles = useRef<ToggleMap>(new Map());
  const unsentToggles = useRef<ToggleMap>(new Map());
  const fallbackModelData = useRef<EnabledModelsResponse | undefined>(
    undefined,
  );
  const activeToggleContext = useRef<ActiveToggleContext | undefined>(
    undefined,
  );

  // After a mutation settles, remove its entries from the overlay — but
  // only when the current overlay value still matches what we sent. A
  // mismatch means the user re-toggled the same model mid-flight; that
  // entry already sits in ``unsentToggles`` for the next flush and must
  // not be dropped from the overlay until its own mutation settles.
  const clearSentOverlay = useCallback((sent: ToggleMap) => {
    for (const [key, sentUpdate] of sent) {
      if (overlayToggles.current.get(key)?.enabled === sentUpdate.enabled) {
        overlayToggles.current.delete(key);
      }
    }
    if (overlayToggles.current.size === 0) {
      fallbackModelData.current = undefined;
      activeToggleContext.current = undefined;
    }
  }, []);

  const discardPendingToggleContext = useCallback(() => {
    const hadUnsentToggles = unsentToggles.current.size > 0;
    const discardedContext = activeToggleContext.current;
    const previousData = fallbackModelData.current;
    unsentToggles.current = new Map();
    overlayToggles.current = new Map();
    fallbackModelData.current = undefined;
    activeToggleContext.current = undefined;

    if (discardedContext) {
      if (previousData) {
        queryClient.setQueryData(discardedContext.queryKey, previousData);
      }
      // setQueryData marks a query successful and clears invalidation. Restore
      // the rollback snapshot for display only, then immediately mark that
      // exact policy cache untrusted so stale grants cannot become actionable.
      void queryClient.invalidateQueries({
        queryKey: discardedContext.queryKey,
        exact: true,
      });
    }
    if (hadUnsentToggles) {
      setErrorData({
        title: t("errors.updateModelStatus"),
        list: [t("modelProviders.errorUnexpected")],
      });
    }
  }, [queryClient, setErrorData, t]);

  // Shared flush prelude: builds the mutation payload, snapshots the
  // pre-toggle cache for rollback, and drains ``unsentToggles`` so a
  // follow-up flush triggered by a new user toggle cannot resend what we
  // just sent. Returns null when there's nothing to do so callers can
  // bail symmetrically.
  const buildAndConsumeToggleBatch = useCallback((): ToggleBatch | null => {
    if (!providerName || unsentToggles.current.size === 0) return null;
    const activeContext = activeToggleContext.current;
    if (!activeContext || activeContext.identity !== currentContextIdentity) {
      discardPendingToggleContext();
      return null;
    }
    if (!canMutateEnabledModels()) {
      discardPendingToggleContext();
      return null;
    }

    const togglesToSend = new Map(unsentToggles.current);

    const updates = Array.from(togglesToSend.values());

    const previousData = fallbackModelData.current;
    unsentToggles.current = new Map();

    return {
      updates,
      previousData,
      togglesToSend,
      queryKey: activeContext.queryKey,
      flowId: activeContext.flowId,
      projectId: activeContext.projectId,
    };
  }, [
    providerName,
    currentContextIdentity,
    canMutateEnabledModels,
    discardPendingToggleContext,
  ]);

  // Shared error-path: drain the overlay BEFORE restoring previousData so
  // the re-overlay effect (triggered by setQueryData below) can't re-apply
  // a stale overlay over the rollback we just performed.
  const rollbackToggleBatch = useCallback(
    (
      togglesToSend: ToggleMap,
      previousData: EnabledModelsResponse | undefined,
      queryKey: ReturnType<typeof getEnabledModelsQueryKey>,
      error: unknown,
    ) => {
      clearSentOverlay(togglesToSend);
      if (previousData) {
        queryClient.setQueryData(queryKey, previousData);
      }
      setErrorData({
        title: t("errors.updateModelStatus"),
        list: [getErrorMessage(error) || "Failed to update model status"],
      });
    },
    [clearSentOverlay, queryClient, setErrorData, t],
  );

  const flushModelToggles = useDebounce(() => {
    const batch = buildAndConsumeToggleBatch();
    if (!batch) return;
    const {
      updates,
      previousData,
      togglesToSend,
      queryKey,
      flowId: batchFlowId,
      projectId: batchProjectId,
    } = batch;

    updateEnabledModels(
      { updates, flowId: batchFlowId, projectId: batchProjectId },
      {
        onError: (error: unknown) => {
          rollbackToggleBatch(togglesToSend, previousData, queryKey, error);
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

  useEffect(() => {
    const activeContext = activeToggleContext.current;
    if (activeContext && activeContext.identity !== currentContextIdentity) {
      flushModelToggles.cancel();
      discardPendingToggleContext();
    }
  }, [currentContextIdentity, discardPendingToggleContext, flushModelToggles]);

  const flushOnUnmountRef = useRef(flushModelToggles);
  const discardOnUnmountRef = useRef(discardPendingToggleContext);
  flushOnUnmountRef.current = flushModelToggles;
  discardOnUnmountRef.current = discardPendingToggleContext;
  useEffect(
    () => () => {
      // Scope-keyed modal navigation unmounts this hook instead of rerendering
      // it with the next identity. Cancel the surviving lodash timer and roll
      // back only unsent intent; an explicit close already consumes its batch
      // through flushPendingChanges before unmount.
      flushOnUnmountRef.current.cancel();
      discardOnUnmountRef.current();
    },
    [],
  );

  const flushPendingChanges = useCallback(async () => {
    // Cancel the pending debounce timer — we'll send the toggles directly
    flushModelToggles.cancel();

    const batch = buildAndConsumeToggleBatch();
    if (!batch) return;
    const {
      updates,
      previousData,
      togglesToSend,
      queryKey,
      flowId: batchFlowId,
      projectId: batchProjectId,
    } = batch;

    try {
      await updateEnabledModelsAsync({
        updates,
        flowId: batchFlowId,
        projectId: batchProjectId,
      });
      clearSentOverlay(togglesToSend);
      // Invalidate the affected queries inline so callers don't need to
      // bolt this on. The modal's onClose still triggers
      // ``refreshAllModelInputs`` afterwards to repopulate per-node
      // template options, but ``useGetEnabledModels`` consumers no longer
      // depend on the caller for cache freshness.
      queryClient.invalidateQueries({ queryKey: ["useGetEnabledModels"] });
      queryClient.invalidateQueries({ queryKey: ["useGetModelProviders"] });
    } catch (error: unknown) {
      rollbackToggleBatch(togglesToSend, previousData, queryKey, error);
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
    (modelName: string, enabled: boolean, modelType: ModelType) => {
      if (!providerName || !canMutateEnabledModels()) return;
      const activeContext = activeToggleContext.current;
      if (activeContext && activeContext.identity !== currentContextIdentity) {
        flushModelToggles.cancel();
        discardPendingToggleContext();
        return;
      }

      const update: ModelStatusUpdate = {
        provider: providerName,
        model_id: modelName,
        model_type: modelType,
        enabled,
      };
      const toggleIdentity = getToggleIdentity(
        currentContextIdentity,
        providerName,
        modelName,
        modelType,
      );

      // Cancel any in-flight refetch of useGetEnabledModels so its (stale)
      // result cannot overwrite the optimistic cache update below. The
      // re-overlay effect handles refetches that start AFTER this point;
      // ``cancelQueries`` covers the ones already in flight at click time.
      void queryClient.cancelQueries({ queryKey: enabledModelsQueryKey });

      if (overlayToggles.current.size === 0) {
        fallbackModelData.current =
          queryClient.getQueryData<EnabledModelsResponse>(
            enabledModelsQueryKey,
          );
        activeToggleContext.current = {
          identity: currentContextIdentity,
          queryKey: enabledModelsQueryKey,
          flowId,
          projectId,
        };
      }

      queryClient.setQueryData<EnabledModelsResponse>(
        enabledModelsQueryKey,
        (old) => {
          if (!old) return old;
          return applyToggleToEnabledModels(old, update);
        },
      );

      // Track in BOTH buffers: overlay for UI protection across refetches,
      // unsent for the next flush's payload.
      overlayToggles.current.set(toggleIdentity, update);
      unsentToggles.current.set(toggleIdentity, update);
      flushModelToggles();
    },
    [
      providerName,
      currentContextIdentity,
      canMutateEnabledModels,
      queryClient,
      flushModelToggles,
      enabledModelsQueryKey,
      discardPendingToggleContext,
      flowId,
      projectId,
    ],
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
    if (overlay.size === 0) return;

    const includesRevokedProvider = Array.from(overlay.values()).some(
      (update) =>
        !Object.hasOwn(enabledModelsData.enabled_models, update.provider),
    );
    if (includesRevokedProvider) {
      flushModelToggles.cancel();
      discardPendingToggleContext();
      return;
    }

    // Loop guard: the ``setQueryData`` below re-emits ``enabledModelsData``
    // and re-runs this effect; ``drifted`` must return false on the second
    // pass for the recursion to terminate. Don't replace this with an
    // unconditional re-apply — the second invocation finds the overlay
    // already applied, ``getToggleEnabled`` matches every queued update, and
    // bails. Any future refactor that removes the drift check must
    // introduce an equivalent termination condition.
    const drifted = Array.from(overlay.values()).some(
      (update) =>
        getToggleEnabled(enabledModelsData, update) !== update.enabled,
    );
    if (!drifted) return;

    queryClient.setQueryData<EnabledModelsResponse>(
      enabledModelsQueryKey,
      (old) => {
        if (!old) return old;
        return applyToggleMap(old, overlay);
      },
    );
  }, [
    enabledModelsData,
    providerName,
    queryClient,
    enabledModelsQueryKey,
    flushModelToggles,
    discardPendingToggleContext,
  ]);

  return {
    handleModelToggle,
    flushPendingChanges,
  };
};
