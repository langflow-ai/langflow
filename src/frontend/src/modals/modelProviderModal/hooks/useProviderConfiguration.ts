import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
    PROVIDER_VARIABLE_MAPPING,
    ProviderVariable,
    VARIABLE_CATEGORY,
} from "@/constants/providerConstants";
import {
    useGetGlobalVariables,
    usePatchGlobalVariables,
    usePostGlobalVariables,
} from "@/controllers/API/queries/variables";
import { useValidateProvider } from "@/controllers/API/queries/models/use-validate-provider";
import { useGetProviderVariables } from "@/controllers/API/queries/models/use-get-provider-variables";
import { useUpdateEnabledModels } from "@/controllers/API/queries/models/use-update-enabled-models";
import { EnabledModelsResponse } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
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
    validationState: ValidationState;
    validationError: string | null;
    providerVariables: ProviderVariable[];
    syncedSelectedProvider: Provider | null;

    // Handlers
    handleVariableChange: (key: string, value: string) => void;
    handleSaveAllVariables: () => Promise<void>;
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

    // Cache invalidation
    invalidateProviderQueries: () => void;
}

export const useProviderConfiguration = ({
    selectedProvider,
}: UseProviderConfigurationOptions): UseProviderConfigurationReturn => {
    const [variableValues, setVariableValues] = useState<Record<string, string>>({});
    const [syncedSelectedProvider, setSyncedSelectedProvider] = useState<Provider | null>(selectedProvider);
    const [validationFailed, setValidationFailed] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [validationState, setValidationState] = useState<ValidationState>("idle");
    const [validationError, setValidationError] = useState<string | null>(null);
    const validationTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const queryClient = useQueryClient();
    const setSuccessData = useAlertStore((state) => state.setSuccessData);
    const setErrorData = useAlertStore((state) => state.setErrorData);

    const { mutateAsync: createGlobalVariable, isPending: isCreating } =
        usePostGlobalVariables();
    const { mutateAsync: updateGlobalVariable, isPending: isUpdating } =
        usePatchGlobalVariables();
    const { data: globalVariables = [] } = useGetGlobalVariables();
    const { mutateAsync: validateProvider } = useValidateProvider();
    const { data: providerVariablesMapping = {} } = useGetProviderVariables();
    const { mutate: updateEnabledModels } = useUpdateEnabledModels({ retry: 0 });
    const { data: modelProviders = [] } = useGetModelProviders({});

    // Keep syncedSelectedProvider in sync with prop and reset state on provider change
    useEffect(() => {
        if (selectedProvider?.provider !== syncedSelectedProvider?.provider) {
            setVariableValues({});
            setValidationState("idle");
            setValidationError(null);
            setValidationFailed(false);
        }
        setSyncedSelectedProvider(selectedProvider);
    }, [selectedProvider]);

    // Sync selectedProvider with fresh data when model providers are refetched
    useEffect(() => {
        if (syncedSelectedProvider && modelProviders.length > 0) {
            const freshProvider = modelProviders.find(
                (p) => p.provider === syncedSelectedProvider.provider,
            );
            if (
                freshProvider &&
                (freshProvider.is_enabled !== syncedSelectedProvider.is_enabled ||
                    freshProvider.is_configured !== syncedSelectedProvider.is_configured)
            ) {
                setSyncedSelectedProvider({
                    ...syncedSelectedProvider,
                    is_enabled: freshProvider.is_enabled,
                    is_configured: freshProvider.is_configured,
                    models: freshProvider.models || syncedSelectedProvider.models,
                });
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
                    description: `Your ${providerName} API key`,
                    required: true,
                    is_secret: true,
                    is_list: false,
                    options: [],
                },
            ];
        }

        return [];
    }, [syncedSelectedProvider, providerVariablesMapping]);

    const isPending = isCreating || isUpdating || isSaving || validationState === "validating";

    // Invalidate all provider-related caches after successful create/update
    const invalidateProviderQueries = useCallback(() => {
        queryClient.invalidateQueries({ queryKey: ["useGetModelProviders"] });
        queryClient.invalidateQueries({ queryKey: ["useGetEnabledModels"] });
        queryClient.invalidateQueries({ queryKey: ["useGetGlobalVariables"] });
        queryClient.refetchQueries({ queryKey: ["flows"] });
    }, [queryClient]);

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

    // Check if all required variables are filled (either configured or have new input)
    const allRequiredFilled = useMemo(() => {
        return providerVariables
            .filter((v) => v.required)
            .every((v) => {
                const hasNewValue = variableValues[v.variable_key]?.trim();
                const isConfigured = globalVariables.some(
                    (gv) => gv.name === v.variable_key,
                );
                return hasNewValue || isConfigured;
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
                const existing = globalVariables.find((gv) => gv.name === v.variable_key);
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

    // Debounced validation when all required fields are filled
    useEffect(() => {
        // Clear any pending validation
        if (validationTimeoutRef.current) {
            clearTimeout(validationTimeoutRef.current);
        }

        // Only validate if we have new values AND all required are filled
        if (hasNewValuesToSave && allRequiredFilled && selectedProvider) {
            setValidationState("idle");
            validationTimeoutRef.current = setTimeout(() => {
                validateCredentials();
            }, 600);
        } else {
            setValidationState("idle");
            setValidationError(null);
        }

        return () => {
            if (validationTimeoutRef.current) {
                clearTimeout(validationTimeoutRef.current);
            }
        };
    }, [hasNewValuesToSave, allRequiredFilled, selectedProvider, variableValues]);

    // Can save only when validation passes
    const canSave = useMemo(() => {
        return hasNewValuesToSave && allRequiredFilled && validationState === "valid";
    }, [hasNewValuesToSave, allRequiredFilled, validationState]);

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

    // Save all variables in parallel
    const handleSaveAllVariables = useCallback(async () => {
        if (!selectedProvider) return;

        const variablesToSave = providerVariables.filter((v) =>
            variableValues[v.variable_key]?.trim(),
        );

        if (variablesToSave.length === 0) return;

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

            // All succeeded
            setSuccessData({
                title: `${selectedProvider.provider} Configuration Saved`,
            });
            invalidateProviderQueries();
            setVariableValues({});
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
                list: [`Provider "${syncedSelectedProvider.provider}" is not supported.`],
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

    const handleModelToggle = useCallback(
        (modelName: string, enabled: boolean) => {
            if (!syncedSelectedProvider?.provider) return;

            const providerName = syncedSelectedProvider.provider;

            const previousData = queryClient.getQueryData<EnabledModelsResponse>([
                "useGetEnabledModels",
            ]);

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

            updateEnabledModels(
                {
                    updates: [{ provider: providerName, model_id: modelName, enabled }],
                },
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
                        queryClient.invalidateQueries({ queryKey: ["useGetEnabledModels"] });
                        queryClient.invalidateQueries({ queryKey: ["useGetModelProviders"] });
                    },
                },
            );
        },
        [syncedSelectedProvider, queryClient, updateEnabledModels, setErrorData],
    );

    return {
        variableValues,
        validationFailed,
        isSaving,
        isPending,
        validationState,
        validationError,
        providerVariables,
        syncedSelectedProvider,

        // Handlers
        handleVariableChange,
        handleSaveAllVariables,
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

        // Cache invalidation
        invalidateProviderQueries,
    };
};
