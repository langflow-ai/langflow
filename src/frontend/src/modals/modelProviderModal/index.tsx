import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader } from "@/components/ui/dialog";
import {
  PROVIDER_VARIABLE_MAPPING,
  VARIABLE_CATEGORY,
} from "@/constants/providerConstants";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { usePostGlobalVariables } from "@/controllers/API/queries/variables";
import { useProviderActions } from "@/hooks/use-provider-actions";
import ProviderList from "@/modals/modelProviderModal/components/ProviderList";
import { Model, Provider } from "@/modals/modelProviderModal/components/types";
import useAlertStore from "@/stores/alertStore";

import { cn } from "@/utils/utils";
import ModelProviderActive from "./components/ModelProviderActive";
import ModelProviderEdit from "./components/ModelProviderEdit";
import ModelProviderSelection from "./components/ModelProviderSelection";

interface ModelProviderModalProps {
  open: boolean;
  onClose: () => void;
  onModelsUpdated?: () => void;
}

const ModelProviderModal = ({
  open,
  onClose,
  onModelsUpdated,
}: ModelProviderModalProps) => {
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null,
  );
  const { data: enabledModelsData } = useGetEnabledModels();
  const { handleBatchToggleModels } = useProviderActions();
  // Track pending model toggle changes locally (modelName -> enabled)
  const [pendingModelChanges, setPendingModelChanges] = useState<
    Record<string, boolean>
  >({});
  const [isEditing, setIsEditing] = useState(true);
  // Track if any updates were made (Configure or Update button pressed)
  const [hasUpdated, setHasUpdated] = useState(false);

  // Form state for provider configuration
  const [authName, setAuthName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiBase, setApiBase] = useState("");

  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutate: createGlobalVariable, isPending } = usePostGlobalVariables();

  // Reset form and pending changes when provider changes
  useEffect(() => {
    setAuthName("");
    setApiKey("");
    setApiBase("");
    setPendingModelChanges({});
  }, [selectedProvider?.provider]);

  // Separate models into LLM and Embedding categories
  const { llmModels, embeddingModels } = useMemo(() => {
    if (!selectedProvider?.models) {
      return { llmModels: [], embeddingModels: [] };
    }
    const llm: Model[] = [];
    const embedding: Model[] = [];
    selectedProvider.models.forEach((model) => {
      const modelType = model.metadata?.model_type || "llm";
      if (modelType === "embeddings") {
        embedding.push(model);
      } else {
        llm.push(model);
      }
    });
    return { llmModels: llm, embeddingModels: embedding };
  }, [selectedProvider?.models]);

  // Get the server-side enabled state for a model
  const getServerModelEnabled = (modelName: string): boolean => {
    if (!selectedProvider) return false;
    const providerModels =
      enabledModelsData?.enabled_models?.[selectedProvider.provider];
    if (providerModels === undefined) return false;
    const isEnabled = providerModels[modelName];
    // If no explicit value, check if model has default enabled in metadata
    if (isEnabled === undefined) {
      const model = selectedProvider.models?.find(
        (m) => m.model_name === modelName,
      );
      return model?.metadata?.default === true;
    }
    return isEnabled === true;
  };

  // Get enabled state for a model (includes pending changes)
  const isModelEnabled = (modelName: string): boolean => {
    // If there's a pending change, use that
    if (modelName in pendingModelChanges) {
      return pendingModelChanges[modelName];
    }
    return getServerModelEnabled(modelName);
  };

  // Store toggle changes locally without applying immediately
  const handleModelToggle = (modelName: string, enabled: boolean) => {
    if (!selectedProvider) return;
    const serverEnabled = getServerModelEnabled(modelName);
    // If the new value matches server state, remove from pending
    if (enabled === serverEnabled) {
      setPendingModelChanges((prev) => {
        const next = { ...prev };
        delete next[modelName];
        return next;
      });
    } else {
      setPendingModelChanges((prev) => ({
        ...prev,
        [modelName]: enabled,
      }));
    }
  };

  // Apply all pending model changes
  const applyPendingModelChanges = () => {
    if (!selectedProvider || Object.keys(pendingModelChanges).length === 0)
      return;

    const updates = Object.entries(pendingModelChanges).map(
      ([modelName, enabled]) => ({
        provider: selectedProvider.provider,
        model_id: modelName,
        enabled,
      }),
    );

    handleBatchToggleModels(updates, () => setHasUpdated(true));
    setPendingModelChanges({});
  };

  // Check if there are pending changes
  const hasPendingChanges = Object.keys(pendingModelChanges).length > 0;

  const handleProviderSelect = (provider: Provider) => {
    setSelectedProvider((prev) =>
      prev?.provider === provider.provider ? null : provider,
    );
    setIsEditing(!provider.is_enabled);
  };

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

    createGlobalVariable(
      {
        name: variableName,
        value: apiKey,
        type: VARIABLE_CATEGORY.CREDENTIAL,
        category: VARIABLE_CATEGORY.GLOBAL,
        default_fields: [],
      },
      {
        onSuccess: () => {
          setSuccessData({
            title: `${selectedProvider.provider} API Key Saved`,
          });
          // Invalidate caches to refresh the UI
          queryClient.invalidateQueries({
            queryKey: ["useGetModelProviders"],
          });
          queryClient.invalidateQueries({
            queryKey: ["useGetEnabledModels"],
          });
          queryClient.invalidateQueries({
            queryKey: ["useGetGlobalVariables"],
          });
          queryClient.invalidateQueries({
            queryKey: ["useGetDefaultModel"],
          });
          // Force refresh flow data to update node templates with new model options
          queryClient.refetchQueries({
            queryKey: ["flows"],
          });
          // Mark that updates were made (refresh will happen on close)
          setHasUpdated(true);
          // Reset form and switch to model selection view
          setApiKey("");
          setAuthName("");
          setApiBase("");
          // Update local state to reflect enabled status
          setSelectedProvider((prev) =>
            prev ? { ...prev, is_enabled: true } : null,
          );
          setIsEditing(false);
        },
        onError: (error: any) => {
          setErrorData({
            title: "Error Saving API Key",
            list: [
              error?.response?.data?.detail ||
                "An unexpected error occurred while saving the API key. Please try again.",
            ],
          });
        },
      },
    );
  };

  // Get names of active models for the editing panel badges
  const activeLLMNames = useMemo(() => {
    return llmModels
      .filter((m) => isModelEnabled(m.model_name))
      .map((m) => m.model_name);
  }, [llmModels, enabledModelsData, selectedProvider, pendingModelChanges]);

  const activeEmbeddingNames = useMemo(() => {
    return embeddingModels
      .filter((m) => isModelEnabled(m.model_name))
      .map((m) => m.model_name);
  }, [
    embeddingModels,
    enabledModelsData,
    selectedProvider,
    pendingModelChanges,
  ]);

  // Handle modal close - refresh if updates were made
  const handleClose = () => {
    if (hasUpdated) {
      onModelsUpdated?.();
    }
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && handleClose()}>
      <DialogContent className="flex flex-col overflow-hidden rounded-xl p-0 max-w-[950px] gap-0">
        {/* model provider header */}
        <DialogHeader className="flex w-full border-b px-4 py-3">
          <div className="flex justify-start items-center gap-3">
            <ForwardedIconComponent name="Brain" className="w-5 h-5" />
            <div className="text-[13px] font-semibold ">Model providers</div>
          </div>
        </DialogHeader>

        {/* model provider list */}
        <div className="flex flex-row w-full overflow-hidden">
          <div
            className={cn(
              "flex border-r p-2 flex-col transition-all duration-300 ease-in-out",
              selectedProvider ? "w-1/2" : "w-full",
            )}
          >
            <ProviderList
              onProviderSelect={handleProviderSelect}
              selectedProviderName={selectedProvider?.provider ?? null}
            />
          </div>

          {/* Model Provider sub header */}
          <div
            className={cn(
              "flex flex-col gap-1 transition-all duration-300 ease-in-out overflow-hidden",
              selectedProvider
                ? "w-1/2 opacity-100 translate-x-0"
                : "w-0 opacity-0 translate-x-full",
            )}
          >
            <div className="flex flex-row items-center gap-1 border-b p-4 min-w-[300px]">
              <ForwardedIconComponent
                name={selectedProvider?.icon || "Bot"}
                className={cn(
                  "w-5 h-5 flex-shrink-0 transition-all",
                  !selectedProvider?.is_enabled && "grayscale opacity-50",
                )}
              />
              <span className="text-[13px] font-semibold pl-2 mr-auto">
                {selectedProvider?.provider || "Unknown Provider"}
              </span>
              {selectedProvider?.is_enabled && (
                <Button
                  variant="menu"
                  size="icon"
                  unstyled
                  onClick={() => setIsEditing(!isEditing)}
                  className=""
                >
                  <ForwardedIconComponent
                    name={"Pencil"}
                    className={cn(
                      "h-4 w-4 flex-shrink-0 ",
                      !isEditing
                        ? "text-primary hover:text-muted-foreground"
                        : "text-muted-foreground hover:text-primary",
                    )}
                  />
                </Button>
              )}
            </div>

            {/* model provider selection */}
            <div className="relative overflow-x-hidden min-w-[300px] ">
              <div
                className={cn(
                  "flex flex-col p-4 gap-3 transition-all duration-300 ease-in-out min-h-[480px] h-[480px]",
                  isEditing
                    ? "opacity-0 -translate-x-full absolute inset-0"
                    : "opacity-100 translate-x-0",
                )}
              >
                <ModelProviderSelection
                  llmModels={llmModels}
                  embeddingModels={embeddingModels}
                  isModelEnabled={isModelEnabled}
                  onModelToggle={handleModelToggle}
                />
              </div>

              {/* Edit */}
              <div
                className={cn(
                  "flex flex-col transition-all duration-300 ease-in-out",
                  isEditing
                    ? "opacity-100 translate-x-0"
                    : "opacity-0 translate-x-full absolute inset-0",
                )}
              >
                <ModelProviderEdit
                  authName={authName}
                  onAuthNameChange={setAuthName}
                  apiKey={apiKey}
                  onApiKeyChange={setApiKey}
                  apiBase={apiBase}
                  onApiBaseChange={setApiBase}
                  providerName={selectedProvider?.provider}
                />
                <ModelProviderActive
                  activeLLMs={activeLLMNames}
                  activeEmbeddings={activeEmbeddingNames}
                />
              </div>
            </div>

            {/* model provider footer */}
            <div className="flex justify-end border-t p-4 min-w-[300px] gap-2">
              {selectedProvider?.is_enabled && !isEditing && (
                <>
                  <Button
                    variant="ghost"
                    className="w-full"
                    onClick={() => {
                      setPendingModelChanges({});
                      setIsEditing(false);
                      onClose();
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    className="w-full"
                    disabled={!hasPendingChanges}
                    onClick={applyPendingModelChanges}
                  >
                    Update
                  </Button>
                </>
              )}
              {(!selectedProvider?.is_enabled || isEditing) && (
                <>
                  {selectedProvider?.is_enabled && (
                    <Button
                      variant="ghost"
                      className="w-full"
                      onClick={() => {
                        setPendingModelChanges({});
                        setIsEditing(false);
                        onClose();
                      }}
                    >
                      Cancel
                    </Button>
                  )}
                  <Button
                    className="w-full"
                    loading={isPending}
                    disabled={!apiKey.trim()}
                    onClick={handleConfigureProvider}
                  >
                    {selectedProvider?.is_enabled ? "Update" : "Configure"}
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ModelProviderModal;
