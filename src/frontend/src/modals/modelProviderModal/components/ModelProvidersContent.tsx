import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  NO_API_KEY_PROVIDERS,
  PROVIDER_VARIABLE_MAPPING,
  ProviderVariable,
  VARIABLE_CATEGORY,
} from "@/constants/providerConstants";
import { useGetProviderVariables } from "@/controllers/API/queries/models/use-get-provider-variables";
import { useUpdateEnabledModels } from "@/controllers/API/queries/models/use-update-enabled-models";
import {
  useGetGlobalVariables,
  usePatchGlobalVariables,
  usePostGlobalVariables,
} from "@/controllers/API/queries/variables";
import ProviderList from "@/modals/modelProviderModal/components/ProviderList";
import { Provider } from "@/modals/modelProviderModal/components/types";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";
import ModelSelection from "./ModelSelection";
import ForwardedIconComponent from "@/components/common/genericIconComponent";

// Masked value shown for configured secret fields
const MASKED_VALUE = "••••••••";

interface ModelProvidersContentProps {
  modelType: "llm" | "embeddings" | "all";
  onClose?: () => void;
}

const ModelProvidersContent = ({
  modelType,
  onClose,
}: ModelProvidersContentProps) => {
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null,
  );
  // State for multiple variable values, keyed by variable_key
  const [variableValues, setVariableValues] = useState<Record<string, string>>(
    {},
  );
  const [validationFailed, setValidationFailed] = useState(false);
  // Track if batch save is in progress
  const [isSaving, setIsSaving] = useState(false);

  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { mutate: createGlobalVariable, isPending: isCreating } =
    usePostGlobalVariables();
  const { mutate: updateGlobalVariable, isPending: isUpdating } =
    usePatchGlobalVariables();
  const { data: globalVariables = [] } = useGetGlobalVariables();
  const { mutate: updateEnabledModels } = useUpdateEnabledModels();
  const { data: providerVariablesMapping = {} } = useGetProviderVariables();

  const isPending = isCreating || isUpdating || isSaving;

  // Get variables for the selected provider from API or fallback to static mapping
  const providerVariables = useMemo((): ProviderVariable[] => {
    if (!selectedProvider) return [];

    // Try to get from API data first
    const apiVariables = providerVariablesMapping[selectedProvider.provider];
    if (apiVariables && apiVariables.length > 0) {
      return apiVariables;
    }

    // Fallback to static mapping for backward compatibility
    const staticVariableKey =
      PROVIDER_VARIABLE_MAPPING[selectedProvider.provider];
    if (staticVariableKey) {
      return [
        {
          variable_name: "API Key",
          variable_key: staticVariableKey,
          description: `Your ${selectedProvider.provider} API key`,
          required: true,
          is_secret: true,
          is_list: false,
          options: [],
        },
      ];
    }

    return [];
  }, [selectedProvider, providerVariablesMapping]);

  // Invalidate all provider-related caches after successful create/update
  // This ensures the UI reflects the latest state across all components
  const invalidateProviderQueries = () => {
    queryClient.invalidateQueries({ queryKey: ["useGetModelProviders"] });
    queryClient.invalidateQueries({ queryKey: ["useGetEnabledModels"] });
    queryClient.invalidateQueries({ queryKey: ["useGetGlobalVariables"] });
    queryClient.refetchQueries({ queryKey: ["flows"] });
  };

  // Reset form when provider changes
  useEffect(() => {
    setVariableValues({});
    setValidationFailed(false);
    setIsSaving(false);
  }, [selectedProvider?.provider]);

  // Helper to get configured value for a variable from globalVariables
  const getConfiguredValue = (variableKey: string): string | null => {
    const variable = globalVariables.find((v) => v.name === variableKey);
    // For credentials, value is redacted (null), so we return a marker
    if (variable) {
      return variable.value || MASKED_VALUE;
    }
    return null;
  };

  // Helper to check if a variable is already configured
  const isVariableConfigured = (variableKey: string): boolean => {
    return globalVariables.some((v) => v.name === variableKey);
  };

  // Check if all required variables are filled (either configured or have new input)
  const allRequiredFilled = useMemo(() => {
    return providerVariables
      .filter((v) => v.required)
      .every((v) => {
        const hasNewValue = variableValues[v.variable_key]?.trim();
        const isConfigured = isVariableConfigured(v.variable_key);
        return hasNewValue || isConfigured;
      });
  }, [providerVariables, variableValues, globalVariables]);

  // Check if there are any new values to save
  const hasNewValuesToSave = useMemo(() => {
    return providerVariables.some((v) =>
      variableValues[v.variable_key]?.trim(),
    );
  }, [providerVariables, variableValues]);

  // Update enabled models when toggled
  const handleModelToggle = (modelName: string, enabled: boolean) => {
    if (!selectedProvider?.provider) return;

    updateEnabledModels(
      {
        updates: [
          {
            provider: selectedProvider.provider,
            model_id: modelName,
            enabled,
          },
        ],
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ["useGetEnabledModels"] });
        },
      },
    );
  };

  // Toggle provider selection - clicking same provider deselects it
  const handleProviderSelect = (provider: Provider) => {
    setSelectedProvider((prev) =>
      prev?.provider === provider.provider ? null : provider,
    );
  };

  // Check if provider requires any configuration (secrets or other required variables)
  const requiresConfiguration = useMemo(() => {
    if (!selectedProvider) return true;
    // Check if provider has any required variables (secret or not)
    const hasRequiredVariables = providerVariables.some((v) => v.required);
    return (
      hasRequiredVariables &&
      !NO_API_KEY_PROVIDERS.includes(selectedProvider.provider)
    );
  }, [selectedProvider, providerVariables]);

  // Activate providers that don't need API keys (e.g., Ollama)
  // Creates/updates a global variable with a placeholder URL to mark provider as enabled
  const handleActivateNoApiKeyProvider = () => {
    if (!selectedProvider) return;

    // Get the first variable (usually the base URL for providers like Ollama)
    const firstVariable = providerVariables[0];
    if (!firstVariable) {
      // Fallback to static mapping
      const variableName = PROVIDER_VARIABLE_MAPPING[selectedProvider.provider];
      if (!variableName) {
        setErrorData({
          title: "Invalid Provider",
          list: [`Provider "${selectedProvider.provider}" is not supported.`],
        });
        return;
      }
    }

    const variableName =
      firstVariable?.variable_key ||
      PROVIDER_VARIABLE_MAPPING[selectedProvider.provider];

    // Check if provider was previously configured (variable exists)
    const existingVariable = globalVariables.find(
      (v) => v.name === variableName,
    );

    // Ollama default endpoint - used as placeholder to mark provider as active
    const placeholderValue =
      firstVariable?.options?.[0] || "http://localhost:11434";

    const onSuccess = () => {
      setSuccessData({ title: `${selectedProvider.provider} Activated` });
      invalidateProviderQueries();
      setSelectedProvider((prev) =>
        prev ? { ...prev, is_enabled: true } : null,
      );
    };

    const onError = (error: any) => {
      setErrorData({
        title: "Error Activating Provider",
        list: [
          error?.response?.data?.detail ||
            "An unexpected error occurred. Please try again.",
        ],
      });
    };

    // Update existing variable or create new one
    if (existingVariable) {
      updateGlobalVariable(
        { id: existingVariable.id, value: placeholderValue },
        { onSuccess, onError },
      );
    } else {
      createGlobalVariable(
        {
          name: variableName,
          value: placeholderValue,
          type: VARIABLE_CATEGORY.CREDENTIAL,
          category: VARIABLE_CATEGORY.GLOBAL,
          default_fields: [],
        },
        { onSuccess, onError },
      );
    }
  };

  // Save all variables with new values for the selected provider (batch save)
  const handleSaveAllVariables = async () => {
    if (!selectedProvider) return;

    // Get all variables that have new values to save
    const variablesToSave = providerVariables.filter((v) =>
      variableValues[v.variable_key]?.trim(),
    );

    if (variablesToSave.length === 0) return;

    setIsSaving(true);
    setValidationFailed(false);

    let successCount = 0;
    let errorOccurred = false;

    // Save each variable sequentially
    for (const variable of variablesToSave) {
      const value = variableValues[variable.variable_key].trim();
      const existingVariable = globalVariables.find(
        (v) => v.name === variable.variable_key,
      );
      const variableType = variable.is_secret
        ? VARIABLE_CATEGORY.CREDENTIAL
        : VARIABLE_CATEGORY.GLOBAL;

      try {
        await new Promise<void>((resolve, reject) => {
          const onSuccess = () => {
            successCount++;
            resolve();
          };
          const onError = (error: any) => {
            reject(error);
          };

          if (existingVariable) {
            updateGlobalVariable(
              { id: existingVariable.id, value },
              { onSuccess, onError },
            );
          } else {
            createGlobalVariable(
              {
                name: variable.variable_key,
                value,
                type: variableType,
                category: VARIABLE_CATEGORY.GLOBAL,
                default_fields: [],
              },
              { onSuccess, onError },
            );
          }
        });
      } catch (error: any) {
        errorOccurred = true;
        setValidationFailed(true);
        setErrorData({
          title: `Error Saving ${variable.variable_name}`,
          list: [
            error?.response?.data?.detail ||
              "An unexpected error occurred. Please try again.",
          ],
        });
        break; // Stop on first error
      }
    }

    setIsSaving(false);

    if (!errorOccurred && successCount > 0) {
      setSuccessData({
        title: `${selectedProvider.provider} Configuration Saved`,
      });
      invalidateProviderQueries();
      // Clear the input values (configured values will show from globalVariables)
      setVariableValues({});
      // Mark provider as enabled
      setSelectedProvider((prev) =>
        prev ? { ...prev, is_enabled: true } : null,
      );
    }
  };

  // Note: refreshAllModelInputs is now called in ModelProviderModal's handleClose
  // to ensure reliable execution when the modal closes

  return (
    <div className="flex flex-row w-full h-full overflow-hidden">
      <div
        className={cn(
          "flex p-2 flex-col transition-all duration-300 ease-in-out",
          selectedProvider ? "w-1/3 border-r" : "w-full",
        )}
      >
        <ProviderList
          modelType={modelType}
          onProviderSelect={handleProviderSelect}
          selectedProviderName={selectedProvider?.provider ?? null}
        />
      </div>

      <div
        className={cn(
          "flex flex-col gap-1 transition-all duration-300 ease-in-out overflow-y-auto",
          selectedProvider
            ? "w-2/3 opacity-100 translate-x-0"
            : "w-0 opacity-0 translate-x-full",
        )}
      >
        <div className="flex flex-col gap-1 p-4">
          <div className="flex flex-row gap-1 min-w-[300px]">
            <span className="text-[13px] font-semibold mr-auto">
              {selectedProvider?.provider || "Unknown Provider"}
              {requiresConfiguration && " Configuration"}
            </span>
          </div>
          <span className="text-[13px] text-muted-foreground pt-1 pb-2">
            {requiresConfiguration ? (
              <>
                Configure your{" "}
                <span
                  className="underline cursor-pointer hover:text-primary"
                  onClick={() => {
                    if (selectedProvider?.api_docs_url) {
                      window.open(
                        selectedProvider.api_docs_url,
                        "_blank",
                        "noopener,noreferrer",
                      );
                    }
                  }}
                >
                  {selectedProvider?.provider} credentials
                </span>{" "}
                to enable these models
              </>
            ) : (
              <>Activate {selectedProvider?.provider} to enable these models</>
            )}
          </span>
          {requiresConfiguration ? (
            <div className="flex flex-col gap-3">
              {providerVariables.map((variable) => {
                const isConfigured = isVariableConfigured(
                  variable.variable_key,
                );
                const hasNewValue =
                  variableValues[variable.variable_key]?.trim();

                return (
                  <div
                    key={variable.variable_key}
                    className="flex flex-col gap-1"
                  >
                    <label className="text-[12px] font-medium text-muted-foreground">
                      {variable.variable_name}
                      {variable.required && (
                        <span className="text-red-500 ml-1">*</span>
                      )}
                    </label>
                    {variable.description && (
                      <span className="text-[11px] text-muted-foreground/70 mb-1">
                        {variable.description}
                      </span>
                    )}
                    {variable.options && variable.options.length > 0 ? (
                      // Render dropdown for variables with predefined options
                      <div className="relative">
                        <Select
                          value={
                            variableValues[variable.variable_key] ||
                            (isConfigured
                              ? getConfiguredValue(variable.variable_key) || ""
                              : "")
                          }
                          onValueChange={(value) => {
                            setValidationFailed(false);
                            setVariableValues((prev) => ({
                              ...prev,
                              [variable.variable_key]: value,
                            }));
                          }}
                        >
                          <SelectTrigger
                            className={cn(
                              "w-full",
                              isConfigured && !hasNewValue && "pr-8",
                            )}
                          >
                            <SelectValue
                              placeholder={`Select ${variable.variable_name}`}
                            />
                          </SelectTrigger>
                          <SelectContent>
                            {variable.options.map((option) => (
                              <SelectItem key={option} value={option}>
                                {option}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {isConfigured && !hasNewValue && (
                          <span className="absolute right-2 top-1/2 -translate-y-1/2 text-green-500 pointer-events-none">
                            <ForwardedIconComponent
                              name="check"
                              className="h-4 w-4"
                            />
                          </span>
                        )}
                      </div>
                    ) : (
                      // Render input for text/secret variables
                      <Input
                        placeholder={
                          isConfigured && !hasNewValue
                            ? variable.is_secret
                              ? MASKED_VALUE
                              : `Add ${variable.variable_name.toLowerCase()}`
                            : `Add ${variable.variable_name.toLowerCase()}`
                        }
                        defaultValue={
                          isConfigured
                            ? (variable.is_secret
                                ? MASKED_VALUE
                                : getConfiguredValue(variable.variable_key)) ||
                              ""
                            : ""
                        }
                        value={variableValues[variable.variable_key] || ""}
                        type={
                          variable.is_secret && hasNewValue
                            ? "password"
                            : "text"
                        }
                        onChange={(e) => {
                          setValidationFailed(false);
                          // Clear masked value on focus/type for secrets
                          const newValue =
                            e.target.value === MASKED_VALUE
                              ? ""
                              : e.target.value;
                          setVariableValues((prev) => ({
                            ...prev,
                            [variable.variable_key]: newValue,
                          }));
                        }}
                        onFocus={() => {
                          // Clear masked value when user focuses on a configured secret field
                          if (
                            isConfigured &&
                            variable.is_secret &&
                            !hasNewValue
                          ) {
                            setVariableValues((prev) => ({
                              ...prev,
                              [variable.variable_key]: "",
                            }));
                          }
                        }}
                        endIcon={
                          isConfigured && !hasNewValue ? "Check" : undefined
                        }
                        endIconClassName={cn(
                          isConfigured && !hasNewValue && "text-green-500",
                        )}
                      />
                    )}
                  </div>
                );
              })}
              {/* Save button - only enabled when all required are filled and there are new values */}
              <Button
                onClick={handleSaveAllVariables}
                loading={isSaving}
                disabled={!allRequiredFilled || !hasNewValuesToSave || isSaving}
                className="mt-2"
              >
                {isSaving
                  ? "Saving..."
                  : validationFailed
                    ? "Retry Save"
                    : "Save Configuration"}
              </Button>
            </div>
          ) : (
            <Button
              onClick={handleActivateNoApiKeyProvider}
              loading={isPending}
              disabled={selectedProvider?.is_enabled}
            >
              {selectedProvider?.is_enabled
                ? `${selectedProvider?.provider} Activated`
                : `Activate ${selectedProvider?.provider}`}
            </Button>
          )}
        </div>

        <div className="flex flex-col px-4 pb-4 gap-3 transition-all duration-300 ease-in-out">
          <ModelSelection
            modelType={modelType}
            availableModels={selectedProvider?.models || []}
            onModelToggle={handleModelToggle}
            providerName={selectedProvider?.provider}
            isEnabledModel={selectedProvider?.is_enabled}
          />
        </div>
      </div>
    </div>
  );
};

export default ModelProvidersContent;
