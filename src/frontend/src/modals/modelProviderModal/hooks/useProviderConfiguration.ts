import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  PROVIDER_VARIABLE_MAPPING,
  ProviderVariable,
  VARIABLE_CATEGORY,
} from "@/constants/providerConstants";
import {
  useDeleteGlobalVariables,
  useGetGlobalVariables,
  usePatchGlobalVariables,
  usePostGlobalVariables,
} from "@/controllers/API/queries/variables";
import { useValidateProvider } from "@/controllers/API/queries/models/use-validate-provider";
import { useGetProviderVariables } from "@/controllers/API/queries/models/use-get-provider-variables";
import { useUpdateEnabledModels } from "@/controllers/API/queries/models/use-update-enabled-models";
import { EnabledModelsResponse } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { useDebounce } from "@/hooks/use-debounce";
import useAlertStore from "@/stores/alertStore";
import { Provider } from "../components/types";

// Masked value shown for configured secret fields
const MASKED_VALUE = "••••••••";

interface UseProviderConfigurationOptions {
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
  handleModelToggle: (modelName: string, enabled: boolean) => void;

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
  invalidateProviderQueries: () => void;
}

export const useProviderConfiguration = ({
  selectedProvider,
}: UseProviderConfigurationOptions): UseProviderConfigurationReturn => {
  const [variableValues, setVariableValues] = useState<Record<string, string>>(
    {},
  );
  const [syncedSelectedProvider, setSyncedSelectedProvider] =
    useState<Provider | null>(selectedProvider);
  const [validationFailed, setValidationFailed] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [validationState, setValidationState] =
    useState<ValidationState>("idle");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isFetchingAfterSave, setIsFetchingAfterSave] = useState(false);
  const [isFetchingAfterDisconnect, setIsFetchingAfterDisconnect] =
    useState(false);
  const validationTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );

  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { mutateAsync: createGlobalVariable, isPending: isCreating } =
    usePostGlobalVariables();
  const { mutateAsync: updateGlobalVariable, isPending: isUpdating } =
    usePatchGlobalVariables();
  const { mutateAsync: deleteGlobalVariable, isPending: isDeleting } =
    useDeleteGlobalVariables();
  const { data: globalVariables = [] } = useGetGlobalVariables();
  const { mutateAsync: validateProvider } = useValidateProvider();
  const { data: providerVariablesMapping = {} } = useGetProviderVariables();
  const { mutate: updateEnabledModels } = useUpdateEnabledModels({ retry: 0 });
  const { data: modelProviders = [], isFetching: isFetchingModels } =
    useGetModelProviders(
      {},
      {
        refetchInterval:
          syncedSelectedProvider?.provider?.toLowerCase() === "ollama"
            ? 10000
            : false,
        staleTime: 1000 * 30, // 30 seconds
      },
    );

  // Invalidate all provider-related caches after successful create/update
  const invalidateProviderQueries = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["useGetModelProviders"] });
    queryClient.invalidateQueries({ queryKey: ["useGetEnabledModels"] });
    queryClient.invalidateQueries({ queryKey: ["useGetGlobalVariables"] });
    queryClient.refetchQueries({ queryKey: ["flows"] });
  }, [queryClient]);

  // Clear isFetchingAfterSave/Disconnect once the models refetch settles
  // We use fetchingSeenRef to avoid clearing prematurely on the first render
  // before react-query has actually started the refetch (isFetchingModels lags by 1 tick).
  const clearValuesAfterFetchRef = useRef(false);
  const pendingSuccessTitleRef = useRef<string | null>(null);
  const fetchingSeenRef = useRef(false);
  useEffect(() => {
    const isWaiting = isFetchingAfterSave || isFetchingAfterDisconnect;
    if (isFetchingModels && isWaiting) {
      // Mark that we've seen the refetch actually start
      fetchingSeenRef.current = true;
    }
    if (!isFetchingModels && fetchingSeenRef.current && isWaiting) {
      // Refetch has completed — now safe to clear
      fetchingSeenRef.current = false;
      if (isFetchingAfterSave) {
        setIsFetchingAfterSave(false);
        if (clearValuesAfterFetchRef.current) {
          clearValuesAfterFetchRef.current = false;
          setVariableValues({});
        }
        if (pendingSuccessTitleRef.current) {
          setSuccessData({ title: pendingSuccessTitleRef.current });
          pendingSuccessTitleRef.current = null;
        }
      }
      if (isFetchingAfterDisconnect) {
        setIsFetchingAfterDisconnect(false);
      }
    }
  }, [isFetchingModels, isFetchingAfterSave, isFetchingAfterDisconnect]);

  // Keep syncedSelectedProvider in sync with prop and reset state on provider change
  useEffect(() => {
    if (selectedProvider?.provider !== syncedSelectedProvider?.provider) {
      setVariableValues({});
      setValidationState("idle");
      setValidationError(null);
      setValidationFailed(false);

      // Force refetch models when switching providers
      invalidateProviderQueries();
    }
    setSyncedSelectedProvider(selectedProvider);
  }, [
    selectedProvider,
    invalidateProviderQueries,
    syncedSelectedProvider?.provider,
  ]);

  // Sync selectedProvider with fresh data when model providers are refetched
  useEffect(() => {
    if (syncedSelectedProvider && modelProviders.length > 0) {
      const freshProvider = modelProviders.find(
        (p) => p.provider === syncedSelectedProvider.provider,
      );
      if (freshProvider) {
        const hasModelsChanged =
          JSON.stringify(freshProvider.models) !==
          JSON.stringify(syncedSelectedProvider.models);
        const hasStatusChanged =
          freshProvider.is_enabled !== syncedSelectedProvider.is_enabled ||
          freshProvider.is_configured !== syncedSelectedProvider.is_configured;

        if (hasModelsChanged || hasStatusChanged) {
          setSyncedSelectedProvider({
            ...syncedSelectedProvider,
            is_enabled: freshProvider.is_enabled,
            is_configured: freshProvider.is_configured,
            models: freshProvider.models || syncedSelectedProvider.models,
          });
        }
      }
    }
  }, [modelProviders, syncedSelectedProvider]);

  // Calculate provider variables
  const providerVariables = useMemo((): ProviderVariable[] => {
    if (!syncedSelectedProvider) return [];

    const providerName = syncedSelectedProvider.provider;
    const apiVariables = providerVariablesMapping[providerName];
    if (apiVariables && apiVariables.length > 0) {
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
  }, [syncedSelectedProvider, providerVariablesMapping]);

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
        return variable.value || MASKED_VALUE;
      }
      return null;
    },
    [globalVariables],
  );

  // Helper to check if a variable is already configured
  const isVariableConfigured = useCallback(
    (variableKey: string): boolean => {
      return globalVariables.some((v) => v.name === variableKey);
    },
    [globalVariables],
  );

  // Check if provider requires configuration (has any required variable)
  const requiresConfiguration = useMemo(() => {
    if (!selectedProvider) return true;
    // A provider requires configuration if it has any required variable
    return providerVariables.some((v) => v.required);
  }, [selectedProvider, providerVariables]);

  // Check if all required variables are filled in the form currently
  const allRequiredFilled = useMemo(() => {
    return providerVariables
      .filter((v) => v.required)
      .every((v) => {
        const currentValue = variableValues[v.variable_key];
        const hasNewValue =
          currentValue !== undefined && currentValue.trim() !== "";
        const isAlreadyConfigured = globalVariables.some(
          (gv) => gv.name === v.variable_key,
        );
        return hasNewValue || isAlreadyConfigured;
      });
  }, [providerVariables, variableValues, globalVariables]);

  // Check if there are any new values to save
  const hasNewValuesToSave = useMemo(() => {
    return providerVariables.some((v) =>
      variableValues[v.variable_key]?.trim(),
    );
  }, [providerVariables, variableValues]);

  // Build the variables object for validation
  const getVariablesForValidation = useCallback((): Record<string, string> => {
    const variables: Record<string, string> = {};
    for (const v of providerVariables) {
      const newValue = variableValues[v.variable_key]?.trim();
      if (newValue) {
        variables[v.variable_key] = newValue;
      } else {
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
    if (!selectedProvider) return false;

    const variables = getVariablesForValidation();
    setValidationState("validating");
    setValidationError(null);

    const startTime = Date.now();

    try {
      const result = await validateProvider({
        provider: selectedProvider.provider,
        variables,
      });

      // Ensure minimum 500ms duration for better UX (prevent flickering)
      const elapsedTime = Date.now() - startTime;
      if (elapsedTime < 500) {
        await new Promise((resolve) => setTimeout(resolve, 500 - elapsedTime));
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
    } catch (error: any) {
      // Ensure minimum 500ms duration even on error
      const elapsedTime = Date.now() - startTime;
      if (elapsedTime < 500) {
        await new Promise((resolve) => setTimeout(resolve, 500 - elapsedTime));
      }

      setValidationState("invalid");
      setValidationError(error?.message || "Validation failed");
      return false;
    }
  }, [selectedProvider, getVariablesForValidation, validateProvider]);

  // Debounced validation removed — validation now happens only on save button click

  // Can save when all required fields are filled and there are new values
  const canSave = useMemo(() => {
    return hasNewValuesToSave && allRequiredFilled;
  }, [hasNewValuesToSave, allRequiredFilled]);

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

  // Save all variables in parallel — validates first, then saves if valid
  const handleSaveAllVariables = useCallback(async () => {
    if (!selectedProvider) return;

    const variablesToSave = providerVariables.filter((v) =>
      variableValues[v.variable_key]?.trim(),
    );

    if (variablesToSave.length === 0) return;

    // Validate first
    const isValid = await validateCredentials();
    if (!isValid) return;
    setIsSaving(true);
    setValidationFailed(false);

    try {
      // Fire all mutations in parallel
      await Promise.all(
        variablesToSave.map(async (variable) => {
          const value = variableValues[variable.variable_key].trim();
          const existingVariable = globalVariables.find(
            (v) => v.name === variable.variable_key,
          );
          const variableType = variable.is_secret
            ? VARIABLE_CATEGORY.CREDENTIAL
            : VARIABLE_CATEGORY.GLOBAL;

          if (existingVariable) {
            return updateGlobalVariable({ id: existingVariable.id, value });
          } else {
            return createGlobalVariable({
              name: variable.variable_key,
              value,
              type: variableType,
              category: VARIABLE_CATEGORY.GLOBAL,
              default_fields: [],
            });
          }
        }),
      );

      // All succeeded — defer toast and value clear until after models refetch
      pendingSuccessTitleRef.current = `${selectedProvider.provider} Configuration Saved`;
      setIsFetchingAfterSave(true);
      clearValuesAfterFetchRef.current = true;
      invalidateProviderQueries();
    } catch (error: any) {
      setValidationFailed(true);
      setErrorData({
        title: "Error Saving Configuration",
        list: [
          error?.response?.data?.detail ||
            "An unexpected error occurred. Please try again.",
        ],
      });
    } finally {
      setIsSaving(false);
    }
  }, [
    selectedProvider,
    providerVariables,
    variableValues,
    globalVariables,
    createGlobalVariable,
    updateGlobalVariable,
    setSuccessData,
    setErrorData,
    invalidateProviderQueries,
  ]);

  // Activate providers that don't need API keys (e.g., Ollama)
  const handleActivateProvider = useCallback(async () => {
    if (!syncedSelectedProvider) return;

    // Get the first variable (usually the base URL for providers like Ollama)
    const firstVariable = providerVariables[0];
    const variableName =
      firstVariable?.variable_key ||
      PROVIDER_VARIABLE_MAPPING[syncedSelectedProvider.provider];

    if (!variableName) {
      setErrorData({
        title: "Invalid Provider",
        list: [
          `Provider "${syncedSelectedProvider.provider}" is not supported.`,
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
        });
      } else {
        await createGlobalVariable({
          name: variableName,
          value: placeholderValue,
          type: VARIABLE_CATEGORY.CREDENTIAL,
          category: VARIABLE_CATEGORY.GLOBAL,
          default_fields: [],
        });
      }

      setSuccessData({ title: `${syncedSelectedProvider.provider} Activated` });
      invalidateProviderQueries();
    } catch (error: any) {
      setErrorData({
        title: "Error Activating Provider",
        list: [
          error?.response?.data?.detail ||
            "An unexpected error occurred. Please try again.",
        ],
      });
    }
  }, [
    syncedSelectedProvider,
    providerVariables,
    globalVariables,
    createGlobalVariable,
    updateGlobalVariable,
    setSuccessData,
    setErrorData,
    invalidateProviderQueries,
  ]);

  // Disconnect / Deactivate provider
  const handleDisconnect = useCallback(async () => {
    if (!syncedSelectedProvider) return;

    const variableName =
      PROVIDER_VARIABLE_MAPPING[syncedSelectedProvider.provider];
    if (!variableName) return;

    const existingVariable = globalVariables.find(
      (v) => v.name === variableName,
    );
    if (!existingVariable) return;

    try {
      await deleteGlobalVariable({ id: existingVariable.id });

      setSuccessData({
        title: `${syncedSelectedProvider.provider} Disconnected`,
      });
      setIsFetchingAfterDisconnect(true);
      invalidateProviderQueries();
    } catch (error: any) {
      setErrorData({
        title: "Error Disconnecting Provider",
        list: [
          error?.response?.data?.detail ||
            "An unexpected error occurred. Please try again.",
        ],
      });
    }
  }, [
    syncedSelectedProvider,
    globalVariables,
    deleteGlobalVariable,
    setSuccessData,
    setErrorData,
    invalidateProviderQueries,
  ]);

  const pendingModelToggles = useRef<Record<string, boolean>>({});
  const fallbackModelData = useRef<EnabledModelsResponse | undefined>(
    undefined,
  );

  const flushModelToggles = useDebounce(() => {
    if (!syncedSelectedProvider?.provider) return;
    const providerName = syncedSelectedProvider.provider;

    const updates = Object.entries(pendingModelToggles.current).map(
      ([modelName, enabled]) => ({
        provider: providerName,
        model_id: modelName,
        enabled,
      }),
    );

    if (updates.length === 0) return;

    // Capture the fallback data
    const previousData = fallbackModelData.current;

    // Clear buffer
    pendingModelToggles.current = {};
    fallbackModelData.current = undefined;

    updateEnabledModels(
      { updates },
      {
        onError: (error: any) => {
          if (previousData) {
            queryClient.setQueryData(["useGetEnabledModels"], previousData);
          }
          const errorMessage =
            error?.response?.data?.detail ||
            error?.message ||
            "Failed to update model status";
          setErrorData({
            title: "Error updating model status",
            list: [errorMessage],
          });
        },
        onSettled: () => {
          queryClient.invalidateQueries({
            queryKey: ["useGetEnabledModels"],
          });
          queryClient.invalidateQueries({
            queryKey: ["useGetModelProviders"],
          });
        },
      },
    );
  }, 1000);

  const handleModelToggle = useCallback(
    (modelName: string, enabled: boolean) => {
      if (!syncedSelectedProvider?.provider) return;

      const providerName = syncedSelectedProvider.provider;

      if (Object.keys(pendingModelToggles.current).length === 0) {
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

      pendingModelToggles.current[modelName] = enabled;
      flushModelToggles();
    },
    [syncedSelectedProvider, queryClient, flushModelToggles],
  );

  return {
    variableValues,
    validationFailed,
    isSaving,
    isPending,
    isDeleting,
    validationState,
    validationError,
    providerVariables,
    syncedSelectedProvider,

    // Handlers
    handleVariableChange,
    handleSaveAllVariables,
    handleDisconnect,
    handleActivateProvider,
    validateCredentials,
    handleModelToggle,

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
