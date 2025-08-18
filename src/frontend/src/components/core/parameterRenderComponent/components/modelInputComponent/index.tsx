import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandGroup,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContentWithoutPortal,
  PopoverTrigger,
} from "@/components/ui/popover";
import { RECEIVING_INPUT_VALUE } from "@/constants/constants";
import { getCustomParameterTitle } from "@/customization/components/custom-parameter";
import useAlertStore from "@/stores/alertStore";
import { convertStringToHTML } from "@/utils/stringManipulation";
import { cn } from "@/utils/utils";
import Fuse from "fuse.js";
import { useCallback, useMemo, useRef, useState } from "react";
import ForwardedIconComponent from "../../../../common/genericIconComponent";
import type { BaseInputProps } from "../../types";
import InputGlobalComponent from "../inputGlobalComponent";

export type ModelInputComponentType = {
  model_type: "language" | "embedding";
  options: {
    name: string;
    icon: string;
    category: string;
    metadata?: any;
    provider?: string;
  }[];
  placeholder: string;
  providers?: string[];
  temperature?: number;
  max_tokens?: number;
  limit?: number;
};

export type SelectedModel = {
  name: string;
  icon: string;
  category: string;
  metadata?: any;
  provider?: string;
};

export default function ModelInputComponent({
  id,
  value,
  disabled,
  handleOnNewValue,
  options = [],
  placeholder = "Select a Model",
  providers = ["OpenAI", "Anthropic"],
  helperText,
}: BaseInputProps<any> & ModelInputComponentType): JSX.Element {
  const [open, setOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<SelectedModel | null>(
    null,
  );
  const [searchTerm, setSearchTerm] = useState("");
  const refButton = useRef<HTMLButtonElement>(null);
  const isLoading = false;
  const { setErrorData } = useAlertStore();

  // Filter options based on search term
  const filteredOptions = useMemo(() => {
    try {
      if (!options || options.length === 0) return [];
      if (!searchTerm.trim()) return options;

      const fuse = new Fuse(options, {
        keys: ["name", "category", "provider"],
        threshold: 0.3,
      });
      return fuse.search(searchTerm).map((result) => result.item);
    } catch (error) {
      console.warn("Error filtering options:", error);
      return options || [];
    }
  }, [options, searchTerm]);

  // Group options by category
  const groupedOptions = useMemo(() => {
    const groups: Record<string, typeof options> = {};

    filteredOptions.forEach((option) => {
      const category = option.category || "Other";
      if (!groups[category]) {
        groups[category] = [];
      }
      groups[category].push(option);
    });

    // Sort by provider priority
    const sortedGroups: [string, typeof options][] = Object.entries(groups);

    // Move specified providers to top
    if (providers?.length) {
      sortedGroups.sort(([a], [b]) => {
        const aIndex = providers.indexOf(a);
        const bIndex = providers.indexOf(b);

        if (aIndex !== -1 && bIndex !== -1) {
          return aIndex - bIndex;
        } else if (aIndex !== -1) {
          return -1;
        } else if (bIndex !== -1) {
          return 1;
        }
        return a.localeCompare(b);
      });
    }

    return sortedGroups;
  }, [filteredOptions, providers]);

  // Handle model selection
  const handleModelSelect = useCallback(
    (modelName: string) => {
      try {
        // Find the selected option from the original options list
        const selectedOption = options.find(
          (option) => option.name === modelName,
        );

        // Update the value as an array with the selected model
        const newValue = [
          {
            name: selectedOption.name,
            icon: selectedOption.icon || "Bot",
            category: selectedOption.category || "Other",
            provider:
              selectedOption.provider || selectedOption.category || "Unknown",
            metadata: selectedOption.metadata || {},
          },
        ];

        handleOnNewValue({ value: newValue });
        setSelectedProvider(selectedOption.provider || selectedOption.category);
        setSelectedModel(selectedOption);
      } catch (error) {
        setErrorData({ title: "Error selecting model" });
      }
    },
    [options, handleOnNewValue],
  );

  const handleApiKeyChange = useCallback((newApiKey: string) => {
    // This could be used for future API key management
    console.log("API Key changed:", newApiKey);
  }, []);

  const handleSendApiKey = useCallback(() => {
    // This could be used for future API key management
    console.log("Send API Key clicked");
  }, []);

  const renderTriggerButton = () => (
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
          className="dropdown-component-false-outline py-2 no-focus-visible w-full justify-between font-normal disabled:bg-muted disabled:text-muted-foreground"
        >
          <span
            className="flex w-full items-center gap-2 overflow-hidden"
            data-testid={`value-dropdown-${id}`}
          >
            {selectedModel && selectedModel?.icon ? (
              <ForwardedIconComponent
                name={selectedModel.icon}
                className="h-4 w-4 flex-shrink-0"
              />
            ) : null}
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
                  {selectedModel?.name || placeholder}
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
      {helperText && (
        <span className="pt-2 text-xs text-muted-foreground">
          {convertStringToHTML(helperText)}
        </span>
      )}
    </div>
  );

  // Render API key input and send button when a model is selected
  const renderApiKeyInput = () => {
    if (!selectedModel) return null;

    return (
      <div className="flex flex-col gap-3">
        {getCustomParameterTitle({
          title: `${selectedProvider || "Provider"} API Key`,
          nodeId: id,
          isFlexView: false,
          required: true,
        })}
        <InputGlobalComponent
          id={`${id}-api-key`}
          display_name={`${selectedProvider || "Provider"} API Key`}
          value={""}
          disabled={false}
          editNode={false}
          handleOnNewValue={({ value }: any) => handleApiKeyChange(value)}
          password={true}
          load_from_db={false}
          placeholder="Enter model API key"
        />
        <Button
          onClick={handleSendApiKey}
          size="sm"
          className="whitespace-nowrap"
          data-testid="enable-provider-button"
        >
          {`Enable ${selectedProvider || "Provider"}`}
        </Button>
      </div>
    );
  };

  // Render the model options
  const renderModelOptions = () => (
    <>
      <CommandList className="max-h-[300px]">
        {groupedOptions.map(([category, categoryOptions]) => {
          const visibleOptions = categoryOptions;

          if (visibleOptions.length === 0) return null;

          return (
            <CommandGroup
              className="p-0 overflow-y-auto"
              key={`${category}`}
            >
              <div className="text-xs font-semibold my-2 ml-4 text-muted-foreground flex items-center">
                {category}
                <div className="ml-2 text-xs text-accent-emerald-foreground">
                  Enabled
                </div>
              </div>
              {visibleOptions.map((option) => {
                // Validate option before rendering
                if (!option || !option.name) {
                  return null;
                }
                return (
                  <CommandItem
                    value={option.name}
                    onSelect={(currentValue) => {
                      handleModelSelect(currentValue);
                      setOpen(false);
                    }}
                    className="w-full items-center rounded-none"
                    data-testid={`${option.name}-option`}
                  >
                    <div className="flex w-full items-center gap-2">
                      <ForwardedIconComponent
                        name={option.icon || "Bot"}
                        className="h-4 w-4 shrink-0 text-primary ml-2"
                      />
                      <div className="truncate text-[13px]">{option.name}</div>
                      <div className="pl-2 ml-auto">
                        <ForwardedIconComponent
                          name="Check"
                          className={cn(
                            "h-4 w-4 shrink-0 text-primary",
                            selectedModel?.name === option.name
                              ? "opacity-100"
                              : "opacity-0",
                          )}
                        />
                      </div>
                    </div>
                  </CommandItem>
                );
              })}
              {category !== groupedOptions[groupedOptions.length - 1][0] &&
                visibleOptions.length > 0 && <CommandSeparator />}
            </CommandGroup>
          );
        })}
      </CommandList>
      <div className="sticky bottom-0 border-t bg-background">
        <CommandItem className="flex cursor-pointer items-center justify-start gap-2 truncate rounded-b-md py-3 text-xs text-muted-foreground">
          <Button
            className="w-full"
            unstyled
            onClick={() => {
              window.open("/settings/model-providers", "_blank");
            }}
            data-testid="manage-model-providers"
          >
            <div className="flex items-center gap-2 pl-1 text-muted-foreground">
              Manage Model Providers
              <ForwardedIconComponent
                name="arrow-up-right"
                className={cn("ml-auto w-4 h-4 text-muted-foreground")}
              />
            </div>
          </Button>
        </CommandItem>
      </div>
    </>
  );

  // Loading state
  if ((options.length === 0 && isLoading) || (!options && isLoading)) {
    return (
      <div className="w-full">
        <Button
          className="dropdown-component-false-outline w-full justify-between py-2 font-normal"
          variant="primary"
          size="xs"
          disabled
        >
          <LoadingTextComponent text="Loading models" />
        </Button>
      </div>
    );
  }

  // Error state - no options available
  if (!options || (options.length === 0 && !isLoading)) {
    return (
      <div className="w-full">
        <Button
          className="dropdown-component-false-outline w-full justify-between py-2 font-normal"
          variant="primary"
          size="xs"
          disabled
        >
          <span className="text-muted-foreground text-sm">
            No models available
          </span>
        </Button>
      </div>
    );
  }

  // Main render
  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        {isLoading ? (
          <Button
            className="dropdown-component-false-outline w-full justify-between py-2 font-normal"
            variant="primary"
            size="xs"
          >
            <LoadingTextComponent text="Loading options" />
          </Button>
        ) : (
          <div className="w-full truncate">{renderTriggerButton()}</div>
        )}
        <PopoverContentWithoutPortal
          side="bottom"
          avoidCollisions={false}
          className="noflow nowheel nopan nodelete nodrag p-0"
          style={{ minWidth: refButton?.current?.clientWidth ?? "200px" }}
        >
          <Command className="flex flex-col">
            {options?.length > 0 && (
              <div className="flex items-center border-b px-2.5">
                <ForwardedIconComponent
                  name="search"
                  className="mr-2 h-4 w-4 shrink-0 opacity-50"
                />
                <input
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Search models..."
                  className="flex h-9 w-full rounded-md bg-transparent py-3 text-[13px] outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
                  autoComplete="off"
                  data-testid="model_search_input"
                />
              </div>
            )}
            {renderModelOptions()}
          </Command>
        </PopoverContentWithoutPortal>
      </Popover>
      {renderApiKeyInput()}
    </>
  );
}
