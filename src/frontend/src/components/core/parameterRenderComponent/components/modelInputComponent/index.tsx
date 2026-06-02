import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { BUILD_PANEL_COLLISION_PADDING_PX } from "@/constants/constants";
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
import { recoverModelOption } from "./helpers/recover-model-option";
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
  placeholder,
  nodeId,
  nodeClass,
  handleNodeClass,
  externalOptions,
  showParameter = true,
  editNode,
  inspectionPanel,
  showEmptyState = false,
  modelType: modelTypeProp,
}: BaseInputProps<ModelOption[] | undefined> &
  ModelInputComponentType): JSX.Element | null {
  const { t } = useTranslation();
  const resolvedPlaceholder = placeholder ?? t("model.setupProvider");
  const { setErrorData } = useAlertStore();
  const refButton = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [openManageProvidersDialog, setOpenManageProvidersDialog] =
    useState(false);
  const [isRefreshingAfterClose, setIsRefreshingAfterClose] = useState(false);
  const [refreshOptions, setRefreshOptions] = useState(false);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const buildInfo = useFlowStore((state) => state.buildInfo);
  const showingBuildPanel =
    isBuilding || !!buildInfo?.error || !!buildInfo?.success;

  // Connection mode is persisted in node data (for reload + external
  // mutations like the agentic flow_builder). We subscribe to the live
  // store value so updates from outside the component (e.g. when the
  // assistant flips `_connectionMode` after wiring an external model)
  // re-render the dropdown immediately. Falling back to local-only state
  // would freeze the UI on the value captured at mount.
  const isConnectionMode = useFlowStore((state) => {
    if (!nodeId) return false;
    const node = state.nodes.find((n) => n.id === nodeId);
    const data = node?.data as { _connectionMode?: boolean } | undefined;
    return data?._connectionMode === true;
  });

  const setConnectionMode = useCallback(
    (enabled: boolean) => {
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

  const _postTemplateValue = usePostTemplateValue({
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
    modelTypeProp ??
    (nodeClass?.template?.model?.model_type === "language"
      ? "llm"
      : "embeddings");

  // Declarative metadata filters from the backend ModelInput (e.g. Agent
  // declares ``filters={"tool_calling": True}``). The backend already
  // applies this to ``options``, but the augment loop below adds models
  // from ``useGetModelProviders`` (which is *not* filter-aware), so without
  // this re-check the picker re-introduces tool-incompatible models
  // alongside the backend-filtered list. Conservative: when a filter key
  // is set but the candidate's metadata doesn't carry that key at all, the
  // candidate fails the check — we'd rather drop an undeclared model than
  // surface one that crashes at run time.
  const modelFilters = useMemo(() => {
    const raw = (
      nodeClass?.template?.model as
        | { filters?: Record<string, unknown> }
        | undefined
    )?.filters;
    if (!raw || typeof raw !== "object") return undefined;
    const entries = Object.entries(raw).filter(
      ([, v]) => v !== null && v !== undefined,
    );
    if (entries.length === 0) return undefined;
    return Object.fromEntries(entries) as Record<string, unknown>;
  }, [nodeClass]);

  const passesModelFilters = useCallback(
    (metadata: Record<string, unknown> | undefined | null): boolean => {
      if (!modelFilters) return true;
      if (!metadata) return false;
      for (const [key, expected] of Object.entries(modelFilters)) {
        if (metadata[key] !== expected) return false;
      }
      return true;
    },
    [modelFilters],
  );

  const {
    data: providersData = [],
    isLoading: isLoadingProviders,
    isFetching: isFetchingProviders,
    error: providersError,
    refetch: refetchProviders,
  } = useGetModelProviders({});
  const {
    data: enabledModelsData,
    isLoading: isLoadingEnabledModels,
    isFetching: isFetchingEnabledModels,
    error: enabledModelsError,
    refetch: refetchEnabledModels,
  } = useGetEnabledModels();

  const isLoading = isLoadingProviders || isLoadingEnabledModels;
  const isFetching = isFetchingProviders || isFetchingEnabledModels;
  // Only surface the retry UI when a query failed AND it has no usable data
  // to fall back on. TanStack Query exposes ``data`` alongside ``error`` for
  // refetch failures (the providers hook explicitly preserves stale data on
  // error), so a transient background-refetch error should not replace a
  // working dropdown with the "couldn't load models" affordance. We also
  // wait until any in-flight refetch settles to avoid flicker.
  const providersUnusable =
    !!providersError && (!providersData || providersData.length === 0);
  const enabledModelsUnusable =
    !!enabledModelsError && enabledModelsData === undefined;
  const hasInitialLoadError =
    !isFetching && (providersUnusable || enabledModelsUnusable);

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
      // selection stays visible and selectable in the dropdown — UNLESS
      // the user has the provider configured locally, in which case the
      // sticky default reflects a model they've actively deactivated (not a
      // provider that needs setup). Hide it so the dropdown defaults to a
      // valid option instead of surfacing the stale selection with a wrench.
      const isStickyNotEnabled = option.metadata?.not_enabled_locally === true;
      if (isStickyNotEnabled) {
        const providerConfigured = providersData?.some(
          (p) => p.provider === provider && p.is_configured,
        );
        if (providerConfigured) continue;
      }

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

      // Defensive filter pass. The backend's update_build_config already
      // applies ``filters`` to ``options``, but stale saved flows (template
      // persisted before the filter shipped) can deliver a build_config
      // that hasn't been filter-corrected yet. Apply the same filter here
      // so a tool-incompatible saved model can't surface even when
      // ``options`` includes it.
      if (
        !passesModelFilters(
          option.metadata as Record<string, unknown> | undefined,
        )
      ) {
        continue;
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
          const modelMetadata = (model.metadata ?? {}) as Record<
            string,
            unknown
          >;
          const modelMetadataType = modelMetadata.model_type;
          if (
            typeof modelMetadataType === "string" &&
            modelMetadataType !== modelType
          ) {
            continue;
          }

          // Apply the declarative filter (e.g. tool_calling=True for the
          // Agent picker). Without this, every enabled model from
          // ``useGetModelProviders`` re-enters the dropdown regardless of
          // capability and re-introduces the bug the backend filter fixed.
          if (!passesModelFilters(modelMetadata)) continue;

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
            metadata: modelMetadata,
          });
        }
      }
    }

    // Source of truth is the providers list: re-inject a registry-valid saved
    // model the filters excluded, so an Assistant-applied model isn't reset.
    const savedValue = value?.[0];
    const savedKey = savedValue?.name
      ? `${savedValue.provider || "Unknown"}::${savedValue.name}`
      : null;
    const savedInRegistry =
      !!savedValue?.name &&
      (providersData?.some(
        (p) =>
          p.provider === savedValue.provider &&
          (p.models ?? []).some((m) => m.model_name === savedValue.name),
      ) ??
        false);
    const shouldInjectSaved =
      !!savedValue?.name &&
      !!savedKey &&
      !seen.has(savedKey) &&
      (Object.keys(grouped).length === 0 || savedInRegistry);
    if (shouldInjectSaved && savedValue) {
      const providerName = savedValue.provider || "Unknown";
      grouped[providerName] = grouped[providerName] ?? [];
      grouped[providerName].push({
        ...(savedValue.id && { id: savedValue.id }),
        name: savedValue.name,
        icon: savedValue.icon || "Bot",
        provider: providerName,
        metadata: {
          ...(savedValue.metadata ?? {}),
          not_enabled_locally: true,
        },
      } as ModelOption);
    }

    return grouped;
  }, [
    options,
    enabledModelsData,
    providersData,
    modelType,
    value,
    passesModelFilters,
  ]);

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
        name: t("modelInput.connectOtherModels"),
        icon: externalOptions?.fields?.data?.node?.icon || "CornerDownLeft",
        provider: "",
      } as SelectedModel;
    }

    // Bug 3 [P2] — defensive: sanitize the saved value before reading
    // `name`. A doubly-encoded payload from the assistant's flow_update
    // pipeline can leave the entire model list serialized into the
    // ``name`` field (or wrap the whole structured value into the first
    // element of the array). Without recovery, the trigger renders the
    // literal JSON, e.g. ``[{"provider":"OpenAI","name":"gpt-4o",...]``.
    const saved = recoverModelOption(value?.[0]);
    const currentName = saved?.name;
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
    //
    // EXCEPTION: when the saved provider is configured locally, the saved
    // model has been actively deactivated (not missing-because-unconfigured).
    // Fall through to the first available option so the user isn't shown a
    // wrench for a provider that doesn't need configuring.
    if (saved) {
      const savedProviderConfigured = providersData?.some(
        (p) => p.provider === saved.provider && p.is_configured,
      );
      if (!savedProviderConfigured) {
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
    }

    return flatOptions.length > 0 ? flatOptions[0] : null;
  }, [value, flatOptions, isConnectionMode, externalOptions, providersData]);

  useEffect(() => {
    if (flatOptions.length === 0 || isConnectionMode) return;
    if (hasProcessedEmptyRef.current) return;

    const isEmpty = !value || value.length === 0;

    // Detect a stale saved value: the saved model isn't in flatOptions AND
    // the saved provider is configured locally (the user has actively
    // deactivated this specific model rather than missing the provider
    // entirely). Reset the persisted value so the flow doesn't reference a
    // model the user can no longer run.
    let isSavedValueStale = false;
    if (!isEmpty) {
      const saved = value[0];
      const inOptions = flatOptions.some((opt) => opt.name === saved.name);
      if (!inOptions && saved.provider) {
        isSavedValueStale =
          providersData?.some(
            (p) => p.provider === saved.provider && p.is_configured,
          ) ?? false;
      }
    }

    // Sticky-default: if the component has a saved value, keep it as-is. The
    // backend injects any selection that isn't in the user's enabled list
    // back into `options` tagged with `not_enabled_locally`, so the saved
    // value remains visible and runnable. Only auto-select the first option
    // when there's no saved value at all OR when the saved value is stale.
    if (!isEmpty && !isSavedValueStale) return;

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
  }, [flatOptions, value, handleOnNewValue, isConnectionMode, providersData]);

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
      await refreshAllModelInputs({ silent: false });
    } catch {
      // refreshAllModelInputs handles its own error notifications via alertStore
    } finally {
      setRefreshOptions(false);
    }
  }, [refreshAllModelInputs]);

  const handleManageProvidersDialogClose = useCallback(
    (opts?: { hasChanges?: boolean }) => {
      setOpenManageProvidersDialog(false);
      // Only enter the post-close loading state when the modal will actually
      // refresh model inputs. When the user opens the dialog and closes it
      // without touching anything, there's no refetch to wait on, so the
      // dropdown should not flicker through "Loading models…".
      if (opts?.hasChanges) {
        setIsRefreshingAfterClose(true);
      }
    },
    [],
  );

  // Clear the refreshing indicator only after BOTH the providers and the
  // enabled-models queries have completed a full refetch cycle (isFetching:
  // false -> true -> false). Watching only ``isFetchingProviders`` clears the
  // loading state too early when the enabled-models refetch is slower,
  // letting ``groupedOptions`` render against a stale ``enabledModelsData``
  // cache; disabled models would briefly leak back into the dropdown after
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
      <LoadingTextComponent text={t("modelInput.loadingModels")} />
    </Button>
  );

  const handleRetryLoad = useCallback(() => {
    void refetchProviders();
    void refetchEnabledModels();
  }, [refetchProviders, refetchEnabledModels]);

  const renderErrorButton = () => (
    <Button
      className="dropdown-component-false-outline w-full justify-between py-2 font-normal"
      variant="primary"
      size="xs"
      data-testid="model-input-load-failed"
      onClick={handleRetryLoad}
    >
      <span className="flex items-center gap-2 truncate text-left">
        <ForwardedIconComponent
          name="AlertTriangle"
          className="h-3.5 w-3.5 shrink-0 text-status-yellow"
        />
        <span className="truncate">{t("modelInput.loadFailed")}</span>
      </span>
      <ForwardedIconComponent name="RotateCw" className="h-3.5 w-3.5" />
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
        t("modelInput.manageProviders"),
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
        avoidCollisions
        collisionPadding={{
          bottom: showingBuildPanel ? BUILD_PANEL_COLLISION_PADDING_PX : 0,
        }}
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
            t("modelInput.refreshList"),
            "RotateCw",
            handleRefreshButtonPress,
            "refresh-model-list",
          )}
          {renderManageProvidersButton()}
          {externalOptions?.fields?.data?.node && (
            <div className="border-t bg-background">
              {renderFooterButton(
                t("modelInput.connectOtherModels"),
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

  // Surface a retry affordance only when the queries failed AND we have no
  // usable data to display. Without this the dropdown silently stays empty
  // (or, before the api interceptor fix, looped on "Loading models…"
  // indefinitely) when the auth/model endpoints reject the initial request.
  // We deliberately ignore refetch errors that leave stale data intact so a
  // transient background refresh failure doesn't replace a working dropdown
  // with the error state.
  if (hasInitialLoadError) {
    return <div className="w-full">{renderErrorButton()}</div>;
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
              placeholder={resolvedPlaceholder}
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
              aria-label={t("model.configureProvider")}
              title={t("model.notEnabledTitle")}
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
