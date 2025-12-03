import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { cn } from "@/utils/utils";
import { Model, DefaultModelData } from "./types";

type ModelListItemProps = {
  model: Model;
  providerName: string;
  // type: 'enabled' | 'available';
  isModelEnabled: boolean;
  defaultModelData?: DefaultModelData;
  onToggleModel: (
    providerName: string,
    modelName: string,
    enabled: boolean,
  ) => void;
  onSetDefaultModel: (
    providerName: string,
    modelName: string,
    modelType: string,
  ) => void;
  onClearDefaultModel: (modelType: string) => void;
};

const ModelListItem = ({
  model,
  providerName,
  // type,
  isModelEnabled,
  defaultModelData,
  onToggleModel,
  onSetDefaultModel,
  onClearDefaultModel,
}: ModelListItemProps) => {
  const isPreview = model.metadata.preview;
  const modelType = model.metadata.model_type || "llm";
  const isLanguageModel = modelType === "llm";
  const isDefaultModel =
    defaultModelData?.default_model?.model_name === model.model_name &&
    defaultModelData?.default_model?.provider === providerName;

  const handleDefaultToggle = () => {
    const modelTypeKey = isLanguageModel ? "language" : "embedding";
    if (isDefaultModel) {
      onClearDefaultModel(modelTypeKey);
    } else {
      onSetDefaultModel(providerName, model.model_name, modelTypeKey);
    }
  };

  return (
    <div className="flex items-center gap-3 py-1 rounded hover:bg-muted/50">
      {/* {type === "enabled" && (
        <Checkbox
          checked={isModelEnabled}
          onCheckedChange={(checked) => {
            onToggleModel(providerName, model.model_name, checked as boolean);
          }}
        />
      )} */}

      <div>{model.model_name}</div>

      <div className="flex items-center gap-2">
        {model.metadata.reasoning && (
          <ShadTooltip content="Reasoning model" side="right">
            <div>
              <ForwardedIconComponent
                name="Brain"
                className="w-4 h-4 text-muted-foreground cursor-pointer"
              />
            </div>
          </ShadTooltip>
        )}
        {model.metadata.tool_calling && (
          <ShadTooltip content="Tooling" side="right">
            <div>
              <ForwardedIconComponent
                name="Hammer"
                className="w-4 h-4 text-muted-foreground cursor-pointer"
              />
            </div>
          </ShadTooltip>
        )}
        {isPreview && (
          <ShadTooltip content="Preview" side="right">
            <div>
              <ForwardedIconComponent
                name="Eye"
                className="w-4 h-4 text-muted-foreground cursor-pointer"
              />
            </div>
          </ShadTooltip>
        )}
        {!isLanguageModel && (
          <ShadTooltip content="Embedding Model" side="right">
            <div>
              <ForwardedIconComponent
                name="Layers"
                className="w-4 h-4 text-muted-foreground cursor-pointer"
              />
            </div>
          </ShadTooltip>
        )}
      </div>

      <div className="ml-auto">
        {isModelEnabled && (
          <ShadTooltip
            content={
              isDefaultModel
                ? isLanguageModel
                  ? "Default LLM Model"
                  : "Default Embedding Model"
                : isLanguageModel
                  ? "Set as Default LLM Model"
                  : "Set as Default Embedding Model"
            }
            side="left"
          >
            <Button
              size="icon"
              variant="ghost"
              className="h-5 w-5"
              onClick={handleDefaultToggle}
              data-testid={`default-${model.model_name}`}
            >
              {isLanguageModel ? (
                <ForwardedIconComponent
                  name={isDefaultModel ? "Sparkle" : "Sparkle"}
                  className={cn(
                    "h-4 w-4",
                    isDefaultModel
                      ? "text-yellow-500 fill-yellow-500"
                      : "text-muted-foreground hover:text-yellow-500",
                  )}
                />
              ) : (
                <ForwardedIconComponent
                  name={isDefaultModel ? "Zap" : "Zap"}
                  className={cn(
                    "h-4 w-4",
                    isDefaultModel
                      ? "text-purple-500 fill-purple-500"
                      : "text-muted-foreground hover:text-purple-500",
                  )}
                />
              )}
            </Button>
          </ShadTooltip>
        )}
      </div>
    </div>
  );
};

export default ModelListItem;
