import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import ModelProviderModal from "@/modals/modelProviderModal";
import useAlertStore from "@/stores/alertStore";
import type { APIClassType } from "@/types/api";
import ForwardedIconComponent from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import { Command } from "../../../../ui/command";
import {
  Popover,
  PopoverContent,
  PopoverContentWithoutPortal,
} from "../../../../ui/popover";
import type { BaseInputProps } from "../../types";
import ModelList from "./components/ModelList";
import ModelTrigger from "./components/ModelTrigger";
import { ModelInputComponentType, ModelOption } from "./types";

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
  showParameter = true,
  editNode,
  inspectionPanel,
  showEmptyState = false,
}: BaseInputProps<any> & ModelInputComponentType): JSX.Element | null {
  const { setErrorData } = useAlertStore();
  const refButton = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [openManageProvidersDialog, setOpenManageProvidersDialog] =
    useState(false);

  // Ref to track if we've already processed the empty options state
  // prevents infinite loop when no models are available
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

  const { data: providersData = [], isLoading: isLoadingProviders } =
    useGetModelProviders({});
  const { data: enabledModelsData, isLoading: isLoadingEnabledModels } =
    useGetEnabledModels();

  const isLoading = isLoadingProviders || isLoadingEnabledModels;

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

  // Derive the currently selected model from the value prop
  const selectedModel = useMemo(() => {
    // If we're in connection mode, we don't have a normal selected model
    if (value === "connect_other_models") {
      return null;
    }

    const currentName = value?.[0]?.name;
    if (!currentName) {
      // Logic to auto-select the first model if none is selected
      // We only do this check if we have options available
      if (flatOptions.length > 0 && !hasProcessedEmptyRef.current) {
        // If we haven't processed empty state yet, we render the first one
        return flatOptions[0];
      }
      return null;
    }

    return (
      flatOptions.find((option) => option.name === currentName) ||
      // Fallback: If the saved name isn't in the list (e.g. disabled), select first available?
      // Or keep displaying the stale one? Original logic selected first available.
      (flatOptions.length > 0 ? flatOptions[0] : null)
    );
  }, [value, flatOptions]);

  useEffect(() => {
    // Only proceed if we have options and haven't selected a value
    if (flatOptions.length > 0 && (!value || value.length === 0)) {
      // Check ref to avoid infinite loops
      if (!hasProcessedEmptyRef.current) {
        const firstOption = flatOptions[0];
        // Construct the new value object
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
        hasProcessedEmptyRef.current = true;
      }
    }
  }, [flatOptions, value, handleOnNewValue]);

  /**
   * Handles model selection from the dropdown.
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
      setOpen(false);
    },
    [flatOptions, handleOnNewValue],
  );

  const handleManageProvidersDialogClose = useCallback(() => {
    setOpenManageProvidersDialog(false);
  }, []);

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

  const renderFooterButton = (
    label: string,
    icon: string,
    onClick: () => void,
    testId?: string,
  ) => (
    <Button
      className="w-full flex cursor-pointer items-center justify-start gap-2 truncate py-2 text-xs text-muted-foreground px-3 hover:bg-accent group"
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

  const renderManageProvidersButton = () => (
    <div className="bottom-0 bg-background">
      {renderFooterButton(
        "Manage Model Providers",
        "Settings",
        () => setOpenManageProvidersDialog(true),
        "manage-model-providers",
      )}
    </div>
  );

  const renderPopoverContent = () => {
    const PopoverContentInput =
      editNode || inspectionPanel
        ? PopoverContent
        : PopoverContentWithoutPortal;
    return (
      <PopoverContentInput
        side="bottom"
        avoidCollisions={true}
        className="noflow nowheel nopan nodelete nodrag p-0"
        style={{ minWidth: refButton?.current?.clientWidth ?? "200px" }}
      >
        <Command className="flex flex-col">
          <ModelList
            groupedOptions={groupedOptions}
            selectedModel={selectedModel}
            onSelect={handleModelSelect}
          />
          {renderManageProvidersButton()}
        </Command>
      </PopoverContentInput>
    );
  };

  if (!showParameter) {
    return null;
  }

  // Loading state
  if (!options || options.length === 0) {
    return <div className="w-full">{renderLoadingButton()}</div>;
  }

  // Main render
  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <div className="w-full truncate">
          <ModelTrigger
            open={open}
            disabled={disabled}
            options={options}
            selectedModel={selectedModel}
            placeholder={placeholder}
            hasEnabledProviders={hasEnabledProviders ?? false}
            onOpenManageProviders={() => setOpenManageProvidersDialog(true)}
            id={id}
            refButton={refButton}
          />
        </div>
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
