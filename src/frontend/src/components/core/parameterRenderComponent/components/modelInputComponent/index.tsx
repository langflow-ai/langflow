import Fuse from "fuse.js";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { RECEIVING_INPUT_VALUE } from "@/constants/constants";
import { PROVIDER_VARIABLE_MAPPING } from "@/constants/providerConstants";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import { useGetDefaultModel } from "@/controllers/API/queries/models/use-get-default-model";
import ApiKeyModal from "@/modals/apiKeyModal";
import useAlertStore from "@/stores/alertStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { convertStringToHTML } from "@/utils/stringManipulation";
import { cn } from "@/utils/utils";
import { default as ForwardedIconComponent } from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import {
  Command,
  CommandGroup,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "../../../../ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../../../../ui/popover";
import type { BaseInputProps } from "../../types";

export type ModelInputComponentType = {
  options?: {
    id?: string;
    name: string;
    icon: string;
    provider: string;
    metadata?: any;
  }[];
  placeholder?: string;
  providers?: string[];
};

export type SelectedModel = {
  id?: string;
  name: string;
  icon: string;
  provider: string;
  metadata?: any;
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
  hasRefreshButton,
  nodeId,
  nodeClass,
  handleNodeClass,
}: BaseInputProps<any> & ModelInputComponentType): JSX.Element {
  // Initialize state and refs
  const [open, setOpen] = useState(false);
  const [openApiKeyDialog, setOpenApiKeyDialog] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [refreshOptions, setRefreshOptions] = useState(false);
  const refButton = useRef<HTMLButtonElement>(null);
  const { setErrorData } = useAlertStore();

  // API hooks
  const postTemplateValue = usePostTemplateValue({
    parameterId: "model",
    nodeId: nodeId,
    node: nodeClass,
  });

  const [selectedProvider, setSelectedProvider] = useState<string | null>(
    () => {
      if (value && Array.isArray(value) && value.length > 0) {
        return value[0].provider || null;
      }
      return null;
    },
  );
  const [selectedModel, setSelectedModel] = useState<SelectedModel | null>(
    () => {
      if (value && Array.isArray(value) && value.length > 0) {
        return value[0];
      }
      return null;
    },
  );

  useGetGlobalVariables();

  const globalVariablesEntries = useGlobalVariablesStore(
    (state) => state.globalVariablesEntries,
  );

  // Get default model
  const { data: defaultModelData } = useGetDefaultModel({ model_type: "language" });

  // Initialize utilities and memoized values
  const filteredOptions = useMemo(() => {
    try {
      if (!options || options.length === 0) return [];
      if (!searchTerm.trim()) return options;

      const fuse = new Fuse(options, {
        keys: ["name", "provider"],
        threshold: 0.3,
      });
      return fuse.search(searchTerm).map((result) => result.item);
    } catch (error) {
      console.warn("Error filtering options:", error);
      return options || [];
    }
  }, [options, searchTerm]);

  const groupedOptions = useMemo(() => {
    const groups: Record<string, typeof options> = {};

    filteredOptions.forEach((option) => {
      const provider = option.provider || "Other";
      if (!groups[provider]) {
        groups[provider] = [];
      }
      groups[provider].push(option);
    });

    const sortedGroups: [string, typeof options][] = Object.entries(groups);

    // Sort providers: enabled first, then by preference, then alphabetically
    sortedGroups.sort(([a], [b]) => {
      const aEnabled = globalVariablesEntries?.includes(
        PROVIDER_VARIABLE_MAPPING[a] || "",
      );
      const bEnabled = globalVariablesEntries?.includes(
        PROVIDER_VARIABLE_MAPPING[b] || "",
      );

      // Enabled providers come first
      if (aEnabled && !bEnabled) return -1;
      if (!aEnabled && bEnabled) return 1;

      // If both enabled or both disabled, use provider preference if available
      if (providers?.length) {
        const aIndex = providers.indexOf(a);
        const bIndex = providers.indexOf(b);

        if (aIndex !== -1 && bIndex !== -1) {
          return aIndex - bIndex;
        } else if (aIndex !== -1) {
          return -1;
        } else if (bIndex !== -1) {
          return 1;
        }
      }

      // Otherwise, sort alphabetically
      return a.localeCompare(b);
    });

    return sortedGroups;
  }, [filteredOptions, providers, options, globalVariablesEntries]);

  const isProviderConfigured = useMemo(() => {
    if (!selectedProvider || !globalVariablesEntries) return false;
    const variableName = PROVIDER_VARIABLE_MAPPING[selectedProvider];
    return variableName ? globalVariablesEntries.includes(variableName) : false;
  }, [selectedProvider, globalVariablesEntries]);

  // Utility functions
  const handleModelSelect = useCallback(
    (modelName: string) => {
      try {
        const selectedOption = options.find(
          (option) => option.name === modelName,
        );

        if (!selectedOption) {
          setErrorData({ title: "Model not found" });
          return;
        }

        const newValue = [
          {
            ...(selectedOption.id && { id: selectedOption.id }),
            name: selectedOption.name,
            icon: selectedOption.icon || "Bot",
            provider: selectedOption.provider || "Unknown",
            metadata: selectedOption.metadata || {},
          },
        ];

        handleOnNewValue({ value: newValue });
        setSelectedProvider(selectedOption.provider || null);
        setSelectedModel(selectedOption);
      } catch (error) {
        setErrorData({ title: "Error selecting model" });
      }
    },
    [options, handleOnNewValue, setErrorData],
  );

  const handleSendApiKey = useCallback(() => {
    setOpenApiKeyDialog(true);
  }, []);

  const handleRefreshButtonPress = useCallback(async () => {
    setRefreshOptions(true);
    setOpen(false);

    await mutateTemplate(
      value,
      nodeId!,
      nodeClass!,
      handleNodeClass!,
      postTemplateValue,
      setErrorData,
    )?.then(() => {
      setTimeout(() => {
        setRefreshOptions(false);
      }, 2000);
    });
  }, [
    value,
    nodeId,
    nodeClass,
    handleNodeClass,
    postTemplateValue,
    setErrorData,
  ]);

  // Effects
  useEffect(() => {
    if (value && Array.isArray(value) && value.length > 0) {
      setSelectedModel(value[0]);
      setSelectedProvider(value[0].provider || null);
    } else {
      setSelectedModel(null);
      setSelectedProvider(null);
    }
  }, [value]);

  const renderLoadingButton = () => (
    <Button
      className="dropdown-component-false-outline w-full justify-between py-2 font-normal"
      variant="primary"
      size="xs"
      disabled
    >
      <LoadingTextComponent text="Loading models" />
    </Button>
  );

  const renderSelectedIcon = () => {
    return selectedModel && selectedModel?.icon ? (
      <ForwardedIconComponent
        name={selectedModel.icon}
        className="h-4 w-4 flex-shrink-0"
      />
    ) : null;
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
            "dropdown-component-false-outline py-2",
            "no-focus-visible w-full justify-between font-normal disabled:bg-muted disabled:text-muted-foreground",
          )}
        >
          <span
            className="flex w-full items-center gap-2 overflow-hidden"
            data-testid={`value-dropdown-${id}`}
          >
            {selectedModel && <>{renderSelectedIcon()}</>}
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

  const renderSearchInput = () => (
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
  );

  const renderOptionsList = () => (
    <CommandList className="max-h-[300px] overflow-y-auto">
      {groupedOptions.map(([provider, providerOptions]) => {
        const visibleOptions = providerOptions;

        if (visibleOptions.length === 0) return null;

        // Check if this provider only has disabled provider entries
        const isDisabledProvider = visibleOptions.length === 1 && 
          visibleOptions[0]?.metadata?.is_disabled_provider === true;
        const isProviderEnabled = globalVariablesEntries?.includes(
          PROVIDER_VARIABLE_MAPPING[provider] || "",
        );

        return (
          <CommandGroup className="p-0" key={`${provider}`}>
            <div className="text-xs font-semibold my-2 ml-4 text-muted-foreground flex items-center justify-between pr-4">
              <div className="flex items-center">
                {provider}
                {isProviderEnabled && (
                  <div className="ml-2 text-xs text-accent-emerald-foreground flex items-center gap-1">
                    <ForwardedIconComponent
                      name="CheckCircle2"
                      className="h-3 w-3"
                    />
                    Enabled
                  </div>
                )}
              </div>
              {isDisabledProvider && (
                <Button
                  size="xs"
                  variant="primary"
                  className="h-6 text-xs"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedProvider(provider);
                    setOpenApiKeyDialog(true);
                  }}
                  data-testid={`enable-${provider}-button`}
                >
                  Enable
                </Button>
              )}
            </div>
            {!isDisabledProvider && visibleOptions.map((option) => {
              if (!option || !option.name) {
                return null;
              }
              const isDefaultModel = 
                defaultModelData?.default_model?.model_name === option.name &&
                defaultModelData?.default_model?.provider === option.provider;
              
              return (
                <CommandItem
                  key={option.name}
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
                    {isDefaultModel && (
                      <ForwardedIconComponent
                        name="Star"
                        className="h-3 w-3 text-yellow-500 fill-yellow-500"
                      />
                    )}
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
            {provider !== groupedOptions[groupedOptions.length - 1][0] &&
              visibleOptions.length > 0 && <CommandSeparator />}
          </CommandGroup>
        );
      })}
    </CommandList>
  );

  const renderManageProvidersButton = () => (
    <div className="sticky bottom-0 border-t bg-background">
      {hasRefreshButton && (
        <CommandItem className="flex cursor-pointer items-center justify-start gap-2 truncate py-3 text-xs font-semibold text-muted-foreground">
          <Button
            className="w-full"
            unstyled
            data-testid="refresh-model-list"
            onClick={() => {
              handleRefreshButtonPress();
            }}
          >
            <div className="flex items-center gap-2 pl-1">
              <ForwardedIconComponent
                name="RefreshCcw"
                className={cn("refresh-icon h-3 w-3 text-primary")}
              />
              Refresh list
            </div>
          </Button>
        </CommandItem>
      )}
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
  );

  const renderPopoverContent = () => (
    <PopoverContent
      side="bottom"
      avoidCollisions={true}
      className="noflow nowheel nopan nodelete nodrag p-0"
      style={{ minWidth: refButton?.current?.clientWidth ?? "200px" }}
    >
      <Command className="flex flex-col">
        {options?.length > 0 && renderSearchInput()}
        {renderOptionsList()}
        {renderManageProvidersButton()}
      </Command>
    </PopoverContent>
  );

  const renderApiKeyInput = () => {
    if (!selectedModel) return null;

    return (
      <Button
        onClick={handleSendApiKey}
        size="sm"
        className="whitespace-nowrap"
        data-testid="enable-provider-button"
      >
        {`Enable ${selectedProvider || "Provider"}`}
      </Button>
    );
  };

  // Loading state
  if ((options.length === 0 && !options) || !options || refreshOptions) {
    return <div className="w-full">{renderLoadingButton()}</div>;
  }

  // Error state - no options available
  if (!options || options.length === 0) {
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
        <div className="w-full truncate">{renderTriggerButton()}</div>
        {renderPopoverContent()}
      </Popover>
      {!isProviderConfigured && renderApiKeyInput()}
      {openApiKeyDialog && (
        <ApiKeyModal
          open={openApiKeyDialog}
          onClose={() => setOpenApiKeyDialog(false)}
          provider={selectedProvider || "Provider"}
        />
      )}
    </>
  );
}
