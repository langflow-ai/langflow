import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { PopoverTrigger } from "@/components/ui/popover";
import { RECEIVING_INPUT_VALUE } from "@/constants/constants";
import { cn } from "@/utils/utils";
import { RefObject } from "react";
import { ModelOption, SelectedModel } from "../types";

interface ModelTriggerProps {
  open: boolean;
  disabled: boolean;
  options: ModelOption[];
  selectedModel: SelectedModel | null;
  placeholder?: string;
  hasEnabledProviders: boolean;
  onOpenManageProviders: () => void;
  id: string;
  refButton: RefObject<HTMLButtonElement | null>;
}

const ModelTrigger = ({
  open,
  disabled,
  options,
  selectedModel,
  placeholder = "Setup Provider",
  hasEnabledProviders,
  onOpenManageProviders,
  id,
  refButton,
}: ModelTriggerProps) => {
  const renderSelectedIcon = () => {
    if (disabled || options.length === 0) {
      return null;
    }

    return selectedModel?.icon ? (
      <ForwardedIconComponent
        name={selectedModel.icon || "Bot"}
        className="h-4 w-4 flex-shrink-0"
      />
    ) : null;
  };

  if (!hasEnabledProviders) {
    return (
      <Button
        variant="default"
        size="sm"
        className="w-full"
        onClick={onOpenManageProviders}
      >
        <ForwardedIconComponent name="Brain" className="h-4 w-4" />
        <div className="text-[13px]">{placeholder}</div>
      </Button>
    );
  }

  return (
    <div className="flex w-full flex-col">
      <PopoverTrigger asChild>
        <Button
          disabled={disabled || options.length === 0}
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
                RECEIVING_INPUT_VALUE
              ) : (
                <div
                  className={cn(
                    "truncate",
                    !selectedModel?.name && "text-muted-foreground",
                  )}
                >
                  {selectedModel?.name || "Select a model"}
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
