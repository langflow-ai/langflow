import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Provider, EnabledModelsData, DefaultModelData } from "./types";
import ModelListItem from "./model-list-item";
import { useState, useEffect } from "react";

type DefaultModelChange = {
  providerName: string;
  modelName: string;
  modelType: string;
} | null;

type ModelUpdate = {
  provider: string;
  model_id: string;
  enabled: boolean;
};

type ProviderModelsDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  provider: Provider | null;
  type: "enabled" | "available";
  enabledModelsData?: EnabledModelsData;
  defaultModelData?: DefaultModelData;
  defaultEmbeddingModelData?: DefaultModelData;
  onBatchToggleModels: (updates: ModelUpdate[]) => void;
  onSetDefaultModel: (
    providerName: string,
    modelName: string,
    modelType: string,
  ) => void;
  onClearDefaultModel: (modelType: string) => void;
};

const ProviderModelsDialog = ({
  open,
  onOpenChange,
  provider,
  type,
  enabledModelsData,
  defaultModelData,
  defaultEmbeddingModelData,
  onBatchToggleModels,
  onSetDefaultModel,
  onClearDefaultModel,
}: ProviderModelsDialogProps) => {
  const [pendingModelToggles, setPendingModelToggles] = useState<
    Map<string, boolean>
  >(new Map());
  const [pendingDefaultModel, setPendingDefaultModel] =
    useState<DefaultModelChange>(null);
  const [pendingDefaultEmbeddingModel, setPendingDefaultEmbeddingModel] =
    useState<DefaultModelChange>(null);
  const [shouldClearDefault, setShouldClearDefault] = useState(false);
  const [shouldClearEmbeddingDefault, setShouldClearEmbeddingDefault] =
    useState(false);
  const [previousOpenState, setPreviousOpenState] = useState(false);

  // Reset pending changes when dialog opens or provider changes
  useEffect(() => {
    // Reset everything when dialog first opens (closed -> open transition)
    const isDialogOpening = open && !previousOpenState;
    if (isDialogOpening) {
      setPendingModelToggles(new Map());
      setPendingDefaultModel(null);
      setPendingDefaultEmbeddingModel(null);
      setShouldClearDefault(false);
      setShouldClearEmbeddingDefault(false);
    } else if (open) {
      // When switching providers (dialog stays open), only reset provider-specific toggles
      setPendingModelToggles(new Map());
      // Don't reset default model settings - they are global across all providers
    }
    setPreviousOpenState(open);
  }, [open, provider?.provider, previousOpenState]);

  if (!provider) return null;

  const applyChanges = () => {
    // Only apply changes if there are any pending
    if (
      pendingModelToggles.size === 0 &&
      !pendingDefaultModel &&
      !pendingDefaultEmbeddingModel &&
      !shouldClearDefault &&
      !shouldClearEmbeddingDefault
    ) {
      return;
    }

    // Apply model toggles - convert Map to array for batch update
    if (pendingModelToggles.size > 0) {
      const updates = Array.from(pendingModelToggles.entries()).map(
        ([modelName, enabled]) => ({
          provider: provider.provider,
          model_id: modelName,
          enabled,
        }),
      );
      // Use batch update function to send all changes in one API call
      onBatchToggleModels(updates);
    }

    // Apply LLM default model changes
    if (shouldClearDefault) {
      onClearDefaultModel("language");
    } else if (pendingDefaultModel) {
      onSetDefaultModel(
        pendingDefaultModel.providerName,
        pendingDefaultModel.modelName,
        "language",
      );
    }

    // Apply embedding default model changes
    if (shouldClearEmbeddingDefault) {
      onClearDefaultModel("embedding");
    } else if (pendingDefaultEmbeddingModel) {
      onSetDefaultModel(
        pendingDefaultEmbeddingModel.providerName,
        pendingDefaultEmbeddingModel.modelName,
        "embedding",
      );
    }

    // Reset pending changes
    setPendingModelToggles(new Map());
    setPendingDefaultModel(null);
    setPendingDefaultEmbeddingModel(null);
    setShouldClearDefault(false);
    setShouldClearEmbeddingDefault(false);
  };

  const handleClose = (e: React.MouseEvent) => {
    e.stopPropagation();
    applyChanges();
    onOpenChange(false);
  };

  const handleOpenChange = (newOpen: boolean) => {
    // When closing the dialog (via ESC, click away, etc.), apply changes first
    if (!newOpen) {
      applyChanges();
    }
    onOpenChange(newOpen);
  };

  const handleToggleModelLocal = (
    _providerName: string,
    modelName: string,
    enabled: boolean,
  ) => {
    setPendingModelToggles((prev) => {
      const updated = new Map(prev);
      updated.set(modelName, enabled);
      return updated;
    });

    // If unchecking a model, check if it's the current default and clear it
    if (!enabled) {
      // Check LLM defaults
      if (pendingDefaultModel?.modelName === modelName) {
        setPendingDefaultModel(null);
      }
      if (defaultModelData?.default_model?.model_name === modelName) {
        setShouldClearDefault(true);
        setPendingDefaultModel(null);
      }

      // Check embedding defaults
      if (pendingDefaultEmbeddingModel?.modelName === modelName) {
        setPendingDefaultEmbeddingModel(null);
      }
      if (defaultEmbeddingModelData?.default_model?.model_name === modelName) {
        setShouldClearEmbeddingDefault(true);
        setPendingDefaultEmbeddingModel(null);
      }
    }
    // When re-enabling a model, do NOT restore default status
    // The user must explicitly click the star button to set it as default again
  };

  const handleSetDefaultModelLocal = (
    providerName: string,
    modelName: string,
    modelType: string,
  ) => {
    if (modelType === "language") {
      setPendingDefaultModel({ providerName, modelName, modelType });
      setShouldClearDefault(false);
    } else if (modelType === "embedding") {
      setPendingDefaultEmbeddingModel({ providerName, modelName, modelType });
      setShouldClearEmbeddingDefault(false);
    }
  };

  const handleClearDefaultModelLocal = (modelType: string) => {
    if (modelType === "language") {
      setShouldClearDefault(true);
      setPendingDefaultModel(null);
    } else if (modelType === "embedding") {
      setShouldClearEmbeddingDefault(true);
      setPendingDefaultEmbeddingModel(null);
    }
  };

  const hasModels = provider.models && provider.models.length > 0;

  // Get the effective default LLM model (considering pending changes)
  const getEffectiveDefaultModel = () => {
    if (shouldClearDefault) {
      return null;
    }
    // Show pending default model regardless of which provider's dialog is open
    // This ensures that when you set a default in one provider and open another,
    // you see the pending change reflected globally
    if (pendingDefaultModel) {
      return {
        model_name: pendingDefaultModel.modelName,
        provider: pendingDefaultModel.providerName,
        model_type: pendingDefaultModel.modelType,
      };
    }
    return defaultModelData?.default_model;
  };

  // Get the effective default embedding model (considering pending changes)
  const getEffectiveDefaultEmbeddingModel = () => {
    if (shouldClearEmbeddingDefault) {
      return null;
    }
    if (pendingDefaultEmbeddingModel) {
      return {
        model_name: pendingDefaultEmbeddingModel.modelName,
        provider: pendingDefaultEmbeddingModel.providerName,
        model_type: pendingDefaultEmbeddingModel.modelType,
      };
    }
    return defaultEmbeddingModelData?.default_model;
  };

  const effectiveDefaultModel = getEffectiveDefaultModel();
  const effectiveDefaultEmbeddingModel = getEffectiveDefaultEmbeddingModel();
  const effectiveDefaultModelName = effectiveDefaultModel?.model_name || "None";
  const effectiveDefaultEmbeddingModelName =
    effectiveDefaultEmbeddingModel?.model_name || "None";

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-[600px] gap-2 px-1 py-6 max-h-[80vh] overflow-y-auto">
        <DialogHeader className="px-5 pb-2">
          <DialogTitle className="gap-2 flex items-center w-full mr-5 mb-2">
            <ForwardedIconComponent
              name={provider.icon || "Bot"}
              className="w-6 h-6"
            />
            <span>{provider.provider}</span>
          </DialogTitle>
          <DialogDescription>
            {type === "enabled" ? (
              <div>
                Configure model availability for this provider using the
                checkboxes below, or designate global default models to
                standardize across all flows.
                <div className="mt-2 flex flex-col gap-1">
                  <div>
                    Default LLM:{" "}
                    <span className="text-yellow-500 font-medium">
                      {effectiveDefaultModelName}
                    </span>
                  </div>
                  <div>
                    Default Embedding:{" "}
                    <span className="text-purple-500 font-medium">
                      {effectiveDefaultEmbeddingModelName}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div>
                These models are available for use with {provider.provider} once
                enabled.
              </div>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-5 overflow-y-auto px-5">
          {hasModels ? (
            <div>
              {provider.models!.map((model, index) => {
                // Get the current enabled state from API data
                const isModelEnabledFromAPI =
                  enabledModelsData?.enabled_models?.[provider.provider]?.[
                    model.model_name
                  ];

                const modelType = model.metadata.model_type || "llm";
                const isLanguageModel = modelType === "llm";

                // Check if this model is the default for its type
                const isDefaultModelInThisList = isLanguageModel
                  ? effectiveDefaultModel?.model_name === model.model_name
                  : effectiveDefaultEmbeddingModel?.model_name ===
                    model.model_name;

                // Determine the current enabled state:
                // 1. If it's the default model, force-check it
                // 2. If backend has explicit value (true/false), use that
                // 3. If backend has no value (undefined) for this provider, default to checked
                const hasBackendValue = isModelEnabledFromAPI !== undefined;
                const currentEnabledState =
                  isDefaultModelInThisList ||
                  (hasBackendValue ? isModelEnabledFromAPI === true : true);
                const isModelEnabled = pendingModelToggles.has(model.model_name)
                  ? pendingModelToggles.get(model.model_name)!
                  : currentEnabledState;

                return (
                  <ModelListItem
                    key={`${model.model_name}-${index}`}
                    model={model}
                    providerName={provider.provider}
                    type={type}
                    isModelEnabled={isModelEnabled}
                    defaultModelData={{
                      default_model: isLanguageModel
                        ? effectiveDefaultModel
                        : effectiveDefaultEmbeddingModel,
                    }}
                    onToggleModel={handleToggleModelLocal}
                    onSetDefaultModel={handleSetDefaultModelLocal}
                    onClearDefaultModel={handleClearDefaultModelLocal}
                  />
                );
              })}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground py-4 text-center">
              No models available
            </div>
          )}
        </div>

        <DialogFooter className="px-5 pt-2">
          <Button
            onClick={handleClose}
            variant="outline"
            data-testid="btn_cancel_delete_confirmation_modal"
          >
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ProviderModelsDialog;
