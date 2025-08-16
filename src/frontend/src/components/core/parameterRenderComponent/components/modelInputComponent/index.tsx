import { PopoverAnchor } from "@radix-ui/react-popover";
import Fuse from "fuse.js";
import React, { type ChangeEvent, useMemo, useRef, useState } from "react";
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
  PopoverContent,
  PopoverContentWithoutPortal,
  PopoverTrigger,
} from "@/components/ui/popover";
import { RECEIVING_INPUT_VALUE } from "@/constants/constants";
import useAlertStore from "@/stores/alertStore";
import { convertStringToHTML } from "@/utils/stringManipulation";
import { cn } from "@/utils/utils";
import ForwardedIconComponent from "../../../../common/genericIconComponent";
import type { BaseInputProps } from "../../types";
import InputGlobalComponent from "../inputGlobalComponent";

export type ModelInputComponentType = {
  model_type: "language" | "embedding";
  options: { name: string; icon: string; category: string }[];
  placeholder: string;
  temperature?: number;
  max_tokens?: number;
  limit?: number;
  search_category?: string[];
};

export type ModelInputProps = BaseInputProps<any> &
  ModelInputComponentType & {
    children?: React.ReactNode;
  };

export default function ModelInputComponent({
  id,
  value,
  disabled,
  editNode = false,
  handleOnNewValue,
  model_type = "language",
  options = [],
  placeholder = "Select a Model",
  search_category = ["OpenAI", "Anthropic"],
  isToolMode = false,
  hasRefreshButton = false,
  helperText,
  children,
}: ModelInputProps): JSX.Element {
  // Initialize state and refs
  const [open, setOpen] = useState(children ? true : false);
  const [showProviderModal, setShowProviderModal] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [currentSelection, setCurrentSelection] = useState<string | null>(null);
  const refButton = useRef<HTMLButtonElement>(null);
  const [customValue, setCustomValue] = useState("");
  const [filteredOptions, setFilteredOptions] = useState(() => options);
  const [isLoading, setIsLoading] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const [enableProvider, setEnableProvider] = useState(false);

  const fuse = new Fuse(options, { keys: ["name", "category"] });
  const PopoverContentDropdown =
    children || editNode ? PopoverContent : PopoverContentWithoutPortal;

  const groupedOptions = useMemo(() => {
    const groups: Record<string, typeof options> = {};

    options.forEach((option) => {
      const category = option.category || "Other";
      if (!groups[category]) {
        groups[category] = [];
      }
      groups[category].push(option);
    });

    // Sort by provider priority
    const sortedGroups: [string, typeof options][] = Object.entries(groups);

    // Move specified categories to top
    if (search_category?.length) {
      sortedGroups.sort(([a], [b]) => {
        const aIndex = search_category.indexOf(a);
        const bIndex = search_category.indexOf(b);

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
  }, [options, search_category]);

  const handleModelSelect = (modelOption: string) => {
    const selectedOption = options.find((opt) => opt.name === modelOption);
    setCurrentSelection(
      selectedOption?.name.includes(":")
        ? selectedOption?.name.split(":")[1]
        : selectedOption?.name,
    );
    if (selectedOption) {
      handleOnNewValue({ value: [selectedOption] });
    } else {
      handleOnNewValue({ value: [{ name: modelOption, icon: "" }] });
    }
  };

  const handleApiKeyChange = (newApiKey: string) => {
    setApiKey(newApiKey);
  };

  const handleSendApiKey = () => {
    // TODO: Wire up API call to save/send key to provider backend
    // Keeping as a no-op for now per request
    // eslint-disable-next-line no-console
    console.log("Send API key clicked", { provider: selectedProvider, apiKey });
    setSuccessData({ title: "Model API key saved successfully" });
  };

  const searchModelsByTerm = async (event: ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setCustomValue(value);

    if (!value) {
      setFilteredOptions(options);
      return;
    }

    const searchValues = fuse.search(value);
    const filtered = searchValues.map((search) => search.item);

    setFilteredOptions(filtered);
  };

  const renderLoadingButton = () => (
    <Button
      className="dropdown-component-false-outline w-full justify-between py-2 font-normal"
      variant="primary"
      size="xs"
    >
      <LoadingTextComponent text="Loading options" />
    </Button>
  );

  const renderSelectedIcon = () => {
    if (Array.isArray(value) && value.length > 0 && value[0]?.name) {
      const selectedOption = options.find((opt) => opt.name === value[0]?.name);
      return selectedOption?.icon ? (
        <ForwardedIconComponent
          name={selectedOption.icon}
          className="h-4 w-4 flex-shrink-0"
        />
      ) : null;
    }
    return null;
  };

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
          className={cn(
            editNode
              ? "dropdown-component-outline input-edit-node"
              : "dropdown-component-false-outline py-2",
            "no-focus-visible w-full justify-between font-normal disabled:bg-muted disabled:text-muted-foreground",
          )}
        >
          <span
            className="flex w-full items-center gap-2 overflow-hidden"
            data-testid={`value-dropdown-${id}`}
          >
            {currentSelection && renderSelectedIcon()}
            <span className="truncate">
              {disabled ? (
                RECEIVING_INPUT_VALUE
              ) : (
                <>{currentSelection || placeholder || "Select a Model"}</>
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
    if (!currentSelection) return null;

    return (
      <div className="flex flex-col gap-4 mt-2">
        <InputGlobalComponent
          id={`${id}-api-key`}
          display_name={`${selectedProvider || "Provider"} API Key`}
          value={apiKey}
          disabled={false}
          editNode={false}
          // The component expects handleOnNewValue signature; we only need value
          handleOnNewValue={({ value }: any) => handleApiKeyChange(value)}
          password={true}
          load_from_db={false}
          placeholder="Enter API key"
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

  // Render the search input
  const renderSearchInput = () => (
    <div className="flex items-center border-b px-2.5">
      <ForwardedIconComponent
        name="search"
        className="mr-2 h-4 w-4 shrink-0 opacity-50"
      />
      <input
        onChange={searchModelsByTerm}
        placeholder="Search models..."
        className="flex h-9 w-full rounded-md bg-transparent py-3 text-[13px] outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
        autoComplete="off"
        data-testid="model_search_input"
      />
    </div>
  );

  // Render the model options
  const renderModelOptions = () => (
    <>
      <CommandList className="max-h-[300px]">
        {groupedOptions.map(([category, categoryOptions]) => {
          const visibleOptions = customValue
            ? categoryOptions.filter((option) =>
                filteredOptions.some(
                  (filtered) => filtered.name === option.name,
                ),
              )
            : categoryOptions;

          if (visibleOptions.length === 0) return null;

          return (
            <CommandGroup
              defaultChecked={false}
              className="p-0 overflow-y-auto"
              key={category}
            >
              <div className="text-xs font-semibold my-2 ml-4 text-muted-foreground flex items-center">
                {category}
                {selectedProvider === category && (
                  <div className="ml-2 text-xs text-accent-emerald-foreground">
                    Enabled
                  </div>
                )}
              </div>
              {visibleOptions.map((option) => (
                <div>
                  <CommandItem
                    value={option.name}
                    onSelect={(currentValue) => {
                      setSelectedProvider(
                        selectedProvider === option.name
                          ? null
                          : option.name.includes(":")
                            ? option.name.split(":")[0]
                            : option.name,
                      );

                      handleModelSelect(currentValue);
                      setOpen(false);
                    }}
                    className="w-full items-center rounded-none"
                    data-testid={`${option.name}-option`}
                  >
                    <div className="flex w-full items-center gap-2">
                      <ForwardedIconComponent
                        name={option.icon || "Unknown"}
                        className="h-4 w-4 shrink-0 text-primary ml-2"
                      />
                      <div className="truncate text-[13px]">
                        {option.name.split(":")[1] || option.name}
                      </div>
                      <div className="pl-2 ml-auto">
                        <ForwardedIconComponent
                          name="Check"
                          className={cn(
                            "h-4 w-4 shrink-0 text-primary",
                            Array.isArray(value) &&
                              value.length > 0 &&
                              value[0]?.name === option.name
                              ? "opacity-100"
                              : "opacity-0",
                          )}
                        />
                      </div>
                    </div>
                  </CommandItem>
                </div>
              ))}
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
              setShowProviderModal(true);
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

  // Render the popover content
  const renderPopoverContent = () => (
    <PopoverContentDropdown
      side="bottom"
      avoidCollisions={!!children}
      className="noflow nowheel nopan nodelete nodrag p-0"
      style={
        children ? {} : { minWidth: refButton?.current?.clientWidth ?? "200px" }
      }
    >
      <Command className="flex flex-col">
        {options?.length > 0 && renderSearchInput()}
        {renderModelOptions()}
      </Command>
    </PopoverContentDropdown>
  );

  // Loading state
  if (options.length === 0 && isLoading) {
    return (
      <div>
        <span className="text-sm italic">Loading...</span>
      </div>
    );
  }

  // Main render
  return (
    <>
      <Popover open={open} onOpenChange={children ? () => {} : setOpen}>
        {children ? (
          <PopoverAnchor>{children}</PopoverAnchor>
        ) : isLoading ? (
          renderLoadingButton()
        ) : (
          <div className="w-full truncate">{renderTriggerButton()}</div>
        )}
        {renderPopoverContent()}
      </Popover>

      {renderApiKeyInput()}
    </>
  );
}
