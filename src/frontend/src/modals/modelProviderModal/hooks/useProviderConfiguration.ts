import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  PROVIDER_VARIABLE_MAPPING,
  ProviderVariable,
  VARIABLE_CATEGORY,
} from "@/constants/providerConstants";
import { getAxiosErrorMessage } from "@/controllers/API/helpers/get-axios-error-message";
import type { ProviderScopeParams } from "@/controllers/API/helpers/provider-scope";
import { isSettledSuccessfulQuery } from "@/controllers/API/helpers/query-cache";
import {
  getModelProvidersQueryOptions,
  useGetModelProviders,
} from "@/controllers/API/queries/models/use-get-model-providers";
import {
  getProviderVariablesQueryKey,
  useGetProviderVariables,
} from "@/controllers/API/queries/models/use-get-provider-variables";
import { useValidateProvider } from "@/controllers/API/queries/models/use-validate-provider";
import {
  getGlobalVariablesQueryKey,
  useDeleteGlobalVariables,
  useGetGlobalVariables,
  usePatchGlobalVariables,
  usePostGlobalVariables,
} from "@/controllers/API/queries/variables";
import { useRefreshModelInputs } from "@/hooks/use-refresh-model-inputs";
import useAlertStore from "@/stores/alertStore";
import type { ModelType } from "@/types/models";
import { Provider } from "../components/types";
import { useModelToggleQueue } from "./useModelToggleQueue";

// Masked value shown for configured secret fields
const MASKED_VALUE = "••••••••";

interface UseProviderConfigurationOptions extends ProviderScopeParams {
  selectedProvider: Provider | null;
}

type ValidationState = "idle" | "validating" | "valid" | "invalid";

interface UseProviderConfigurationReturn {
  // State
  variableValues: Record<string, string>;
  validationFailed: boolean;
  isSaving: boolean;
  isPending: boolean;
  isDeleting: boolean;
  validationState: ValidationState;
  validationError: string | null;
  providerVariables: ProviderVariable[];
  syncedSelectedProvider: Provider | null;

  // Handlers
  handleVariableChange: (key: string, value: string) => void;
  handleSaveAllVariables: () => Promise<void>;
  handleDisconnect: () => Promise<void>;
  handleActivateProvider: () => void;
  validateCredentials: () => Promise<boolean>;
  handleModelToggle: (
    modelName: string,
    enabled: boolean,
    modelType: ModelType,
  ) => void;
  flushPendingChanges: () => Promise<void>;
  hasUserMadeChanges: () => boolean;

  // Helpers
  isVariableConfigured: (key: string) => boolean;
  getConfiguredValue: (key: string) => string | null;

  // Derived state
  allRequiredFilled: boolean;
  hasNewValuesToSave: boolean;
  requiresConfiguration: boolean;
  canSave: boolean;
  isFetchingAfterSave: boolean;
  isFetchingAfterDisconnect: boolean;

  // Cache invalidation
  invalidateProviderQueries: () => Promise<void>;
}

export const useProviderConfiguration = ({
  selectedProvider,
  flowId,
  projectId,
}: UseProviderConfigurationOptions): UseProviderConfigurationReturn => {
  const [variableValues, setVariableValues] = useState<Record<string, string>>(
    {},
  );
  const [validationFailed, setValidationFailed] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [validationState, setValidationState] =
    useState<ValidationState>("idle");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isFetchingAfterSave, setIsFetchingAfterSave] = useState(false);
  const [isFetchingAfterDisconnect, setIsFetchingAfterDisconnect] =
    useState(false);
  const _validationTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const configurationContextKey = `${flowId ?? ""}\0${projectId ?? ""}\0${selectedProvider?.provider ?? ""}`;
  const previousConfigurationContextRef = useRef(configurationContextKey);
  const activeConfigurationContextRef = useRef<string | null>(
    configurationContextKey,
  );
  activeConfigurationContextRef.current = configurationContextKey;
  const localStateMatchesContext =
    previousConfigurationContextRef.current === configurationContextKey;

  useEffect(() => {
    activeConfigurationContextRef.current = configurationContextKey;
    return () => {
      if (activeConfigurationContextRef.current === configurationContextKey) {
        activeConfigurationContextRef.current = null;
      }
    };
  }, [configurationContextKey]);

  // Tracks whether the user has made any persisted changes during this dialog
  // session (save / activate / disconnect / model toggle). Read synchronously
  // by the modal's onClose handler to skip refreshAllModelInputs and the
  // accompanying loading affordance when the user opened the dialog and closed
  // it without touching anything.
  const hasUserMadeChangesRef = useRef(false);
  const hasUserMadeChanges = useCallback(
    () => hasUserMadeChangesRef.current,
    [],
  );

  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { mutateAsync: createGlobalVariable, isPending: isCreating } =
    usePostGlobalVariables();
  const { mutateAsync: updateGlobalVariable, isPending: isUpdating } =
    usePatchGlobalVariables();
  const { mutateAsync: deleteGlobalVariable, isPending: isDeleting } =
    useDeleteGlobalVariables();
  const providerScope = { flowId, projectId };
  const providerCatalogParams = {
    includeDeprecated: true,
    flowId,
    projectId,
    purpose: "configure" as const,
  };
  const providerCatalogQueryKey = getModelProvidersQueryOptions(
    providerCatalogParams,
  ).queryKey;
  const globalVariablesQueryKey = getGlobalVariablesQueryKey(providerScope);
  const providerVariablesQueryKey = getProviderVariablesQueryKey(providerScope);

  const { data: globalVariables = [] } = useGetGlobalVariables({
    flowId,
    projectId,
  });
  const { mutateAsync: validateProvider } = useValidateProvider();
  const { data: providerVariablesMapping = {} } = useGetProviderVariables({
    flowId,
    projectId,
  });
  const { refreshAllModelInputs } = useRefreshModelInputs();
  const {
    data: modelProviders = [],
    isError: isModelProvidersError,
    isFetched: areModelProvidersFetched,
    isFetching: isFetchingModels,
    isSuccess: isModelProvidersSuccess,
    fetchStatus: modelProvidersFetchStatus,
  } = useGetModelProviders(providerCatalogParams, {
    // Issue #13137: the previous 10s ``refetchInterval`` polled
    // ``/api/v1/models`` continuously while the Ollama card was
    // selected. Each backend call serially probed every Ollama model
    // (GET /api/tags + POST /api/show per model), so with many models
    // the request took longer than the interval and the queue grew
    // unbounded. The catalog already refreshes on credential save and
    // disconnect via ``invalidateProviderQueries``, so the timer is
    // unnecessary — leaving it removed makes the list update on
    // demand instead of on a fixed schedule.
    refetchInterval: false,
    staleTime: 1000 * 30, // 30 seconds
  });
  const hasSettledProviderCatalog =
    areModelProvidersFetched &&
    isModelProvidersSuccess &&
    !isFetchingModels &&
    modelProvidersFetchStatus === "idle" &&
    !isModelProvidersError;

  const trustedSelectedProvider = useMemo((): Provider | null => {
    if (!selectedProvider || !hasSettledProviderCatalog) return null;
    const freshProvider = modelProviders.find(
      (provider) => provider.provider === selectedProvider.provider,
    );
    if (!freshProvider) return null;
    return {
      ...selectedProvider,
      is_enabled: freshProvider.is_enabled,
      is_configured: freshProvider.is_configured,
      models: freshProvider.models || selectedProvider.models,
    };
  }, [hasSettledProviderCatalog, modelProviders, selectedProvider]);

  const isCurrentConfigurationContext = useCallback(
    (): boolean =>
      activeConfigurationContextRef.current === configurationContextKey &&
      previousConfigurationContextRef.current === configurationContextKey,
    [configurationContextKey],
  );

  const canUseCurrentProviderPolicy = useCallback(
    (providerName: string): boolean =>
      isCurrentConfigurationContext() &&
      trustedSelectedProvider?.provider === providerName &&
      isSettledSuccessfulQuery(queryClient, providerCatalogQueryKey) &&
      isSettledSuccessfulQuery(queryClient, globalVariablesQueryKey) &&
      isSettledSuccessfulQuery(queryClient, providerVariablesQueryKey),
    [
      globalVariablesQueryKey,
      providerCatalogQueryKey,
      providerVariablesQueryKey,
      queryClient,
      isCurrentConfigurationContext,
      trustedSelectedProvider,
    ],
  );

  // Invalidate all provider-related caches after successful create/update
  const invalidateProviderQueries = useCallback(async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["useGetModelProviders"] }),
      queryClient.invalidateQueries({ queryKey: ["useGetEnabledModels"] }),
      queryClient.invalidateQueries({ queryKey: ["useGetProviderVariables"] }),
      queryClient.invalidateQueries({
        queryKey: getGlobalVariablesQueryKey({ flowId, projectId }),
        exact: true,
      }),
      queryClient.refetchQueries({ queryKey: ["flows"] }),
    ]);
  }, [flowId, projectId, queryClient]);

  // Reset every local value/ref when either the provider or its authorization
  // scope changes. A credential typed in flow/project A must never repaint or
  // be persisted after the same provider becomes available in scope B.
  useEffect(() => {
    const didConfigurationContextChange =
      configurationContextKey !== previousConfigurationContextRef.current;
    previousConfigurationContextRef.current = configurationContextKey;

    if (didConfigurationContextChange) {
      setVariableValues({});
      setValidationState("idle");
      setValidationError(null);
      setValidationFailed(false);
      setIsSaving(false);
      setIsFetchingAfterSave(false);
      setIsFetchingAfterDisconnect(false);
      hasUserMadeChangesRef.current = false;
      if (_validationTimeoutRef.current) {
        clearTimeout(_validationTimeoutRef.current);
        _validationTimeoutRef.current = null;
      }

      // Force refetch models when switching provider or authorization scope.
      void invalidateProviderQueries();
    }
  }, [configurationContextKey, invalidateProviderQueries]);

  // Calculate provider variables
  const providerVariables = useMemo((): ProviderVariable[] => {
    if (!trustedSelectedProvider) return [];

    const providerName = trustedSelectedProvider.provider;
    const apiVariables = providerVariablesMapping[providerName];
    if (Array.isArray(apiVariables) && apiVariables.length > 0) {
      return apiVariables;
    }

    const staticVariableKey = PROVIDER_VARIABLE_MAPPING[providerName];
    if (staticVariableKey) {
      return [
        {
          variable_name: "API Key",
          variable_key: staticVariableKey,
          required: true,
          is_secret: true,
          is_list: false,
          options: [],
        },
      ];
    }

    return [];
  }, [trustedSelectedProvider, providerVariablesMapping]);

  const isPending =
    isCreating ||
    isUpdating ||
    isDeleting ||
    isSaving ||
    validationState === "validating";

  // Helper to get configured value for a variable from globalVariables
  const getConfiguredValue = useCallback(
    (variableKey: string): string | null => {
      const variable = globalVariables.find((v) => v.name === variableKey);
      if (variable) {
        return variable.value ?? MASKED_VALUE;
      }
      return null;
    },
    [globalVariables],
  );

  // Helper to check if a variable is already configured
  const isVariableConfigured = useCallback(
    (variableKey: string): boolean => {
      const variable = globalVariables.find((v) => v.name === variableKey);
      return Boolean(variable && variable.has_value !== false);
    },
    [globalVariables],
  );

  // Check if provider requires configuration (has any required variable)
  const requiresConfiguration = useMemo(() => {
    if (!trustedSelectedProvider) return true;
    // A provider requires configuration if it has any required variable
    return providerVariables.some((v) => v.required);
  }, [trustedSelectedProvider, providerVariables]);

  // Check if all required variables are filled in the form currently
  const allRequiredFilled = useMemo(() => {
    return providerVariables
      .filter((v) => v.required)
      .every((v) => {
        const currentValue = variableValues[v.variable_key];
        const hasNewValue =
          currentValue !== undefined && currentValue.trim() !== "";
        const isAlreadyConfigured = isVariableConfigured(v.variable_key);
        return hasNewValue || isAlreadyConfigured;
      });
  }, [providerVariables, variableValues, isVariableConfigured]);

  const isConfiguredOptionalVariableCleared = useCallback(
    (variable: ProviderVariable): boolean => {
      const draftValue = variableValues[variable.variable_key];
      return (
        !variable.required &&
        !variable.is_secret &&
        draftValue !== undefined &&
        draftValue.trim() === "" &&
        isVariableConfigured(variable.variable_key)
      );
    },
    [isVariableConfigured, variableValues],
  );

  // Check if there are any new values or explicit optional-value clears to save
  const hasNewValuesToSave = useMemo(() => {
    return providerVariables.some(
      (v) =>
        Boolean(variableValues[v.variable_key]?.trim()) ||
        isConfiguredOptionalVariableCleared(v),
    );
  }, [providerVariables, variableValues, isConfiguredOptionalVariableCleared]);

  // Build the variables object for validation
  const getVariablesForValidation = useCallback((): Record<string, string> => {
    const variables: Record<string, string> = {};
    for (const v of providerVariables) {
      const newValue = variableValues[v.variable_key]?.trim();
      if (newValue) {
        variables[v.variable_key] = newValue;
      } else if (!(v.variable_key in variableValues)) {
        // Use existing configured value
        const existing = globalVariables.find(
          (gv) => gv.name === v.variable_key,
        );
        if (existing?.value) {
          variables[v.variable_key] = existing.value;
        }
      }
    }
    return variables;
  }, [providerVariables, variableValues, globalVariables]);

  // Validate credentials with the backend
  const validateCredentials = useCallback(async (): Promise<boolean> => {
    const providerName = trustedSelectedProvider?.provider;
    if (!providerName || !canUseCurrentProviderPolicy(providerName)) {
      return false;
    }

    const variables = getVariablesForValidation();
    setValidationState("validating");
    setValidationError(null);

    const startTime = Date.now();

    try {
      const result = await validateProvider({
        provider: providerName,
        variables,
        flowId,
        projectId,
      });

      // Ensure minimum 500ms duration for better UX (prevent flickering)
      const elapsedTime = Date.now() - startTime;
      if (elapsedTime < 500) {
        await new Promise((resolve) => setTimeout(resolve, 500 - elapsedTime));
      }

      if (!isCurrentConfigurationContext()) {
        return false;
      }
      if (!canUseCurrentProviderPolicy(providerName)) {
        setValidationState("invalid");
        setValidationError(t("modelProviders.errorUnexpected"));
        return false;
      }

      if (result.valid) {
        setValidationState("valid");
        setValidationError(null);
        return true;
      } else {
        setValidationState("invalid");
        setValidationError(result.error || "Validation failed");
        return false;
      }
    } catch (error: unknown) {
      // Ensure minimum 500ms duration even on error
      const elapsedTime = Date.now() - startTime;
      if (elapsedTime < 500) {
        await new Promise((resolve) => setTimeout(resolve, 500 - elapsedTime));
      }

      if (!isCurrentConfigurationContext()) {
        return false;
      }
      setValidationState("invalid");
      setValidationError(getAxiosErrorMessage(error, "Validation failed"));
      return false;
    }
  }, [
    trustedSelectedProvider,
    canUseCurrentProviderPolicy,
    getVariablesForValidation,
    validateProvider,
    flowId,
    projectId,
    isCurrentConfigurationContext,
    t,
  ]);

  // Debounced validation removed — validation now happens only on save button click

  // Can save when all required fields are filled and there are new values
  const canSave = useMemo(() => {
    return localStateMatchesContext && hasNewValuesToSave && allRequiredFilled;
  }, [localStateMatchesContext, hasNewValuesToSave, allRequiredFilled]);

  // Handle variable input change
  const handleVariableChange = useCallback((key: string, value: string) => {
    setValidationFailed(false);
    setValidationState("idle");
    setValidationError(null);
    setVariableValues((prev) => ({
      ...prev,
      [key]: value,
    }));
  }, []);

  // Save all variables with the primary provider variable last — validates first,
  // then saves if valid
  const handleSaveAllVariables = useCallback(async () => {
    const providerName = trustedSelectedProvider?.provider;
    if (!providerName || !canUseCurrentProviderPolicy(providerName)) return;

    // Match the backend's primary-variable selection: required secret, then
    // any secret, then the first provider variable. The variables API validates
    // that field against companion values already in storage, so persist it last.
    const primaryVariableKey =
      providerVariables.find((v) => v.required && v.is_secret)?.variable_key ??
      providerVariables.find((v) => v.is_secret)?.variable_key ??
      providerVariables[0]?.variable_key;
    const variablesToSave = providerVariables
      .filter((v) => variableValues[v.variable_key]?.trim())
      .sort(
        (a, b) =>
          Number(a.variable_key === primaryVariableKey) -
          Number(b.variable_key === primaryVariableKey),
      );
    const variableKeysToReset = new Set(
      providerVariables
        .filter(isConfiguredOptionalVariableCleared)
        .map((v) => v.variable_key),
    );
    const variablesToReset = globalVariables.filter((v) =>
      variableKeysToReset.has(v.name),
    );

    if (variablesToSave.length === 0 && variablesToReset.length === 0) return;

    // Reset-only saves do not introduce credentials to validate. When
    // another value is being saved, validate the effective post-clear config.
    if (variablesToSave.length > 0) {
      const isValid = await validateCredentials();
      if (!isValid || !canUseCurrentProviderPolicy(providerName)) return;
    }
    setIsSaving(true);
    setValidationFailed(false);
    let hasPersistedVariable = false;
    let hasAttemptedProviderInvalidation = false;
    const refreshProviderCaches = async (): Promise<void> => {
      hasAttemptedProviderInvalidation = true;
      await invalidateProviderQueries();
    };

    try {
      // Reset optional values first so a following primary credential write is
      // validated against the effective post-reset configuration. Keeping the
      // row preserves its UUID and any resource shares attached to it.
      for (const variable of variablesToReset) {
        if (!canUseCurrentProviderPolicy(providerName)) {
          if (hasPersistedVariable) await refreshProviderCaches();
          return;
        }
        await updateGlobalVariable({
          id: variable.id,
          value: "",
          flowId,
          projectId,
        });
        hasPersistedVariable = true;

        // Keep the exact scoped variable cache settled before the next write,
        // matching the policy checks used for non-empty updates below.
        if (!isSettledSuccessfulQuery(queryClient, globalVariablesQueryKey)) {
          await queryClient.refetchQueries(
            { queryKey: globalVariablesQueryKey, exact: true },
            { cancelRefetch: false },
          );
        }
        if (!canUseCurrentProviderPolicy(providerName)) {
          await refreshProviderCaches();
          return;
        }
      }

      // Persist each companion field before starting the primary-variable
      // request so backend validation can read the complete configuration.
      for (const variable of variablesToSave) {
        if (!canUseCurrentProviderPolicy(providerName)) {
          if (hasPersistedVariable) await refreshProviderCaches();
          return;
        }
        const value = variableValues[variable.variable_key].trim();
        const existingVariable = globalVariables.find(
          (v) => v.name === variable.variable_key,
        );
        const variableType = variable.is_secret
          ? VARIABLE_CATEGORY.CREDENTIAL
          : VARIABLE_CATEGORY.GLOBAL;

        if (existingVariable) {
          await updateGlobalVariable({
            id: existingVariable.id,
            value,
            flowId,
            projectId,
          });
        } else {
          await createGlobalVariable({
            name: variable.variable_key,
            value,
            type: variableType,
            category: VARIABLE_CATEGORY.GLOBAL,
            default_fields: [],
            flowId,
            projectId,
          });
        }
        hasPersistedVariable = true;

        // Variable mutations start an exact scoped-cache refetch in onSettled.
        // Wait for that self-induced refresh instead of treating it as a policy
        // revocation, then re-run every fail-closed policy check before the next
        // write or the completion path.
        if (!isSettledSuccessfulQuery(queryClient, globalVariablesQueryKey)) {
          await queryClient.refetchQueries(
            { queryKey: globalVariablesQueryKey, exact: true },
            { cancelRefetch: false },
          );
        }
        if (!canUseCurrentProviderPolicy(providerName)) {
          await refreshProviderCaches();
          return;
        }
      }

      if (!canUseCurrentProviderPolicy(providerName)) {
        await refreshProviderCaches();
        return;
      }

      // All succeeded. Await the cache refresh directly instead of relying on
      // React to render an intermediate `isFetching` state, which a fast
      // refetch can enter and leave in the same batch.
      hasUserMadeChangesRef.current = true;
      setIsFetchingAfterSave(true);
      await refreshProviderCaches();

      if (isCurrentConfigurationContext()) {
        setVariableValues({});
        setSuccessData({
          title: t("modelProviders.configurationSaved", {
            provider: providerName,
          }),
        });
        void refreshAllModelInputs({ silent: true });
      }
    } catch (error: unknown) {
      if (hasPersistedVariable) {
        hasUserMadeChangesRef.current = true;
        if (!hasAttemptedProviderInvalidation) {
          try {
            await refreshProviderCaches();
          } catch {
            // Preserve the original mutation/refetch error for the current UI.
          }
        }
      }
      if (isCurrentConfigurationContext()) {
        setValidationFailed(true);
        setErrorData({
          title: t("modelProviders.errorSavingConfiguration"),
          list: [
            getAxiosErrorMessage(error, t("modelProviders.errorUnexpected")),
          ],
        });
      }
    } finally {
      if (isCurrentConfigurationContext()) {
        setIsSaving(false);
        setIsFetchingAfterSave(false);
      }
    }
  }, [
    trustedSelectedProvider,
    canUseCurrentProviderPolicy,
    providerVariables,
    variableValues,
    globalVariables,
    isConfiguredOptionalVariableCleared,
    createGlobalVariable,
    updateGlobalVariable,
    flowId,
    projectId,
    queryClient,
    globalVariablesQueryKey,
    validateCredentials,
    t,
    setSuccessData,
    setErrorData,
    invalidateProviderQueries,
    refreshAllModelInputs,
    isCurrentConfigurationContext,
  ]);

  // Activate providers that don't need API keys (e.g., Ollama)
  const handleActivateProvider = useCallback(async () => {
    const providerName = trustedSelectedProvider?.provider;
    if (!providerName || !canUseCurrentProviderPolicy(providerName)) return;

    // Get the first variable (usually the base URL for providers like Ollama)
    const firstVariable = providerVariables[0];
    const variableName =
      firstVariable?.variable_key || PROVIDER_VARIABLE_MAPPING[providerName];

    if (!variableName) {
      setErrorData({
        title: t("modelProviders.errorInvalidProvider"),
        list: [
          t("modelProviders.errorInvalidProviderMessage", {
            provider: providerName,
          }),
        ],
      });
      return;
    }

    const existingVariable = globalVariables.find(
      (v) => v.name === variableName,
    );
    const placeholderValue =
      firstVariable?.options?.[0] || "http://localhost:11434";

    try {
      if (existingVariable) {
        await updateGlobalVariable({
          id: existingVariable.id,
          value: placeholderValue,
          flowId,
          projectId,
        });
      } else {
        await createGlobalVariable({
          name: variableName,
          value: placeholderValue,
          type: VARIABLE_CATEGORY.CREDENTIAL,
          category: VARIABLE_CATEGORY.GLOBAL,
          default_fields: [],
          flowId,
          projectId,
        });
      }

      if (isCurrentConfigurationContext()) {
        hasUserMadeChangesRef.current = true;
      }
      await invalidateProviderQueries();

      if (isCurrentConfigurationContext()) {
        setSuccessData({
          title: t("modelProviders.providerActivated", {
            provider: providerName,
          }),
        });
      }
    } catch (error: unknown) {
      if (isCurrentConfigurationContext()) {
        setErrorData({
          title: t("modelProviders.errorActivatingProvider"),
          list: [
            getAxiosErrorMessage(error, t("modelProviders.errorUnexpected")),
          ],
        });
      }
    }
  }, [
    trustedSelectedProvider,
    canUseCurrentProviderPolicy,
    providerVariables,
    globalVariables,
    createGlobalVariable,
    updateGlobalVariable,
    flowId,
    projectId,
    setSuccessData,
    setErrorData,
    invalidateProviderQueries,
    isCurrentConfigurationContext,
  ]);

  // Disconnect / Deactivate provider
  const handleDisconnect = useCallback(async () => {
    const providerName = trustedSelectedProvider?.provider;
    if (!providerName || !canUseCurrentProviderPolicy(providerName)) return;

    // Resolve every variable key associated with this provider so
    // multi-variable providers (e.g. OpenRouter's API key + attribution
    // headers, IBM WatsonX's apikey + project_id + url) are fully removed.
    // The dynamic ``providerVariables`` list comes from
    // ``GET /api/v1/models/provider-variable-mapping`` and is the source of
    // truth; fall back to the deprecated ``PROVIDER_VARIABLE_MAPPING`` only
    // when the API call has not resolved yet (or the provider is missing
    // from the dynamic mapping for some reason).
    const variableKeys = new Set<string>();
    for (const v of providerVariables) {
      if (v.variable_key) variableKeys.add(v.variable_key);
    }
    if (variableKeys.size === 0) {
      const staticKey = PROVIDER_VARIABLE_MAPPING[providerName];
      if (staticKey) variableKeys.add(staticKey);
    }

    const variablesToDelete = globalVariables.filter((v) =>
      variableKeys.has(v.name),
    );
    if (variablesToDelete.length === 0) return;

    try {
      // Delete in parallel — backend already cleans up per-provider enabled
      // and disabled model lists on the primary credential delete, so order
      // does not matter.
      const deletionResults = await Promise.allSettled(
        variablesToDelete.map((v) =>
          deleteGlobalVariable({ id: v.id, flowId, projectId }),
        ),
      );
      const hasSuccessfulDeletion = deletionResults.some(
        (result) => result.status === "fulfilled",
      );
      const failedDeletion = deletionResults.find(
        (result) => result.status === "rejected",
      );

      if (hasSuccessfulDeletion && isCurrentConfigurationContext()) {
        hasUserMadeChangesRef.current = true;
        setIsFetchingAfterDisconnect(true);
      }
      if (hasSuccessfulDeletion) {
        await invalidateProviderQueries();
      }

      if (failedDeletion) {
        throw failedDeletion.reason;
      }

      if (isCurrentConfigurationContext()) {
        setSuccessData({
          title: t("modelProviders.providerDisconnected", {
            provider: providerName,
          }),
        });
        void refreshAllModelInputs({ silent: true });
      }
    } catch (error: unknown) {
      if (isCurrentConfigurationContext()) {
        setErrorData({
          title: t("modelProviders.errorDisconnectingProvider"),
          list: [
            getAxiosErrorMessage(error, t("modelProviders.errorUnexpected")),
          ],
        });
      }
    } finally {
      if (isCurrentConfigurationContext()) {
        setIsFetchingAfterDisconnect(false);
      }
    }
  }, [
    trustedSelectedProvider,
    canUseCurrentProviderPolicy,
    providerVariables,
    globalVariables,
    deleteGlobalVariable,
    flowId,
    projectId,
    setSuccessData,
    setErrorData,
    invalidateProviderQueries,
    refreshAllModelInputs,
    isCurrentConfigurationContext,
  ]);

  const { handleModelToggle: queueModelToggle, flushPendingChanges } =
    useModelToggleQueue({
      providerName: trustedSelectedProvider?.provider,
      flowId,
      projectId,
    });

  const handleModelToggle = useCallback(
    (modelName: string, enabled: boolean, modelType: ModelType) => {
      if (!trustedSelectedProvider?.provider) return;
      hasUserMadeChangesRef.current = true;
      queueModelToggle(modelName, enabled, modelType);
    },
    [trustedSelectedProvider, queueModelToggle],
  );

  return {
    variableValues: localStateMatchesContext ? variableValues : {},
    validationFailed,
    isSaving,
    isPending,
    isDeleting,
    validationState,
    validationError,
    providerVariables,
    syncedSelectedProvider: trustedSelectedProvider,

    // Handlers
    handleVariableChange,
    handleSaveAllVariables,
    handleDisconnect,
    handleActivateProvider,
    validateCredentials,
    handleModelToggle,
    flushPendingChanges,
    hasUserMadeChanges,

    // Helpers
    isVariableConfigured,
    getConfiguredValue,

    // Derived state
    allRequiredFilled,
    hasNewValuesToSave,
    requiresConfiguration,
    canSave,
    isFetchingAfterSave,
    isFetchingAfterDisconnect,

    // Cache invalidation
    invalidateProviderQueries,
  };
};
