<<<<<<< HEAD
=======

import Fuse from "fuse.js";

>>>>>>> 166528f555acf5e51ccaeb2e7d4c0401f94ad21e

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { RECEIVING_INPUT_VALUE } from "@/constants/constants";
import { PROVIDER_VARIABLE_MAPPING } from "@/constants/providerConstants";

<<<<<<< HEAD

import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";

=======

import { useGetDefaultModel } from "@/controllers/API/queries/models/use-get-default-model";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import ApiKeyModal from "@/modals/apiKeyModal";

>>>>>>> 166528f555acf5e51ccaeb2e7d4c0401f94ad21e

import ModelProviderModal from "@/modals/modelProviderModal";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { useTypesStore } from "@/stores/typesStore";
import { APIClassType } from "@/types/api";
import { scapedJSONStringfy } from "@/utils/reactflowUtils";
import { convertStringToHTML } from "@/utils/stringManipulation";
import { cn, groupByFamily } from "@/utils/utils";
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
  PopoverContentWithoutPortal,
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
  externalOptions?: any;
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
  placeholder = "Setup Provider",
  helperText,
  hasRefreshButton,
  nodeId,
  nodeClass,
  handleNodeClass,
  externalOptions,
}: BaseInputProps<any> & ModelInputComponentType): JSX.Element {
  // Initialize state and refs
  const [open, setOpen] = useState(false);
  const [openApiKeyDialog, setOpenApiKeyDialog] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [refreshOptions, setRefreshOptions] = useState(false);
  const [openManageProvidersDialog, setOpenManageProvidersDialog] =
    useState(false);
  const refButton = useRef<HTMLButtonElement>(null);
  const { setErrorData } = useAlertStore();
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [initialValueSet, setInitialValueSet] = useState(false);
  const [selectedModel, setSelectedModel] = useState<SelectedModel | null>(
    null,
  );

  // API hooks
  const postTemplateValue = usePostTemplateValue({
    parameterId: "model",
    nodeId: nodeId || "",
    node: (nodeClass as APIClassType) || null,
  });

  const navigate = useCustomNavigate();

  useGetGlobalVariables();

  const globalVariablesEntries = useGlobalVariablesStore(
    (state) => state.globalVariablesEntries,
  );

  const groupedOptions = useMemo(() => {
    const groups: Record<string, typeof options> = {};

    options.forEach((option) => {
      const provider = option.provider || "Other";
      if (!groups[provider]) {
        groups[provider] = [];
      }
      groups[provider].push(option);
    });

    const sortedGroups: [string, typeof options][] = Object.entries(groups);

    // Sort providers:
    // 1. Provider with default model first
    // 2. Enabled providers next
    // 3. Alphabetically after that
    sortedGroups.sort(([a], [b]) => {
      const aEnabled = globalVariablesEntries?.includes(
        PROVIDER_VARIABLE_MAPPING[a] || "",
      );
      const bEnabled = globalVariablesEntries?.includes(
        PROVIDER_VARIABLE_MAPPING[b] || "",
      );

      // Then enabled providers
      if (aEnabled && !bEnabled) return -1;
      if (!aEnabled && bEnabled) return 1;

      // Otherwise, sort alphabetically
      return a.localeCompare(b);
    });

    return sortedGroups;
  }, [options, globalVariablesEntries]);

  const hasEnabledProviders = useMemo(() => {
    if (!globalVariablesEntries) return false;
    return groupedOptions.some(([provider]) =>
      globalVariablesEntries.includes(
        PROVIDER_VARIABLE_MAPPING[provider] || "",
      ),
    );
  }, [groupedOptions, globalVariablesEntries]);

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

  const handleExternalOptions = useCallback(
    async (optionValue: string) => {
      setOpen(false);

      // Clear the current selection UI state
      setSelectedModel(null);
      setSelectedProvider(null);

      // Pass the optionValue ("connect_other_models") as both the field value and to mutateTemplate
      // This way the backend knows we're in connection mode
      handleOnNewValue({ value: optionValue });

      await mutateTemplate(
        optionValue,
        nodeId!,
        nodeClass!,
        handleNodeClass!,
        postTemplateValue,
        setErrorData,
        "model",
        () => {
          // Enable connection mode for connect_other_models AFTER mutation completes
          try {
            if (optionValue === "connect_other_models") {
              const store = useFlowStore.getState();
              const node = store.getNode(nodeId!);
              const templateField = node?.data?.node?.template?.["model"];
              if (!templateField) {
                return;
              }

              const inputTypes: string[] =
                (Array.isArray(templateField.input_types)
                  ? templateField.input_types
                  : []) || [];
              const effectiveInputTypes =
                inputTypes.length > 0 ? inputTypes : ["LanguageModel"];

              const tooltipTitle: string =
                (inputTypes && inputTypes.length > 0
                  ? inputTypes.join("\n")
                  : templateField.type) || "";

              const myId = scapedJSONStringfy({
                inputTypes: effectiveInputTypes,
                type: templateField.type,
                id: nodeId,
                fieldName: "model",
                proxy: templateField.proxy,
              });

              const typesData = useTypesStore.getState().data;
              const grouped = groupByFamily(
                typesData,
                (effectiveInputTypes && effectiveInputTypes.length > 0
                  ? effectiveInputTypes.join("\n")
                  : tooltipTitle) || "",
                true,
                store.nodes,
              );

              // Build a pseudo source so compatible target handles (left side) glow
              const pseudoSourceHandle = scapedJSONStringfy({
                fieldName: "model",
                id: nodeId,
                inputTypes: effectiveInputTypes,
                type: "str",
              });

              const filterObj = {
                source: undefined,
                sourceHandle: undefined,
                target: nodeId,
                targetHandle: pseudoSourceHandle,
                type: "LanguageModel",
                color: "datatype-fuchsia",
              } as any;

              // Show compatible handles glow
              store.setFilterEdge(grouped);
              store.setFilterType(filterObj);
            }
          } catch (error) {
            console.warn("Error setting up connection mode:", error);
          }
        },
      );
    },
    [
      nodeId,
      nodeClass,
      handleNodeClass,
      postTemplateValue,
      setErrorData,
      handleOnNewValue,
    ],
  );

  // Effects
  // Sync selectedModel state with the value prop
  useEffect(() => {
    if (value && Array.isArray(value) && value.length > 0) {
      const currentValue = value[0];

      // Check if the value exists in the available options
      const modelExists = options.some(
        (option) =>
          option.name === currentValue.name &&
          option.provider === currentValue.provider,
      );

      if (modelExists) {
        setSelectedModel({
          id: currentValue.id,
          name: currentValue.name,
          icon: currentValue.icon || "Bot",
          provider: currentValue.provider || "Unknown",
          metadata: currentValue.metadata || {},
        });
        setSelectedProvider(currentValue.provider || null);
      } else {
        // Model doesn't exist in options, clear the selection
        setSelectedModel(null);
        setSelectedProvider(null);
        handleOnNewValue({ value: [] });
      }
    }
  }, [value, options, handleOnNewValue]);

  // Set initial value based on default model or first enabled provider
  useEffect(() => {
    if (initialValueSet || !options || options.length === 0) return;

    // If value is already set, don't override
    if (value && Array.isArray(value) && value.length > 0) {
      setInitialValueSet(true);
      return;
    }

    // Don't auto-select if user is explicitly connecting other models (value is the string "connect_other_models")
    if (value === "connect_other_models") {
      setInitialValueSet(true);
      return;
    }

    let modelToSet: SelectedModel | null = null;

    // If no default model, find the first model in the first enabled provider
    if (!modelToSet && globalVariablesEntries) {
      for (const [provider, providerOptions] of groupedOptions) {
        const isProviderEnabled = globalVariablesEntries.includes(
          PROVIDER_VARIABLE_MAPPING[provider] || "",
        );
        if (isProviderEnabled && providerOptions.length > 0) {
          const firstModel = providerOptions[0];
          if (firstModel && !firstModel.metadata?.is_disabled_provider) {
            modelToSet = firstModel;
            break;
          }
        }
      }
    }

    // Set the model if found
    if (modelToSet) {
      const newValue = [
        {
          ...(modelToSet.id && { id: modelToSet.id }),
          name: modelToSet.name,
          icon: modelToSet.icon || "Bot",
          provider: modelToSet.provider || "Unknown",
          metadata: modelToSet.metadata || {},
        },
      ];
      handleOnNewValue({ value: newValue });
      setSelectedProvider(modelToSet.provider || null);
      setSelectedModel(modelToSet);
    }

    setInitialValueSet(true);
  }, [
    options,
    globalVariablesEntries,
    groupedOptions,
    value,
    handleOnNewValue,
    initialValueSet,
  ]);

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

  const renderTriggerButton = () =>
    !hasEnabledProviders ? (
      <Button
        variant="default"
        size="sm"
        className="w-full"
        onClick={() => setOpenManageProvidersDialog(true)}
      >
        <ForwardedIconComponent name="Brain" className="h-4 w-4" />
        <div className="text-[13px]">{placeholder || "Add Models"}</div>
      </Button>
    ) : (
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

  const renderOptionsList = () => (
    <CommandList className="max-h-[300px] overflow-y-auto">
      {groupedOptions.map(([provider, providerOptions]) => {
        const visibleOptions = providerOptions;

        if (visibleOptions.length === 0) return null;

        // Check if this provider only has disabled provider entries
        const isDisabledProvider =
          visibleOptions.length === 1 &&
          visibleOptions[0]?.metadata?.is_disabled_provider === true;
        const isProviderEnabled = globalVariablesEntries?.includes(
          PROVIDER_VARIABLE_MAPPING[provider] || "",
        );

        // Don't show disabled providers in the dropdown
        if (!isProviderEnabled) return null;

        // Don't show providers that only have disabled provider entries (no actual models)
        if (isDisabledProvider) return null;

        return (
          <CommandGroup className="p-0" key={`${provider}`}>
            <div className="text-xs font-semibold my-2 ml-4 text-muted-foreground flex items-center justify-between pr-4">
              <div className="flex items-center">{provider}</div>
            </div>
            {!isDisabledProvider &&
              visibleOptions.map((option) => {
                if (!option || !option.name) {
                  return null;
                }

                const isReasoning = option.metadata?.reasoning_models?.includes(
                  option.name,
                );

                return (
                  <CommandItem
                    key={option.name}
                    value={option.name}
                    onSelect={(currentValue) => {
                      handleModelSelect(currentValue);
                      setSearchTerm("");
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

                      {/* {isReasoning && (
                        <ForwardedIconComponent
                          name="brain"
                          className="h-4 w-4 shrink-0 text-muted-foreground"
                        />
                      )} */}
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
    <div className="sticky bottom-0 bg-background">
      {/* {hasRefreshButton && (
        <Button
          className="w-full flex cursor-pointer items-center justify-start gap-2 truncate py-3 text-xs text-muted-foreground px-3 hover:bg-accent group"
          unstyled
          data-testid="refresh-model-list"
          onClick={() => {
            handleRefreshButtonPress();
          }}
        >
          <div className="flex items-center gap-2 pl-1 group-hover:text-primary">
            Refresh list
            <ForwardedIconComponent
              name="RefreshCcw"
              className={cn(
                "refresh-icon h-3 w-3 text-primary text-muted-foreground group-hover:text-primary",
              )}
            />
          </div>
        </Button>
      )} */}
      {/* {externalOptions?.fields?.data?.node && (
        <Button
          className="w-full flex cursor-pointer items-center justify-start gap-2 truncate py-3 text-xs text-muted-foreground px-3 hover:bg-accent group"
          unstyled
          data-testid="external-option-button"
          onClick={() => {
            handleExternalOptions(externalOptions.fields.data.node.name || "");
          }}
        >
          <div className="flex items-center gap-2 pl-1 group-hover:text-primary">
            {externalOptions.fields.data.node.display_name}
            {externalOptions.fields.data.node.icon && (
              <ForwardedIconComponent
                name={externalOptions.fields.data.node.icon}
                className={cn(
                  "w-4 h-4 text-muted-foreground group-hover:text-primary",
                )}
              />
            )}
          </div>
        </Button>
      )} */}

      <Button
        className="w-full flex cursor-pointer items-center justify-start gap-2 truncate py-3 text-xs text-muted-foreground px-3 hover:bg-accent group"
        unstyled
        onClick={() => {
          setOpenManageProvidersDialog(true);
        }}
        data-testid="manage-model-providers"
      >
        <div className="flex items-center gap-2 pl-1 group-hover:text-primary">
          Manage Model Providers
          <ForwardedIconComponent
            name="Settings"
            className={cn(
              "w-4 h-4 text-muted-foreground group-hover:text-primary",
            )}
          />
        </div>
      </Button>
    </div>
  );

  const renderPopoverContent = () => (
    <PopoverContentWithoutPortal
      side="bottom"
      avoidCollisions={true}
      className="noflow nowheel nopan nodelete nodrag p-0"
      style={{ minWidth: refButton?.current?.clientWidth ?? "200px" }}
    >
      <Command className="flex flex-col">
        {renderOptionsList()}
        {renderManageProvidersButton()}
      </Command>
    </PopoverContentWithoutPortal>
  );

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

      {openManageProvidersDialog && (
        <ModelProviderModal
          open={openManageProvidersDialog}
          onClose={() => setOpenManageProvidersDialog(false)}
          onModelsUpdated={handleRefreshButtonPress}
        />
      )}
    </>
  );
}
