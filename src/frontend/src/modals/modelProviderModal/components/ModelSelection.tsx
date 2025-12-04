import ForwardedIconComponent from '@/components/common/genericIconComponent';
import { Switch } from '@/components/ui/switch';
import { useGetEnabledModels } from '@/controllers/API/queries/models/use-get-enabled-models';

import { Model } from '@/modals/modelProviderModal/components/types';

export interface ModelProviderSelectionProps {
  availableModels: Model[];
  onModelToggle: (modelName: string, enabled: boolean) => void;
  modelType: 'llm' | 'embeddings';
  providerName?: string;
}

interface ModelRowProps {
  model: Model;
  enabled: boolean;
  onToggle: (modelName: string, enabled: boolean) => void;
  testIdPrefix: string;
}

/** Single row displaying a model with its toggle switch */
const ModelRow = ({
  onToggle,
  model,
  enabled,
  testIdPrefix,
}: ModelRowProps) => (
  <div className="flex flex-row items-center justify-between">
    <div className="flex flex-row items-center gap-2">
      <ForwardedIconComponent
        name={model.metadata?.icon || 'Bot'}
        className="w-5 h-5"
      />
      <span className="text-sm">{model.model_name}</span>
    </div>
    <Switch
      checked={enabled}
      onCheckedChange={checked => onToggle(model.model_name, checked)}
      data-testid={`${testIdPrefix}-toggle-${model.model_name}`}
    />
  </div>
);

/**
 * Displays lists of LLM and embedding models with toggle switches.
 * Allows users to enable/disable individual models for a provider.
 */
const ModelSelection = ({
  modelType = 'llm',
  availableModels,
  onModelToggle,
  providerName,
}: ModelProviderSelectionProps) => {
  const { data: enabledModelsData } = useGetEnabledModels();

  console.log({ enabledModelsData });

  const isModelEnabled = (modelName: string): boolean => {
    if (!providerName || !enabledModelsData?.enabled_models) return false;
    return enabledModelsData.enabled_models[providerName]?.[modelName] ?? false;
  };

  return (
    <div data-testid="model-provider-selection">
      {availableModels.length > 0 && (
        <div data-testid="llm-models-section">
          <div className="text-[13px] font-semibold text-muted-foreground">
            {modelType === 'llm' ? 'LLM' : 'Embeddings'}
          </div>
          <div className="flex flex-col gap-2 pt-4">
            {availableModels.map(model => (
              <ModelRow
                key={model.model_name}
                model={model}
                enabled={isModelEnabled(model.model_name)}
                onToggle={onModelToggle}
                testIdPrefix={modelType}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ModelSelection;
