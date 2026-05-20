import { RefObject } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/utils/utils";
import type { SelectedModel } from "../types";

interface ModelTriggerProps {
  open: boolean;
  disabled: boolean;
  visibleOptionsCount: number;
  selectedModel: SelectedModel | null;
  showCloudIncompatibleWarning?: boolean;
  placeholder?: string;
  hasEnabledProviders: boolean;
  onOpenManageProviders: () => void;
  id: string;
  refButton: RefObject<HTMLButtonElement | null>;
  showEmptyState?: boolean;
  emptyStateLabel?: string;
}

const ModelTrigger = ({
  open,
  disabled,
  visibleOptionsCount,
  selectedModel,
  showCloudIncompatibleWarning = false,
  placeholder = "Setup Provider",
  hasEnabledProviders,
  onOpenManageProviders,
  id,
  refButton,
  showEmptyState = false,
  emptyStateLabel = "No models enabled",
}: ModelTriggerProps) => {
  const { t } = useTranslation();
  const hasVisibleOptions = visibleOptionsCount > 0;


  const renderSelectedIcon = () => {
    if (disabled) {
      return null;
    }

    return selectedModel?.icon ? (
      <ForwardedIconComponent
        name={selectedModel.icon || "Bot"}
        className="h-4 w-4 flex-shrink-0"
      />
    ) : null;
  };

  // Check if we're in empty state mode (showEmptyState=true and no options)
  const isEmptyStateMode = showEmptyState && !hasVisibleOptions;

  if (!hasEnabledProviders && !showEmptyState && !hasVisibleOptions) {
    return (
      <Button
        variant="outline"
        size="xs"
        className="dropdown-component-false-outline w-full justify-start gap-2 py-2 font-normal"
        onClick={onOpenManageProviders}
      >
        <ForwardedIconComponent
          name="BrainCircuit"
          className="h-4 w-4 flex-shrink-0 text-muted-foreground"
        />
        <div className="text-[13px] text-muted-foreground">
          {placeholder === "Setup Provider"
            ? t("model.setupProvider")
            : placeholder}
        </div>
      </Button>
    );
  }

  return (
    <div className="flex w-full flex-col">
      <PopoverTrigger asChild>
        <Button
          disabled={
            disabled ||
            (!hasVisibleOptions && !isEmptyStateMode && !selectedModel)
          }
          variant="primary"
          size="xs"
          role="combobox"
          ref={refButton}
          aria-expanded={open}
          data-testid={id}
          className={cn(
            "dropdown-component-false-outline py-2",
            "no-focus-visible w-full justify-between font-normal disabled:bg-muted disabled:text-muted-foreground",
          )}
        >
          <span
            className="flex w-full items-center gap-2 overflow-hidden"
            data-testid={`value-dropdown-${id}`}
          >
            {renderSelectedIcon()}
            <span className="truncate">
              {disabled ? (
                t("component.receivingInput")
              ) : isEmptyStateMode ? (
                <div className="truncate text-muted-foreground">
                  {emptyStateLabel}
                </div>
              ) : (
                <div className="flex min-w-0 flex-col items-start">
                  <div
                    className={cn(
                      "truncate",
                      !selectedModel?.name && "text-muted-foreground",
                    )}
                  >
                    {selectedModel?.name || t("model.selectModel")}
                  </div>
                  {showCloudIncompatibleWarning && (
                    <div className="flex items-center gap-1 text-[11px] text-accent-emerald-foreground">
                      <ForwardedIconComponent
                        name="CloudOff"
                        className="h-3 w-3"
                      />
                      <span>{t("cloud.notAvailableInCloud")}</span>
                    </div>
                  )}
                </div>
              )}
            </span>
          </span>
          <ForwardedIconComponent
            name={disabled ? "Lock" : "ChevronsUpDown"}
            className={cn(
              "ml-2 h-4 w-4 shrink-0 text-foreground",
              disabled
                ? "text-placeholder-foreground hover:text-placeholder-foreground"
                : "hover:text-foreground",
            )}
          />
        </Button>
      </PopoverTrigger>
    </div>
  );
};

export default ModelTrigger;
