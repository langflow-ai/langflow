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

  // Ref to track if we've already processed the empty options state
  // prevents infinite loop when no models are available
  const hasProcessedEmptyRef = useRef(false);

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
  const { data: enabledModelsData, isLoading: isLoadingEnabledModels } =
    useGetEnabledModels();

  const isLoading = isLoadingProviders || isLoadingEnabledModels;

  const hasEnabledProviders = useMemo(() => {
    return providersData?.some(
      (provider) => provider.is_enabled || provider.is_configured,
    );
  }, [providersData]);

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

      // Backend sticky-default: options tagged with `not_enabled_locally` are
      // the user's saved selection injected into the options list by the
      // unified-models build_config helper even though they aren't in the
      // enabled list. They must always pass the client-side filter so the
      // selection stays visible and selectable in the dropdown.
      const isStickyNotEnabled = option.metadata?.not_enabled_locally === true;

      // Filter against client-side enabled models data. This is the source of
      // truth for what the current user has enabled — stale `options` saved in
      // an imported flow may include models from providers the current user
      // hasn't enabled (e.g. WatsonX). When the provider is tracked in
      // enabled_models, the model must be explicitly enabled (=== true); a
      // `false` or missing entry means the model should be hidden.
      if (!isStickyNotEnabled && enabledModelsData?.enabled_models) {
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

    // Zero-provider import fallback: if the user has no providers configured
    // locally but an imported flow carries a saved model, inject that saved
    // selection as the only dropdown entry so the trigger renders the model
    // (with the Configure wrench) instead of the "Setup Provider" button.
    // Without this, ``flatOptions`` would be empty and ``ModelTrigger`` would
    // swap the dropdown for the setup CTA, visually losing the imported
    // selection.
    const hasAnyGrouped = Object.keys(grouped).length > 0;
    const savedValue = value?.[0];
    if (!hasAnyGrouped && savedValue?.name) {
      const providerName = savedValue.provider || "Unknown";
      grouped[providerName] = [
        {
          ...(savedValue.id && { id: savedValue.id }),
          name: savedValue.name,
          icon: savedValue.icon || "Bot",
          provider: providerName,
          metadata: {
            ...(savedValue.metadata ?? {}),
            not_enabled_locally: true,
          },
        } as ModelOption,
      ];
    }

    return grouped;
  }, [options, enabledModelsData, providersData, modelType, value]);

  // Flattened array of all enabled options for efficient lookups by name
  const flatOptions = useMemo(
    () => Object.values(groupedOptions).flat(),
    [groupedOptions],
  );

  // Derive the currently selected model from the value prop
  const selectedModel = useMemo(() => {
    // If we're in connection mode, show the connection option as selected
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
    if (!currentName) {
      // Logic to auto-select the first model if none is selected
      // We only do this check if we have options available
      if (flatOptions.length > 0 && !hasProcessedEmptyRef.current) {
        // If we haven't processed empty state yet, we render the first one
        return flatOptions[0];
      }
      return null;
    }

    const match = flatOptions.find((option) => option.name === currentName);
    if (match) return match;

    // Saved name isn't in the filtered options list — typically because the
    // flow was imported via drag-drop (no backend sticky-default round-trip)
    // or because an outdated component was upgraded and the fresh template
    // lacks the sticky-default metadata. Preserve the saved selection in the
    // trigger so it doesn't visually "snap" to the user's first enabled
    // model. The wrench affordance in the dropdown handles configuration.
    const saved = value?.[0];
    if (saved) {
      return {
        ...(saved.id && { id: saved.id }),
        name: saved.name,
        icon: saved.icon || "Bot",
        provider: saved.provider || "Unknown",
        metadata: {
          ...(saved.metadata ?? {}),
          not_enabled_locally: true,
        },
      } as SelectedModel;
    }

    return flatOptions.length > 0 ? flatOptions[0] : null;
  }, [value, flatOptions, isConnectionMode, externalOptions]);

  useEffect(() => {
    if (flatOptions.length === 0 || isConnectionMode) return;
    if (hasProcessedEmptyRef.current) return;

    const isEmpty = !value || value.length === 0;
    // Sticky-default: if the component has a saved value, keep it as-is. The
    // backend injects any selection that isn't in the user's enabled list
    // back into `options` tagged with `not_enabled_locally`, so the saved
    // value remains visible and runnable. Only auto-select the first option
    // when there's no saved value at all.
    if (!isEmpty) return;

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

  // Clear the refreshing indicator after the providers query completes a full
  // refetch cycle (isFetchingProviders: false → true → false). We track whether
  // we've seen the fetch start so we don't clear prematurely before the
  // invalidation has even been triggered by refreshAllModelInputs.
  const hasSeenFetchStartRef = useRef(false);
  useEffect(() => {
    if (!isRefreshingAfterClose) {
      hasSeenFetchStartRef.current = false;
      return;
    }
    if (isFetchingProviders) {
      hasSeenFetchStartRef.current = true;
    } else if (hasSeenFetchStartRef.current) {
      setIsRefreshingAfterClose(false);
    }
  }, [isRefreshingAfterClose, isFetchingProviders]);

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

  // Show a small "Configure" wrench next to the trigger when the currently
  // selected model was injected by the backend as a sticky default — i.e.
  // the user's saved selection isn't in their current enabled_models list.
  // Clicking it jumps straight to the provider manager so the user can
  // enable the provider without losing their selection.
  const showConfigureAffordance =
    selectedModel?.metadata?.not_enabled_locally === true;

  // Main render
  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <div className="flex w-full items-center gap-2">
          <div className="min-w-0 flex-1 truncate">
            <ModelTrigger
              open={open}
              disabled={disabled}
              options={flatOptions}
              selectedModel={selectedModel}
              placeholder={placeholder}
              hasEnabledProviders={hasEnabledProviders ?? false}
              onOpenManageProviders={() => setOpenManageProvidersDialog(true)}
              id={id}
              refButton={refButton}
              showEmptyState={showEmptyState}
            />
          </div>
          {showConfigureAffordance && (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                setOpenManageProvidersDialog(true);
              }}
              data-testid={`${id}-configure`}
              aria-label="Configure this model's provider"
              title="This model isn't enabled for your user. Click to configure its provider."
              className="shrink-0 inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-primary"
            >
              <ForwardedIconComponent name="Wrench" className="h-3.5 w-3.5" />
            </button>
          )}
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
