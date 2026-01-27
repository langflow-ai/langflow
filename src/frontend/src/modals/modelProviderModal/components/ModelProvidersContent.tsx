import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  NO_API_KEY_PROVIDERS,
  PROVIDER_VARIABLE_MAPPING,
  VARIABLE_CATEGORY,
} from "@/constants/providerConstants";
import { useUpdateEnabledModels } from "@/controllers/API/queries/models/use-update-enabled-models";
import {
  useDeleteGlobalVariables,
  useGetGlobalVariables,
  usePatchGlobalVariables,
  usePostGlobalVariables,
} from "@/controllers/API/queries/variables";
import { useDebounce } from "@/hooks/use-debounce";
import ProviderList from "@/modals/modelProviderModal/components/ProviderList";
import { Provider } from "@/modals/modelProviderModal/components/types";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";
import DisconnectWarning from "./DisconnectWarning";
import ModelSelection from "./ModelSelection";

// API key placeholder examples by provider
const API_KEY_PLACEHOLDERS: Record<string, string> = {
  OpenAI: "sk-****************************************************************",
  Anthropic:
    "sk-ant-****************************************************************",
  "Google Generative AI": "AIza***********************************",
  "IBM WatsonX": "********************************************",
};

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
  const [apiKey, setApiKey] = useState("");
  const [validationFailed, setValidationFailed] = useState(false);
  const [showReplaceWarning, setShowReplaceWarning] = useState(false);
  const [isInputFocused, setIsInputFocused] = useState(false);
  // Track if API key change came from user typing (vs programmatic reset)
  // Used to prevent auto-save from triggering when we clear the input after success
  const isUserInputRef = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { mutate: createGlobalVariable, isPending: isCreating } =
    usePostGlobalVariables();
  const { mutate: updateGlobalVariable, isPending: isUpdating } =
    usePatchGlobalVariables();
  const { data: globalVariables = [] } = useGetGlobalVariables();
  const { mutate: updateEnabledModels } = useUpdateEnabledModels();
  const { mutate: deleteGlobalVariable, isPending: isDeleting } =
    useDeleteGlobalVariables();

  const isPending = isCreating || isUpdating || isDeleting;

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
    setApiKey("");
    setValidationFailed(false);
    setShowReplaceWarning(false);
  }, [selectedProvider?.provider]);

  const handleApiKey = () => {
    setShowReplaceWarning(true);
  };

  const handleDisconnect = () => {
    setShowReplaceWarning(true);
  };

  const handleConfirmDisconnect = () => {
    if (!selectedProvider) return;

    const variableName = PROVIDER_VARIABLE_MAPPING[selectedProvider.provider];
    if (!variableName) return;

    const existingVariable = globalVariables.find(
      (v) => v.name === variableName,
    );
    if (!existingVariable) return;

    deleteGlobalVariable(
      { id: existingVariable.id },
      {
        onSuccess: () => {
          setSuccessData({
            title: `${selectedProvider.provider} Disconnected`,
          });
          invalidateProviderQueries();
          setShowReplaceWarning(false);
          setSelectedProvider((prev) =>
            prev ? { ...prev, is_enabled: false } : null,
          );
        },
        onError: (error: any) => {
          setErrorData({
            title: "Error Disconnecting Provider",
            list: [
              error?.response?.data?.detail ||
                "An unexpected error occurred. Please try again.",
            ],
          });
        },
      },
    );
  };

  // Auto-save API key after user stops typing for 800ms
  // The debounce prevents API calls on every keystroke
  const debouncedConfigureProvider = useDebounce(() => {
    if (apiKey.trim() && selectedProvider && isUserInputRef.current) {
      handleConfigureProvider();
      isUserInputRef.current = false;
    }
  }, 800);

  // Trigger debounced save when apiKey changes from user input
  useEffect(() => {
    if (
      apiKey.trim() &&
      isUserInputRef.current &&
      !selectedProvider?.is_enabled
    ) {
      debouncedConfigureProvider();
    }
  }, [apiKey, debouncedConfigureProvider, selectedProvider?.is_enabled]);

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

  // Some providers (e.g., Ollama) don't require API keys - they just need activation
  const requiresApiKey = useMemo(() => {
    if (!selectedProvider) return true;
    return !NO_API_KEY_PROVIDERS.includes(selectedProvider.provider);
  }, [selectedProvider]);

  // Activate providers that don't need API keys (e.g., Ollama)
  // Creates/updates a global variable with a placeholder URL to mark provider as enabled
  const handleActivateNoApiKeyProvider = () => {
    if (!selectedProvider) return;

    // Map provider name to its corresponding global variable name
    const variableName = PROVIDER_VARIABLE_MAPPING[selectedProvider.provider];
    if (!variableName) {
      setErrorData({
        title: "Invalid Provider",
        list: [`Provider "${selectedProvider.provider}" is not supported.`],
      });
      return;
    }

    // Check if provider was previously configured (variable exists)
    const existingVariable = globalVariables.find(
      (v) => v.name === variableName,
    );

    // Ollama default endpoint - used as placeholder to mark provider as active
    const placeholderValue = "http://localhost:11434";

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

  // Save API key for providers that require authentication (e.g., OpenAI, Anthropic)
  const handleConfigureProvider = () => {
    if (!selectedProvider || !apiKey.trim()) return;

    const variableName = PROVIDER_VARIABLE_MAPPING[selectedProvider.provider];
    if (!variableName) {
      setErrorData({
        title: "Invalid Provider",
        list: [`Provider "${selectedProvider.provider}" is not supported.`],
      });
      return;
    }

    // Check if provider was previously configured - determines update vs create
    const existingVariable = globalVariables.find(
      (v) => v.name === variableName,
    );

    const onSuccess = () => {
      setSuccessData({ title: `${selectedProvider.provider} API Key Saved` });
      invalidateProviderQueries();
      setApiKey("");
      setIsInputFocused(false);
      inputRef.current?.blur();
      setSelectedProvider((prev) =>
        prev ? { ...prev, is_enabled: true } : null,
      );
    };

    const onError = (error: any) => {
      setValidationFailed(true);
      setErrorData({
        title: existingVariable
          ? "Error Updating API Key"
          : "Error Saving API Key",
        list: [
          error?.response?.data?.detail ||
            "An unexpected error occurred. Please try again.",
        ],
      });
    };

    if (existingVariable) {
      updateGlobalVariable(
        { id: existingVariable.id, value: apiKey },
        { onSuccess, onError },
      );
    } else {
      createGlobalVariable(
        {
          name: variableName,
          value: apiKey,
          type: VARIABLE_CATEGORY.CREDENTIAL,
          category: VARIABLE_CATEGORY.GLOBAL,
          default_fields: [],
        },
        { onSuccess, onError },
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
          "flex flex-col gap-1 transition-all duration-300 ease-in-out overflow-hidden",
          selectedProvider
            ? "w-2/3 opacity-100 translate-x-0"
            : "w-0 opacity-0 translate-x-full",
        )}
      >
        <div className="flex flex-col gap-1 p-4">
          <div className="flex flex-row gap-1 min-w-[300px]">
            <span className="text-[13px] font-semibold mr-auto">
              {selectedProvider?.provider || "Unknown Provider"}
              {requiresApiKey && " API Key"}
              {requiresApiKey && <span className="text-red-500 ml-1">*</span>}
            </span>
          </div>
          <span className="text-[13px] text-muted-foreground pt-1 pb-2">
            {requiresApiKey ? (
              <>
                Add your{" "}
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
                  {selectedProvider?.provider} API key
                </span>{" "}
                to enable these models
              </>
            ) : (
              <>Activate {selectedProvider?.provider} to enable these models</>
            )}
          </span>
          {requiresApiKey ? (
            <>
              <Input
                ref={inputRef}
                placeholder={
                  isInputFocused || !selectedProvider?.is_enabled
                    ? "Enter API key"
                    : API_KEY_PLACEHOLDERS[selectedProvider?.provider ?? ""] ||
                      "Enter API key"
                }
                placeholderClassName={cn(
                  "text-primary group-focus-within:text-placeholder-foreground whitespace-nowrap overflow-hidden right-10",
                  !selectedProvider?.is_enabled &&
                    "text-placeholder-foreground",
                )}
                value={apiKey}
                className="group"
                type="password"
                onFocus={() => setIsInputFocused(true)}
                onBlur={() => setIsInputFocused(false)}
                onChange={(e) => {
                  isUserInputRef.current = true;
                  setValidationFailed(false);
                  setApiKey(e.target.value);
                }}
                // Show loading spinner while saving, X on error, checkmark when configured
                endIcon={
                  isPending
                    ? "LoaderCircle"
                    : validationFailed
                      ? "X"
                      : selectedProvider?.is_enabled
                        ? "Check"
                        : undefined
                }
                endIconClassName={cn(
                  isPending && "animate-spin text-muted-foreground top-2.5",
                  validationFailed && "text-red-500",
                  !isPending &&
                    !validationFailed &&
                    selectedProvider?.is_enabled &&
                    "text-green-500",
                )}
              />
              {selectedProvider?.is_enabled && (
                <div
                  className={cn(
                    "justify-end flex gap-2 mt-2 transition-all duration-300 ease-in-out",
                    showReplaceWarning
                      ? "opacity-0 max-h-0 overflow-hidden"
                      : "opacity-100 max-h-20",
                  )}
                >
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => {
                      handleDisconnect();
                    }}
                  >
                    Disconnect
                  </Button>

                  <Button size="sm" onClick={handleConfigureProvider}>
                    <span>Replace API Key</span>
                  </Button>
                </div>
              )}
              <DisconnectWarning
                show={showReplaceWarning}
                message="Disconnecting an API key will disable all of the provider's models being used in a flow."
                onCancel={() => setShowReplaceWarning(false)}
                onConfirm={handleConfirmDisconnect}
                isLoading={isDeleting}
              />
            </>
          ) : (
            <>
              <div
                className={cn(
                  "transition-all duration-300 ease-in-out",
                  showReplaceWarning
                    ? "opacity-0 max-h-0 overflow-hidden"
                    : "opacity-100 max-h-20",
                )}
              >
                <Button
                  onClick={
                    selectedProvider?.is_enabled
                      ? handleDisconnect
                      : handleActivateNoApiKeyProvider
                  }
                  loading={isPending && !showReplaceWarning}
                  variant={
                    selectedProvider?.is_enabled ? "destructive" : "default"
                  }
                  className={cn(
                    "w-full",
                    selectedProvider?.is_enabled && "text-primary",
                  )}
                >
                  {selectedProvider?.is_enabled
                    ? `Deactivate ${selectedProvider?.provider}`
                    : `Activate ${selectedProvider?.provider}`}
                </Button>
              </div>
              <DisconnectWarning
                show={showReplaceWarning}
                message={`Deactivating ${selectedProvider?.provider} will disable all of the provider's models being used in a flow.`}
                onCancel={() => setShowReplaceWarning(false)}
                onConfirm={handleConfirmDisconnect}
                isLoading={isDeleting}
              />
            </>
          )}
        </div>

        <div className="overflow-x-hidden">
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
    </div>
  );
};

export default ModelProvidersContent;
