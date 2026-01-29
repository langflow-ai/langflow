import { useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import type { AssistantModel } from "../assistant-panel.types";

interface ModelSelectorProps {
  selectedModel: AssistantModel | null;
  onModelChange: (model: AssistantModel) => void;
}

export function ModelSelector({
  selectedModel,
  onModelChange,
}: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const { data: providersData = [], isLoading } = useGetModelProviders({});
  const { data: enabledModelsData } = useGetEnabledModels();

  // Filter only enabled providers and their ACTIVE models (toggled on by user)
  const enabledProviders = useMemo(() => {
    const enabledModels = enabledModelsData?.enabled_models || {};

    return providersData
      .filter((provider) => provider.is_enabled)
      .map((provider) => {
        const providerEnabledModels = enabledModels[provider.provider] || {};
        return {
          ...provider,
          // Filter only models that are enabled AND not embeddings
          models: provider.models.filter(
            (model) =>
              providerEnabledModels[model.model_name] === true &&
              !model.model_name.includes("embedding"),
          ),
        };
      })
      .filter((provider) => provider.models.length > 0);
  }, [providersData, enabledModelsData]);

  // Flatten all models for easy selection
  const allModels = useMemo(() => {
    return enabledProviders.flatMap((provider) =>
      provider.models.map((model) => ({
        id: `${provider.provider}-${model.model_name}`,
        name: model.model_name,
        provider: provider.provider,
        displayName: model.model_name,
        icon: provider.icon || "Bot",
      })),
    );
  }, [enabledProviders]);

  // Set default model if none selected
  const currentModel = selectedModel || allModels[0] || null;

  const handleModelSelect = (model: (typeof allModels)[0]) => {
    onModelChange({
      id: model.id,
      name: model.name,
      provider: model.provider,
      displayName: model.displayName,
    });
    setIsOpen(false);
  };

  if (isLoading) {
    return (
      <Button
        variant="ghost"
        size="sm"
        className="h-7 gap-1.5 px-2 text-xs text-muted-foreground"
        disabled
      >
        <span className="text-accent-emerald-foreground">•</span>
        <span>Loading...</span>
      </Button>
    );
  }

  if (allModels.length === 0) {
    return (
      <Button
        variant="ghost"
        size="sm"
        className="h-7 gap-1.5 px-2 text-xs text-muted-foreground"
        disabled
      >
        <span className="text-muted-foreground">•</span>
        <span>No models configured</span>
      </Button>
    );
  }

  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground"
        >
          <span className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 bg-muted-foreground" />
            <span className="font-medium tracking-wide">AI</span>
          </span>
          <span>{currentModel?.displayName || "Select model"}</span>
          <ForwardedIconComponent
            name={isOpen ? "ChevronUp" : "ChevronDown"}
            className="h-3 w-3"
          />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="max-h-96 w-72 overflow-y-auto p-2">
        {enabledProviders.map((provider, index) => (
          <div key={provider.provider}>
            {index > 0 && <DropdownMenuSeparator className="my-2" />}
            <DropdownMenuLabel className="flex items-center gap-2 px-2 py-2 text-xs font-medium text-muted-foreground">
              <ForwardedIconComponent
                name={provider.icon || "Bot"}
                className="h-4 w-4"
              />
              {provider.provider}
            </DropdownMenuLabel>
            <div className="flex flex-col gap-1">
              {provider.models.map((model) => {
                const modelId = `${provider.provider}-${model.model_name}`;
                const isSelected = currentModel?.id === modelId;
                return (
                  <DropdownMenuItem
                    key={modelId}
                    onClick={() =>
                      handleModelSelect({
                        id: modelId,
                        name: model.model_name,
                        provider: provider.provider,
                        displayName: model.model_name,
                        icon: provider.icon || "Bot",
                      })
                    }
                    className="flex cursor-pointer items-center justify-between rounded-md px-3 py-2 pl-8"
                  >
                    <span className="text-sm">{model.model_name}</span>
                    {isSelected && (
                      <ForwardedIconComponent name="Check" className="h-4 w-4" />
                    )}
                  </DropdownMenuItem>
                );
              })}
            </div>
          </div>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
