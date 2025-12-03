import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Switch } from "@/components/ui/switch";
import { Model } from "@/pages/SettingsPage/pages/ModelProvidersPage/components/types";

interface ModelProviderSelectionProps {
  llmModels: Model[];
  embeddingModels: Model[];
  isModelEnabled: (modelName: string) => boolean;
  onModelToggle: (modelName: string, enabled: boolean) => void;
}

const ModelProviderSelection = ({
  llmModels,
  embeddingModels,
  isModelEnabled,
  onModelToggle,
}: ModelProviderSelectionProps) => {
  return (
    <>
      {llmModels.length > 0 && (
        <>
          <div className="text-[13px] font-semibold text-muted-foreground">
            LLM
          </div>
          {llmModels.map((model) => {
            const enabled = isModelEnabled(model.model_name);
            return (
              <div
                key={model.model_name}
                className="flex flex-row items-center justify-between"
              >
                <div className="flex flex-row items-center gap-2">
                  <ForwardedIconComponent
                    name={model.metadata?.icon || "Bot"}
                    className="w-5 h-5"
                  />
                  <span className="text-sm">{model.model_name}</span>
                </div>
                <Switch
                  checked={enabled}
                  onCheckedChange={(checked) =>
                    onModelToggle(model.model_name, checked)
                  }
                />
              </div>
            );
          })}
        </>
      )}
      {embeddingModels.length > 0 && (
        <>
          <div className="text-[13px] font-semibold text-muted-foreground pt-2">
            Embedding
          </div>
          {embeddingModels.map((model) => {
            const enabled = isModelEnabled(model.model_name);
            return (
              <div
                key={model.model_name}
                className="flex flex-row items-center justify-between"
              >
                <div className="flex flex-row items-center gap-2">
                  <ForwardedIconComponent
                    name={model.metadata?.icon || "Bot"}
                    className="w-5 h-5"
                  />
                  <span className="text-sm">{model.model_name}</span>
                </div>
                <Switch
                  checked={enabled}
                  onCheckedChange={(checked) =>
                    onModelToggle(model.model_name, checked)
                  }
                />
              </div>
            );
          })}
        </>
      )}
    </>
  );
};

export default ModelProviderSelection;
