import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { useRefreshModelInputs } from "@/hooks/use-refresh-model-inputs";
import ModelProviderModal from "@/modals/modelProviderModal";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType } from "@/types/api";
import type { NodeDataType } from "@/types/flow";
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
import { useModelConnectionLogic } from "./hooks/useModelConnectionLogic";
import type {
  ModelInputComponentType,
  ModelOption,
  SelectedModel,
} from "./types";

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
}: BaseInputProps<SelectedModel[]> &
  ModelInputComponentType): JSX.Element | null {
  const { setErrorData } = useAlertStore();
  const refButton = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [openManageProvidersDialog, setOpenManageProvidersDialog] =
    useState(false);
  const [isRefreshingAfterClose, setIsRefreshingAfterClose] = useState(false);
  const [refreshOptions, setRefreshOptions] = useState(false);

  // Connection mode: local state for reactivity, persisted in node data for reload
  const [isConnectionMode, setIsConnectionMode] = useState(() => {
    if (!nodeId) return false;
    const node = useFlowStore.getState().nodes.find((n) => n.id === nodeId);
    const data = node?.data as { _connectionMode?: boolean } | undefined;
    return data?._connectionMode === true;
  });

  const setConnectionMode = useCallback(
    (enabled: boolean) => {
      setIsConnectionMode(enabled);
      if (!nodeId) return;
      const store = useFlowStore.getState();
      store.setNode(
        nodeId,
        (node) => ({
          ...node,
          data: { ...node.data, _connectionMode: enabled },
        }),
        false,
      );
    },
    [nodeId],
  );

  const { refreshAllModelInputs } = useRefreshModelInputs();

  const postTemplateValue = usePostTemplateValue({
    parameterId: "model",
    nodeId: nodeId || "",
    node: (nodeClass as APIClassType) || null,
  });

  const { handleExternalOptions } = useModelConnectionLogic({
    nodeId: nodeId || "",
    closePopover: () => setOpen(false),
    clearSelection: () => {
      // Only set the _connectionMode flag on the node data.
      // Don't call handleOnNewValue — it triggers a backend round-trip
      // that tries to resolve __default_language_model__ and fails.
      // The credential fields are cleared by useModelConnectionLogic
      // directly in the node template via setNode.
      setConnectionMode(true);
    },
  });

  const modelType =
    nodeClass?.template?.model?.model_type === "language"
      ? "llm"
      : "embeddings";

  const {
    data: providersData = [],
    isLoading: isLoadingProviders,
    isFetching: isFetchingProviders,
  } = useGetModelProviders({});
  const {
    data: enabledModelsData,
    isLoading: isLoadingEnabledModels,
    isFetching: isFetchingEnabledModels,
  } = useGetEnabledModels();

  const isLoading = isLoadingProviders || isLoadingEnabledModels;

  // Groups models by their provider name for sectioned display in dropdown.
  // Filters out models from disabled providers AND disabled models, then
  // augments with any enabled models from `providersData` that weren't in the
  // component's saved `options` (e.g. after importing a flow whose exporter
  // only had a subset of the current user's enabled providers).
  const groupedOptions = useMemo(() => {
    const grouped: Record<string, ModelOption[]> = {};
    const seen = new Set<string>();

    for (const option of options) {
      if (option.metadata?.is_disabled_provider) continue;
      const provider = option.provider || "Unknown";

      // Filter against client-side enabled models data. The user's
      // current enabled list is the single source of truth: a model that
      // isn't explicitly enabled (=== true) is hidden, even if it's the
      // node's saved selection. There is no sticky-default carve-out —
      // a globally-disabled model never appears in the dropdown.
      if (enabledModelsData?.enabled_models) {
        const providerModels = enabledModelsData.enabled_models[provider];
        if (providerModels && providerModels[option.name] !== true) {
          continue;
        }
      }

      if (!grouped[provider]) {
        grouped[provider] = [];
      }
      grouped[provider].push(option);
      seen.add(`${provider}::${option.name}`);
    }

    // Augment with models the user has enabled that were not in the saved
    // `options` (the saved list reflects only what the exporter had available).
    // This ensures importing a flow shows the importing user's full enabled
    // list rather than the intersection of the two sets.
    //
    // Cross-type guard: `providersData` from ``GET /api/v1/models`` is NOT
    // filtered by ``model_type`` (the hook doesn't pass one), and the merged
    // ``enabled_models`` map treats llm + embeddings as a single flat
    // provider→name→bool record.  Without this check, text-embedding models
    // leak into the language-model dropdown (and vice versa) whenever their
    // provider has both kinds enabled.  Filter by each model's own
    // ``model_type`` metadata so the component only shows its own type.
    if (enabledModelsData?.enabled_models && providersData) {
      for (const providerInfo of providersData) {
        const providerName = providerInfo.provider;
        const providerModels = enabledModelsData.enabled_models[providerName];
        if (!providerModels) continue;

        for (const model of providerInfo.models ?? []) {
          const modelName = model.model_name;
          if (providerModels[modelName] !== true) continue;

          // Only include models whose declared type matches this component.
          // Older metadata without ``model_type`` is allowed through so we
          // don't regress providers that haven't adopted the tag yet.
          const modelMetadataType = (
            model.metadata as Record<string, unknown> | undefined
          )?.model_type;
          if (
            typeof modelMetadataType === "string" &&
            modelMetadataType !== modelType
          ) {
            continue;
          }

          const key = `${providerName}::${modelName}`;
          if (seen.has(key)) continue;
          seen.add(key);

          if (!grouped[providerName]) {
            grouped[providerName] = [];
          }
          grouped[providerName].push({
            name: modelName,
            icon: providerInfo.icon || "Bot",
            provider: providerName,
            metadata: (model.metadata ?? {}) as Record<string, unknown>,
          });
        }
      }
    }

    return grouped;
  }, [options, enabledModelsData, providersData, modelType]);

  // True iff at least one model of this component's type is enabled across
  // any provider. Drives the Setup Provider CTA — a provider that is
  // configured but has all its models disabled is treated the same as a
  // provider that hasn't been configured yet.
  const hasEnabledProviders = useMemo(
    () => Object.values(groupedOptions).some((models) => models.length > 0),
    [groupedOptions],
  );

  // Flattened array of all enabled options for efficient lookups by name
  const flatOptions = useMemo(
    () => Object.values(groupedOptions).flat(),
    [groupedOptions],
  );

  // Derive the currently selected model from the value prop. If the saved
  // value isn't in the current ``flatOptions`` (typically because the
  // model was globally disabled), it's treated as if no model is selected
  // — the trigger renders the first available option as the visual
  // selection and the effect below realigns the stored ``value`` to match.
  const selectedModel = useMemo(() => {
    if (isConnectionMode) {
      return {
        name:
          externalOptions?.fields?.data?.node?.display_name ||
          "Connect other models",
        icon: externalOptions?.fields?.data?.node?.icon || "CornerDownLeft",
        provider: "",
      } as SelectedModel;
    }

    const currentName = value?.[0]?.name;
    if (currentName) {
      const match = flatOptions.find((option) => option.name === currentName);
      if (match) return match;
    }

    return flatOptions.length > 0 ? flatOptions[0] : null;
  }, [value, flatOptions, isConnectionMode, externalOptions]);

  // Auto-select the first available option whenever the stored ``value``
  // doesn't point at a currently-available model — including the case
  // where the previously-selected model was globally disabled. Without
  // this, the trigger would visually show one model while the node's
  // saved value pointed at a different (or removed) one.
  useEffect(() => {
    if (flatOptions.length === 0 || isConnectionMode) return;

    const savedName = value?.[0]?.name;
    if (savedName && flatOptions.some((o) => o.name === savedName)) return;

    const firstOption = flatOptions[0];
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
  }, [flatOptions, value, handleOnNewValue, isConnectionMode]);

  /**
   * Handles model selection from the dropdown.
   */
  const handleModelSelect = useCallback(
    (modelName: string) => {
      setConnectionMode(false);
      // Clear the _connection_mode flag from the model field template
      // so the backend resumes normal update_build_config behavior.
      if (nodeId) {
        const store = useFlowStore.getState();
        const node = store.getNode(nodeId);
        const nodeData = node?.data as NodeDataType | undefined;
        if (nodeData?.node?.template?.model?._connection_mode) {
          store.setNode(
            nodeId,
            (prev) => ({
              ...prev,
              data: {
                ...prev.data,
                _connectionMode: false,
                node: {
                  ...(prev.data as NodeDataType).node,
                  template: {
                    ...(prev.data as NodeDataType).node.template,
                    model: {
                      ...(prev.data as NodeDataType).node.template.model,
                      _connection_mode: false,
                    },
                  },
                },
              } as NodeDataType,
            }),
            false,
          );
        }
      }
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

  const handleRefreshButtonPress = useCallback(async () => {
    setOpen(false);
    setRefreshOptions(true);
    try {
      await refreshAllModelInputs({ silent: true });
    } catch {
      // refreshAllModelInputs handles its own error notifications via alertStore
    } finally {
      setRefreshOptions(false);
    }
  }, [refreshAllModelInputs]);

  const handleManageProvidersDialogClose = useCallback(() => {
    setOpenManageProvidersDialog(false);
    setIsRefreshingAfterClose(true);
  }, []);

  // Clear the refreshing indicator only after BOTH the providers and the
  // enabled-models queries have completed a full refetch cycle (isFetching:
  // false → true → false). Watching only ``isFetchingProviders`` clears the
  // loading state too early when the enabled-models refetch is slower,
  // letting ``groupedOptions`` render against a stale ``enabledModelsData``
  // cache — disabled models would briefly leak back into the dropdown after
  // the user closes the provider modal. We track whether we've seen the
  // fetch start so we don't clear prematurely before the invalidation has
  // even been triggered by refreshAllModelInputs.
  const hasSeenFetchStartRef = useRef(false);
  useEffect(() => {
    if (!isRefreshingAfterClose) {
      hasSeenFetchStartRef.current = false;
      return;
    }
    if (isFetchingProviders || isFetchingEnabledModels) {
      hasSeenFetchStartRef.current = true;
    } else if (hasSeenFetchStartRef.current) {
      setIsRefreshingAfterClose(false);
    }
  }, [isRefreshingAfterClose, isFetchingProviders, isFetchingEnabledModels]);

  // Safety timeout: clear loading even if no refetch cycle is detected
  // (e.g. no model nodes on canvas, or the refresh was a no-op)
  useEffect(() => {
    if (!isRefreshingAfterClose) return;
    const timeout = setTimeout(() => setIsRefreshingAfterClose(false), 5000);
    return () => clearTimeout(timeout);
  }, [isRefreshingAfterClose]);

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
          {renderFooterButton(
            "Refresh List",
            "RotateCw",
            handleRefreshButtonPress,
            "refresh-model-list",
          )}
          {renderManageProvidersButton()}
          {externalOptions?.fields?.data?.node && (
            <div className="border-t bg-background">
              {renderFooterButton(
                externalOptions.fields.data.node.display_name ||
                  "Connect other models",
                externalOptions.fields.data.node.icon || "CornerDownLeft",
                () => handleExternalOptions("connect_other_models"),
                "connect-other-models",
              )}
            </div>
          )}
        </Command>
      </PopoverContentInput>
    );
  };

  if (!showParameter) {
    return null;
  }

  // Show loading indicator only when actually loading data, not when options are genuinely empty
  if (isLoading || isRefreshingAfterClose || refreshOptions) {
    return <div className="w-full">{renderLoadingButton()}</div>;
  }

  // Main render
  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <ModelTrigger
          open={open}
          disabled={disabled}
          options={flatOptions}
          selectedModel={selectedModel}
          placeholder={placeholder}
          hasEnabledProviders={hasEnabledProviders}
          onOpenManageProviders={() => setOpenManageProvidersDialog(true)}
          id={id}
          refButton={refButton}
          showEmptyState={showEmptyState}
        />
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
