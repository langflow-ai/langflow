import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
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
import { useRefreshModelInputs } from "@/hooks/use-refresh-model-inputs";
import ModelProviderModal from "@/modals/modelProviderModal";
import { cn } from "@/utils/utils";
import type { AssistantModel } from "../assistant-panel.types";
import { classifyModelStrength } from "../helpers/model-strength";
import { useEnabledModels } from "../hooks";

interface ModelSelectorProps {
  selectedModel: AssistantModel | null;
  onModelChange: (model: AssistantModel) => void;
}

export function ModelSelector({
  selectedModel,
  onModelChange,
}: ModelSelectorProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [isManageProvidersOpen, setIsManageProvidersOpen] = useState(false);
  const { filteredProviders: enabledProviders, isLoading } = useEnabledModels();
  const { refresh: refreshAllModelInputs } = useRefreshModelInputs();

  const handleRefreshList = async () => {
    setIsOpen(false);
    await refreshAllModelInputs({ silent: true });
  };

  const handleOpenManageProviders = () => {
    setIsOpen(false);
    setIsManageProvidersOpen(true);
  };

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

  // Discreet UX hint: when the selected model is too small for agent loops
  // (heuristic in helpers/model-strength.ts), surface an inline italic note
  // next to the chip. Classification is advisory; the dropdown behaves the
  // same regardless of result. Re-evaluated on every change of currentModel.
  // Must stay above the early returns below — Rules of Hooks: hook count
  // can't change between renders, and isLoading flips false on first fetch.
  const modelStrength = useMemo(
    () => classifyModelStrength(currentModel?.name ?? ""),
    [currentModel?.name],
  );

  if (isLoading) {
    return (
      <Button
        variant="ghost"
        size="sm"
        className="h-7 gap-1.5 px-2 text-xs text-muted-foreground"
        disabled
      >
        <span className="text-accent-emerald-foreground">•</span>
        <span>{t("assistant.loading")}</span>
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
        <span>{t("assistant.noModels")}</span>
      </Button>
    );
  }

  return (
    // gap-3: leaves room for the chip's focus ring (~4px outline + offset)
    // so the italic warning to the right doesn't visually overlap it after
    // the user clicks the dropdown and the button keeps keyboard focus.
    <div className="flex items-center gap-3">
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
            <span>
              {currentModel?.displayName || t("assistant.selectModel")}
            </span>
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
          <DropdownMenuSeparator className="my-2" />
          <DropdownMenuItem
            onClick={(e) => {
              e.preventDefault();
              handleRefreshList();
            }}
            data-testid="assistant-refresh-model-list"
            className="flex w-full cursor-pointer items-center rounded-md px-3 py-2 text-muted-foreground hover:text-foreground"
          >
            <div className="flex w-full items-center gap-2">
              <span className="ml-2 text-[13px]">
                {t("modelInput.refreshList")}
              </span>
              <ForwardedIconComponent
                name="RotateCw"
                className="ml-auto h-4 w-4 shrink-0"
              />
            </div>
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={(e) => {
              e.preventDefault();
              handleOpenManageProviders();
            }}
            data-testid="assistant-manage-model-providers"
            className="flex w-full cursor-pointer items-center rounded-md px-3 py-2 text-muted-foreground hover:text-foreground"
          >
            <div className="flex w-full items-center gap-2">
              <span className="ml-2 text-[13px]">
                {t("modelInput.manageProviders")}
              </span>
              <ForwardedIconComponent
                name="Settings"
                className="ml-auto h-4 w-4 shrink-0"
              />
            </div>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {modelStrength === "weak" && (
        <span
          data-testid="assistant-model-weak-hint"
          className="select-none text-xs italic text-muted-foreground/70"
          title="Smaller models may underperform on agent tasks"
        >
          Smaller models may underperform on agent tasks
        </span>
      )}
      {isManageProvidersOpen && (
        <ModelProviderModal
          open={isManageProvidersOpen}
          onClose={() => setIsManageProvidersOpen(false)}
          modelType="llm"
        />
      )}
    </div>
  );
}
