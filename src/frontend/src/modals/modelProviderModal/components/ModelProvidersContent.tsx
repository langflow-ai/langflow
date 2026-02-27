import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
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
import ProviderList from "@/modals/modelProviderModal/components/ProviderList";
import { Provider } from "@/modals/modelProviderModal/components/types";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";
import DisconnectWarning from "./DisconnectWarning";
import ModelSelection from "./ModelSelection";

interface ModelProvidersContentProps {
  modelType: "llm" | "embeddings" | "all";
}

const ModelProvidersContent = ({ modelType }: ModelProvidersContentProps) => {
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null,
  );
  const [apiKey, setApiKey] = useState("");
  const [validationFailed, setValidationFailed] = useState(false);
  const [showReplaceWarning, setShowReplaceWarning] = useState(false);
  const [isEditingKey, setIsEditingKey] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Generate a masked preview of the API key based on provider
  const getMaskedKeyPreview = (providerName: string): string => {
    const keyConfig: Record<string, { prefix: string; totalLength: number }> = {
      OpenAI: { prefix: "sk-proj-", totalLength: 164 },
      Anthropic: { prefix: "sk-ant-", totalLength: 108 },
      "Google Generative AI": { prefix: "AIza", totalLength: 39 },
      "IBM watsonx": { prefix: "", totalLength: 44 },
    };
    const config = keyConfig[providerName] || {
      prefix: "",
      totalLength: 40,
    };
    const maskedLength = config.totalLength - config.prefix.length;
    return `${config.prefix}${"•".repeat(maskedLength)}`;
  };

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

  const invalidateProviderQueries = () => {
    queryClient.invalidateQueries({ queryKey: ["useGetModelProviders"] });
    queryClient.invalidateQueries({ queryKey: ["useGetEnabledModels"] });
    queryClient.invalidateQueries({ queryKey: ["useGetGlobalVariables"] });
  };

  const placeholderValue = "http://localhost:11434";

  useEffect(() => {
    setApiKey("");
    setValidationFailed(false);
    setShowReplaceWarning(false);
    setIsEditingKey(false);
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

  const handleProviderSelect = (provider: Provider) => {
    setSelectedProvider((prev) =>
      prev?.provider === provider.provider ? null : provider,
    );
  };

  const requiresApiKey = useMemo(() => {
    if (!selectedProvider) return true;
    return !NO_API_KEY_PROVIDERS.includes(selectedProvider.provider);
  }, [selectedProvider]);

  const handleActivateNoApiKeyProvider = () => {
    if (!selectedProvider) return;

    const variableName = PROVIDER_VARIABLE_MAPPING[selectedProvider.provider];

    if (!variableName) {
      setErrorData({
        title: "Invalid Provider",
        list: [`Provider "${selectedProvider.provider}" is not supported.`],
      });
      return;
    }

    const existingVariable = globalVariables.find(
      (v) => v.name === variableName,
    );

    const onSuccess = () => {
      invalidateProviderQueries();
      setSuccessData({ title: `${selectedProvider.provider} Activated` });
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
        <div className={cn("flex flex-col gap-1 relative p-4")}>
          {requiresApiKey ? (
            <>
              <div
                className={cn(
                  "flex flex-col gap-3 transition-all duration-300 ease-in-out relative",
                  showReplaceWarning
                    ? "opacity-0 pointer-events-none"
                    : "opacity-100",
                )}
              >
                <div className="flex flex-col gap-1">
                  <span className="text-sm font-semibold">
                    {selectedProvider?.provider || "Unknown Provider"}
                    {requiresApiKey && " API Key"}
                    {requiresApiKey && (
                      <span className="text-red-500 ml-1">*</span>
                    )}
                  </span>
                  <span className="text-sm text-muted-foreground">
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
                  </span>
                </div>
                <Input
                  ref={inputRef}
                  placeholder={"Enter API key"}
                  value={
                    selectedProvider?.is_enabled && !isEditingKey
                      ? getMaskedKeyPreview(selectedProvider.provider)
                      : apiKey
                  }
                  className="group"
                  type={
                    selectedProvider?.is_enabled && !isEditingKey
                      ? "text"
                      : "password"
                  }
                  onFocus={() => {
                    if (selectedProvider?.is_enabled) {
                      setIsEditingKey(true);
                    }
                  }}
                  onBlur={() => {
                    if (!apiKey) {
                      setIsEditingKey(false);
                    }
                  }}
                  onChange={(e) => {
                    setValidationFailed(false);
                    setApiKey(e.target.value);
                  }}
                  endIcon={
                    isPending
                      ? "LoaderCircle"
                      : validationFailed
                        ? "X"
                        : selectedProvider?.is_enabled && !isEditingKey
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
                <div className="flex gap-2 justify-end">
                  {selectedProvider?.is_enabled && (
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => {
                        handleDisconnect();
                      }}
                    >
                      Disconnect
                    </Button>
                  )}
                  <Button size="sm" onClick={handleConfigureProvider}>
                    <span>
                      {selectedProvider?.is_enabled ? "Replace" : "Validate"}{" "}
                      API Key
                    </span>
                  </Button>
                </div>
              </div>
              <DisconnectWarning
                show={showReplaceWarning}
                message="Disconnecting an API key will disable all of the provider's models being used in a flow."
                onCancel={() => setShowReplaceWarning(false)}
                onConfirm={handleConfirmDisconnect}
                isLoading={isDeleting}
                className="absolute inset-0 m-4"
              />
            </>
          ) : (
            <>
              <div
                className={cn(
                  "flex flex-col gap-3 transition-all duration-300 ease-in-out relative",
                  showReplaceWarning
                    ? "opacity-0 pointer-events-none"
                    : "opacity-100",
                )}
              >
                <div className="flex flex-col gap-1">
                  <span className="text-sm font-semibold">
                    {selectedProvider?.provider || "Unknown Provider"}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    Activate {selectedProvider?.provider} to enable these models
                  </span>
                </div>
                <Input
                  disabled
                  value={"No key required"}
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
                <div className="flex gap-2 justify-end">
                  {selectedProvider?.is_enabled && (
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={handleDisconnect}
                    >
                      Deactivate {selectedProvider?.provider}
                    </Button>
                  )}
                  {!selectedProvider?.is_enabled && (
                    <Button
                      size="sm"
                      onClick={handleActivateNoApiKeyProvider}
                      loading={isPending && !showReplaceWarning}
                    >
                      Activate {selectedProvider?.provider}
                    </Button>
                  )}
                </div>
              </div>
              <DisconnectWarning
                show={showReplaceWarning}
                message={`Deactivating ${selectedProvider?.provider} will disable all of the provider's models being used in a flow.`}
                onCancel={() => setShowReplaceWarning(false)}
                onConfirm={handleConfirmDisconnect}
                isLoading={isDeleting}
                className="absolute inset-0 m-4"
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
