import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Switch } from "@/components/ui/switch";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";

import { Model } from "@/modals/modelProviderModal/components/types";
import { cn } from "@/utils/utils";

export interface ModelProviderSelectionProps {
  availableModels: Model[];
  onModelToggle: (modelName: string, enabled: boolean) => void;
  modelType: "llm" | "embeddings" | "all";
  providerName?: string;
  isEnabledModel?: boolean;
}

interface ModelRowProps {
  model: Model;
  enabled: boolean;
  onToggle: (modelName: string, enabled: boolean) => void;
  testIdPrefix: string;
  isEnabledModel?: boolean;
}

/** Single row displaying a model with its toggle switch */
const ModelRow = ({
  onToggle,
  model,
  enabled,
  testIdPrefix,
  isEnabledModel,
}: ModelRowProps) => (
  <div className="flex flex-row items-center justify-between h-[24px]">
    <div className="flex flex-row items-center gap-2">
      <ForwardedIconComponent
        name={model.metadata?.icon || "Bot"}
        className={cn("w-5 h-5", { grayscale: !isEnabledModel })}
      />
      <span
        className={cn("text-sm", { "text-muted-foreground": !isEnabledModel })}
      >
        {model.model_name}
      </span>
    </div>
    {isEnabledModel && (
      <Switch
        checked={enabled}
        onCheckedChange={(checked) => onToggle(model.model_name, checked)}
        data-testid={`${testIdPrefix}-toggle-${model.model_name}`}
      />
    )}
  </div>
);

/**
 * Displays lists of LLM and embedding models with toggle switches.
 * Allows users to enable/disable individual models for a provider.
 */
const ModelSelection = ({
  modelType = "llm",
  availableModels,
  onModelToggle,
  providerName,
  isEnabledModel,
}: ModelProviderSelectionProps) => {
  const { data: enabledModelsData } = useGetEnabledModels();

  const isModelEnabled = (modelName: string): boolean => {
    if (!providerName || !enabledModelsData?.enabled_models) return false;
    return enabledModelsData.enabled_models[providerName]?.[modelName] ?? false;
  };

  const llmModels = availableModels.filter(
    (model) => model.metadata?.model_type === "llm",
  );
  const embeddingModels = availableModels.filter(
    (model) => model.metadata?.model_type === "embeddings",
  );

  const renderModelSection = (
    title: string,
    models: Model[],
    testIdPrefix: string,
  ) => {
    if (models.length === 0) return null;
    return (
      <div data-testid={`${testIdPrefix}-models-section`}>
        <div className="text-[13px] font-semibold text-muted-foreground">
          {title}
        </div>
        <div className="flex flex-col gap-2 pt-4">
          {models.map((model) => (
            <ModelRow
              key={model.model_name}
              model={model}
              enabled={isModelEnabled(model.model_name)}
              onToggle={onModelToggle}
              testIdPrefix={testIdPrefix}
              isEnabledModel={isEnabledModel}
            />
          ))}
        </div>
      </div>
    );
  };

  const isOllama = providerName?.toLowerCase() === "ollama";
  const noModelsAvailable =
    (modelType === "llm" && llmModels.length === 0) ||
    (modelType === "embeddings" && embeddingModels.length === 0) ||
    (modelType === "all" && availableModels.length === 0);

  return (
    <div data-testid="model-provider-selection" className="flex flex-col gap-6">
      {isOllama && noModelsAvailable ? (
        <div className="flex flex-col items-center justify-center p-8 text-center border border-dashed rounded-lg bg-muted/30">
          <ForwardedIconComponent
            name="Info"
            className="w-10 h-10 mb-4 text-muted-foreground"
          />
          <h3 className="mb-2 text-sm font-semibold text-foreground">
            No models available
          </h3>
          <p className="max-w-[300px] text-xs text-muted-foreground leading-relaxed">
            It looks like you don't have any
            {modelType === "llm"
              ? " language"
              : modelType === "embeddings"
                ? " embedding"
                : ""}{" "}
            models installed for Ollama. Please pull the models you want to use.
          </p>
          <a
            href="https://ollama.com/library"
            target="_blank"
            rel="noreferrer"
            className="mt-6 text-xs font-medium text-primary underline underline-offset-4 hover:opacity-80 transition-opacity"
          >
            Check Ollama Library
          </a>
        </div>
      ) : (
        <>
          {modelType === "all" ? (
            <>
              {renderModelSection("Language Models", llmModels, "llm")}
              {renderModelSection(
                "Embedding Models",
                embeddingModels,
                "embeddings",
              )}
            </>
          ) : modelType === "llm" ? (
            renderModelSection("Language Models", llmModels, "llm")
          ) : (
            renderModelSection(
              "Embedding Models",
              embeddingModels,
              "embeddings",
            )
          )}
        </>
      )}
    </div>
  );
};

export default ModelSelection;
