import { ForwardedIconComponent } from '@/components/common/genericIconComponent';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Provider, EnabledModelsData, DefaultModelData } from './types';
import ModelListItem from './model-list-item';
import { useState, useEffect } from 'react';

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
  type: 'enabled' | 'available';
  enabledModelsData?: EnabledModelsData;
  defaultModelData?: DefaultModelData;
  onBatchToggleModels: (updates: ModelUpdate[]) => void;
  onSetDefaultModel: (
    providerName: string,
    modelName: string,
    modelType: string
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
  onBatchToggleModels,
  onSetDefaultModel,
  onClearDefaultModel,
}: ProviderModelsDialogProps) => {
  const [pendingModelToggles, setPendingModelToggles] = useState<Map<string, boolean>>(new Map());
  const [pendingDefaultModel, setPendingDefaultModel] = useState<DefaultModelChange>(null);
  const [shouldClearDefault, setShouldClearDefault] = useState(false);

  // Reset pending changes when dialog opens or provider changes
  useEffect(() => {
    if (open) {
      setPendingModelToggles(new Map());
      setPendingDefaultModel(null);
      setShouldClearDefault(false);
    }
  }, [open, provider?.provider]);

  if (!provider) return null;

  const applyChanges = () => {
    // Only apply changes if there are any pending
    if (pendingModelToggles.size === 0 && !pendingDefaultModel && !shouldClearDefault) {
      return;
    }

    // Apply model toggles - convert Map to array for batch update
    if (pendingModelToggles.size > 0) {
      const updates = Array.from(pendingModelToggles.entries()).map(([modelName, enabled]) => ({
        provider: provider.provider,
        model_id: modelName,
        enabled,
      }));

      // Use batch update function to send all changes in one API call
      onBatchToggleModels(updates);
    }

    // Apply default model changes
    if (shouldClearDefault) {
      onClearDefaultModel('language');
    } else if (pendingDefaultModel) {
      onSetDefaultModel(
        pendingDefaultModel.providerName,
        pendingDefaultModel.modelName,
        pendingDefaultModel.modelType
      );
    }

    // Reset pending changes
    setPendingModelToggles(new Map());
    setPendingDefaultModel(null);
    setShouldClearDefault(false);
  };

  const handleSave = (e: React.MouseEvent) => {
    e.stopPropagation();
    applyChanges();
    onOpenChange(false);
  };

  const handleClose = (e: React.MouseEvent) => {
    e.stopPropagation();
    applyChanges();
    onOpenChange(false);
  };

  const handleToggleModelLocal = (
    providerName: string,
    modelName: string,
    enabled: boolean
  ) => {
    setPendingModelToggles(prev => {
      const updated = new Map(prev);
      updated.set(modelName, enabled);
      return updated;
    });
  };

  const handleSetDefaultModelLocal = (
    providerName: string,
    modelName: string,
    modelType: string
  ) => {
    setPendingDefaultModel({ providerName, modelName, modelType });
    setShouldClearDefault(false);
  };

  const handleClearDefaultModelLocal = (modelType: string) => {
    setShouldClearDefault(true);
    setPendingDefaultModel(null);
  };

  const hasModels = provider.models && provider.models.length > 0;

  // Get the effective default model (considering pending changes)
  const getEffectiveDefaultModel = () => {
    if (shouldClearDefault) {
      return null;
    }
    if (pendingDefaultModel && pendingDefaultModel.providerName === provider.provider) {
      return {
        model_name: pendingDefaultModel.modelName,
        provider: pendingDefaultModel.providerName,
        model_type: pendingDefaultModel.modelType,
      };
    }
    return defaultModelData?.default_model;
  };

  const effectiveDefaultModel = getEffectiveDefaultModel();
  const effectiveDefaultModelName = effectiveDefaultModel?.model_name || 'None';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[600px] gap-2 px-1 py-6 max-h-[80vh] overflow-y-auto">
        <DialogHeader className="px-5 pb-2">
          <DialogTitle className="gap-2 flex items-center w-full mr-5 mb-2">
            <ForwardedIconComponent
              name={provider.icon || 'Bot'}
              className="w-6 h-6"
            />
            <span>{provider.provider}</span>
          </DialogTitle>
          <DialogDescription>
            {type === 'enabled' ? (
              <div>
                Select Models to show for this Provider. The current selected
                default model for {provider.provider} is{' '}
                <span className="text-primary font-medium">
                  {effectiveDefaultModelName}
                </span>
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
                const currentEnabledState =
                  enabledModelsData?.enabled_models?.[provider.provider]?.[
                    model.model_name
                  ] ?? true;

                // Check if there's a pending change for this model
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
                      default_model: effectiveDefaultModel,
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
            className="mr-1"
            variant="outline"
            data-testid="btn_cancel_delete_confirmation_modal"
          >
            Close
          </Button>

          {type === 'enabled' && (
            <Button
              onClick={handleSave}
              type="submit"
              data-testid="btn_delete_delete_confirmation_modal"
            >
              Save
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ProviderModelsDialog;
