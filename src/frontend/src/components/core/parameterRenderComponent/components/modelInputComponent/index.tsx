import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { mutateTemplate } from "@/CustomNodes/helpers/mutate-template";
import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { RECEIVING_INPUT_VALUE } from "@/constants/constants";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import ModelProviderModal from "@/modals/modelProviderModal";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useTypesStore } from "@/stores/typesStore";
import type { APIClassType } from "@/types/api";
import { scapedJSONStringfy } from "@/utils/reactflowUtils";
import { cn, groupByFamily } from "@/utils/utils";
import ForwardedIconComponent from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import {
  Command,
  CommandGroup,
  CommandItem,
  CommandList,
} from "../../../../ui/command";
import {
  Popover,
  PopoverContentWithoutPortal,
  PopoverTrigger,
} from "../../../../ui/popover";
import type { BaseInputProps } from "../../types";

/** Represents a single model option in the dropdown */
export interface ModelOption {
  id?: string;
  name: string;
  icon: string;
  provider: string;
  metadata?: Record<string, unknown>;
}

export interface ModelInputComponentType {
  options?: ModelOption[];
  placeholder?: string;
  externalOptions?: any;
}

export type SelectedModel = ModelOption;

export default function ModelInputComponent({
  id,
  value,
  disabled,
  handleOnNewValue,
  options = [],
  placeholder = "Setup Provider",
  nodeId,
  nodeClass,
  handleNodeClass,
  externalOptions,
}: BaseInputProps<any> & ModelInputComponentType): JSX.Element {
  const { setErrorData } = useAlertStore();
  const refButton = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [refreshOptions, setRefreshOptions] = useState(false);
  const [selectedModel, setSelectedModel] = useState<SelectedModel | null>(
    null,
  );
  const [openManageProvidersDialog, setOpenManageProvidersDialog] =
    useState(false);

  // Ref to track if we've already processed the empty options state
  // Prevents infinite loop when no models are available
  const hasProcessedEmptyRef = useRef(false);

  const postTemplateValue = usePostTemplateValue({
    parameterId: "model",
    nodeId: nodeId || "",
    node: (nodeClass as APIClassType) || null,
  });

  const modelType =
    nodeClass?.template?.model?.model_type === "language"
      ? "llm"
      : "embeddings";

  const { data: providersData = [] } = useGetModelProviders({});
  const { data: enabledModelsData } = useGetEnabledModels();

  // Determines if we should show the model selector or the "Setup Provider" button
  const hasEnabledProviders = useMemo(() => {
    return providersData?.some((provider) => provider.is_enabled);
  }, [providersData]);

  // Groups models by their provider name for sectioned display in dropdown.
  // Filters out models from disabled providers AND disabled models.
  const groupedOptions = useMemo(() => {
    const grouped: Record<string, ModelOption[]> = {};
    for (const option of options) {
      if (option.metadata?.is_disabled_provider) continue;
      const provider = option.provider || "Unknown";

      // Filter out disabled models using client-side enabled models data
      // This provides a reliable fallback when backend filtering fails
      if (enabledModelsData?.enabled_models) {
        const providerModels = enabledModelsData.enabled_models[provider];
        if (providerModels && providerModels[option.name] === false) {
          continue; // Skip disabled models
        }
      }

      (grouped[provider] ??= []).push(option);
    }
    return grouped;
  }, [options, enabledModelsData]);

  // Flattened array of all enabled options for efficient lookups by name
  const flatOptions = useMemo(
    () => Object.values(groupedOptions).flat(),
    [groupedOptions],
  );

  // Sync local selectedModel state with the external value prop and available options.
  // Handles three cases: no available models (clear selection), current value exists in options (keep it),
  // or current value is invalid/missing (select first available model).
  useEffect(() => {
    // Skip auto-selection when in connection mode (value is "connect_other_models" string)
    if (value === "connect_other_models") {
      return;
    }

    const availableOptions = flatOptions;
    const currentName = value?.[0]?.name;

    // No available models: clear selection/value
    if (!availableOptions || availableOptions.length === 0) {
      // Only process empty state once to prevent infinite loop
      if (!hasProcessedEmptyRef.current) {
        hasProcessedEmptyRef.current = true;
        // Only call handleOnNewValue if value is not already empty
        if (value && Array.isArray(value) && value.length > 0) {
          handleOnNewValue({ value: [] });
        }
      }
      setSelectedModel(null);
      return;
    }

    // Reset the empty state flag when we have options
    hasProcessedEmptyRef.current = false;

    // If current value exists in refreshed options, keep it
    if (currentName) {
      const existingModel = availableOptions.find(
        (option) => option.name === currentName,
      );
      if (existingModel) {
        setSelectedModel(existingModel);
        return;
      }
    }

    // Otherwise select the first available model
    const firstOption = availableOptions[0];
    const newValue = [
      {
        ...(firstOption.id && { id: firstOption.id }),
        name: firstOption.name,
        icon: firstOption.icon || "Bot",
        provider: firstOption.provider || "Unknown",
        metadata: firstOption.metadata ?? {},
      },
    ];

    handleOnNewValue({ value: newValue });
    setSelectedModel(firstOption);
  }, [flatOptions, value, handleOnNewValue]);

  /**
   * Handles model selection from the dropdown.
   * Constructs a normalized value object and propagates it to the parent.
   * The value is wrapped in an array to match the expected format.
   */
  const handleModelSelect = useCallback(
    (modelName: string) => {
      const selectedOption = flatOptions.find(
        (option) => option.name === modelName,
      );
      if (!selectedOption) return;

      // Build normalized value - only include id if it exists
      const newValue = [
        {
          ...(selectedOption.id && { id: selectedOption.id }),
          name: selectedOption.name,
          icon: selectedOption.icon || "Bot",
          provider: selectedOption.provider || "Unknown",
          metadata: selectedOption.metadata ?? {},
        },
      ];

      handleOnNewValue({ value: newValue });
      setSelectedModel(selectedOption);
    },
    [flatOptions, handleOnNewValue],
  );

  /**
   * Triggers a refresh of available model options from the backend.
   * Shows loading state for 2 seconds to provide visual feedback.
   */
  const handleRefreshButtonPress = useCallback(async () => {
    setRefreshOptions(true);
    setOpen(false);

    // mutateTemplate triggers a backend call to refresh the template options
    await mutateTemplate(
      value,
      nodeId!,
      nodeClass!,
      handleNodeClass!,
      postTemplateValue,
      setErrorData,
    );
    // Brief delay before hiding loading state for better UX
    setTimeout(() => setRefreshOptions(false), 2000);
  }, [
    value,
    nodeId,
    nodeClass,
    handleNodeClass,
    postTemplateValue,
    setErrorData,
  ]);

  const handleManageProvidersDialogClose = useCallback(() => {
    setOpenManageProvidersDialog(false);
    // Note: Don't call handleRefreshButtonPress here - the cleanup effect in
    // ModelProvidersContent triggers refreshAllModelInputs which properly validates
    // model values against available options. Calling both causes a race condition
    // where the debounced mutateTemplate overwrites the validated value.
  }, []);

  const handleExternalOptions = useCallback(
    async (optionValue: string) => {
      setOpen(false);

      // Clear the current selection UI state
      setSelectedModel(null);

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

  // Renders either a "Setup Provider" button (no providers) or the model selector dropdown trigger
  const renderTriggerButton = () =>
    !hasEnabledProviders ? (
      <Button
        variant="default"
        size="sm"
        className="w-full"
        onClick={() => setOpenManageProvidersDialog(true)}
      >
        <ForwardedIconComponent name="Brain" className="h-4 w-4" />
        <div className="text-[13px]">{placeholder || "Setup Provider"}</div>
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

  const footerButtonClass =
    "w-full flex cursor-pointer items-center justify-start gap-2 truncate py-2 text-xs text-muted-foreground px-3 hover:bg-accent group";

  const renderFooterButton = (
    label: string,
    icon: string,
    onClick: () => void,
    testId?: string,
  ) => (
    <Button
      className={footerButtonClass}
      unstyled
      data-testid={testId}
      onClick={onClick}
    >
      <div className="flex items-center gap-2 pl-1 group-hover:text-primary">
        {label}
        <ForwardedIconComponent
          name={icon}
          className="w-4 h-4 text-muted-foreground group-hover:text-primary"
        />
      </div>
    </Button>
  );

  const renderOptionsList = () => (
    <CommandList className="max-h-[300px] overflow-y-auto">
      {Object.entries(groupedOptions).map(([provider, models]) => (
        <CommandGroup className="p-0" key={provider}>
          <div className="text-xs font-semibold my-2 ml-4 text-muted-foreground flex items-center justify-between pr-4">
            <div className="flex items-center">{provider}</div>
          </div>
          {models.map((data) => (
            <CommandItem
              key={data.name}
              value={data.name}
              onSelect={() => {
                handleModelSelect(data.name);
                setOpen(false);
              }}
              className="w-full items-center rounded-none"
              data-testid={`${data.name}-option`}
            >
              <div className="flex w-full items-center gap-2">
                <ForwardedIconComponent
                  name={data.icon || "Bot"}
                  className="h-4 w-4 shrink-0 text-primary ml-2"
                />
                <div className="truncate text-[13px]">{data.name}</div>
                <div className="pl-2 ml-auto">
                  <ForwardedIconComponent
                    name="Check"
                    className={cn(
                      "h-4 w-4 shrink-0 text-primary",
                      selectedModel?.name === data.name
                        ? "opacity-100"
                        : "opacity-0",
                    )}
                  />
                </div>
              </div>
            </CommandItem>
          ))}
        </CommandGroup>
      ))}
    </CommandList>
  );

  const renderManageProvidersButton = () => (
    <div className="bottom-0 bg-background">
      {/* {renderFooterButton(
        "Refresh List",
        "RefreshCw",
        handleRefreshButtonPress,
        "external-option-button",
      )} */}

      {renderFooterButton(
        "Manage Model Providers",
        "Settings",
        () => setOpenManageProvidersDialog(true),
        "manage-model-providers",
      )}

      {externalOptions?.fields?.data?.node &&
        renderFooterButton(
          externalOptions.fields.data.node.display_name,
          externalOptions.fields.data.node.icon || "Box",
          () =>
            handleExternalOptions(externalOptions.fields.data.node.name || ""),
          "external-option-button",
        )}
    </div>
  );

  const renderNoProviders = () => (
    <CommandList className="max-h-[300px] overflow-y-auto">
      <CommandItem
        disabled
        className="w-full px-4 py-2 text-[13px] text-muted-foreground"
      >
        No Models Enabled
      </CommandItem>
    </CommandList>
  );

  const renderPopoverContent = () => (
    <PopoverContentWithoutPortal
      side="bottom"
      avoidCollisions={true}
      className="noflow nowheel nopan nodelete nodrag p-0"
      style={{ minWidth: refButton?.current?.clientWidth ?? "200px" }}
    >
      <Command className="flex flex-col">
        {Object.keys(groupedOptions).length > 0
          ? renderOptionsList()
          : renderNoProviders()}
        {renderManageProvidersButton()}
      </Command>
    </PopoverContentWithoutPortal>
  );

  // Loading state
  if (!options || options.length === 0 || refreshOptions) {
    return <div className="w-full">{renderLoadingButton()}</div>;
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
          onClose={handleManageProvidersDialogClose}
          modelType={modelType || "llm"}
        />
      )}
    </>
  );
}
