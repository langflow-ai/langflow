import { useEffect, useMemo, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { AssistantModel } from "../assistant-panel.types";
import { useEnabledModels } from "../hooks";

interface ModelSelectorProps {
  selectedModel: AssistantModel | null;
  onModelChange: (model: AssistantModel) => void;
}

export function ModelSelector({
  selectedModel,
  onModelChange,
}: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const { filteredProviders: enabledProviders, isLoading } = useEnabledModels();

  // Flatten all models for easy selection
  const allModels = useMemo(() => {
    return enabledProviders.flatMap((provider) =>
      provider.models.map((model) => ({
        id: `${provider.provider}-${model.model_name}`,
        name: model.model_name,
        provider: provider.provider,
        displayName: model.model_name,
        icon: provider.icon,
      })),
    );
  }, [enabledProviders]);

  // Auto-select first available model if none selected or if the selected model
  // is no longer available (e.g., provider was removed or model was disabled)
  useEffect(() => {
    if (allModels.length === 0) return;

    const isSelectedModelValid =
      selectedModel && allModels.some((m) => m.id === selectedModel.id);

    if (!isSelectedModelValid) {
      const defaultModel = allModels[0];
      onModelChange({
        id: defaultModel.id,
        name: defaultModel.name,
        provider: defaultModel.provider,
        displayName: defaultModel.displayName,
      });
    }
  }, [selectedModel, allModels, onModelChange]);

  const currentModel = selectedModel || allModels[0] || null;

  // Resolve the provider icon for the currently selected model
  const currentProviderIcon = useMemo(() => {
    if (!currentModel) return "Bot";
    const provider = enabledProviders.find(
      (p) => p.provider === currentModel.provider,
    );
    return provider?.icon || "Bot";
  }, [currentModel, enabledProviders]);

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
          data-testid="assistant-model-selector"
          className="h-7 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground active:!scale-100"
        >
          <span className="flex items-center gap-1.5">
            <ForwardedIconComponent
              name={currentProviderIcon}
              className="h-4 w-4 shrink-0"
            />
          </span>
          <span>{currentModel?.displayName || "Select model"}</span>
          <ForwardedIconComponent
            name={isOpen ? "ChevronUp" : "ChevronDown"}
            className="h-3 w-3"
          />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className="z-[70] max-h-96 w-72 overflow-y-auto p-2"
      >
        {enabledProviders.map((provider, index) => (
          <div key={provider.provider}>
            {index > 0 && <DropdownMenuSeparator className="my-2" />}
            <DropdownMenuLabel className="text-xs font-semibold my-2 ml-2 text-muted-foreground">
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
                        icon: provider.icon,
                      })
                    }
                    className="flex w-full cursor-pointer items-center rounded-md px-3 py-2"
                  >
                    <div className="flex w-full items-center gap-2">
                      <ForwardedIconComponent
                        name={provider.icon}
                        className="h-4 w-4 shrink-0 text-primary ml-2"
                      />
                      <div className="truncate text-[13px]">
                        {model.model_name}
                      </div>
                      <div className="pl-2 ml-auto">
                        <ForwardedIconComponent
                          name="Check"
                          className={cn(
                            "h-4 w-4 shrink-0 text-primary",
                            isSelected ? "opacity-100" : "opacity-0",
                          )}
                        />
                      </div>
                    </div>
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
