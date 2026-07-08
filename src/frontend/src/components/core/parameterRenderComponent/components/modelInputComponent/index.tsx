import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import LoadingTextComponent from "@/components/common/loadingTextComponent";
import { BUILD_PANEL_COLLISION_PADDING_PX } from "@/constants/constants";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { useRefreshModelInputs } from "@/hooks/use-refresh-model-inputs";
import ModelProviderModal from "@/modals/modelProviderModal";
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
import { focusCommandListOnOpen } from "../../utils/focus-command-list-on-open";
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
  const refButton = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [openManageProvidersDialog, setOpenManageProvidersDialog] =
    useState(false);
  const [isRefreshingAfterClose, setIsRefreshingAfterClose] = useState(false);
  const [refreshOptions, setRefreshOptions] = useState(false);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const buildInfo = useFlowStore((state) => state.buildInfo);
  const inspectionPanelVisible = useFlowStore(
    (state) => state.inspectionPanelVisible,
  );
  const showingBuildPanel =
    isBuilding || !!buildInfo?.error || !!buildInfo?.success;

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
      setConnectionMode(true);
    },
  });

  const modelType =
    modelTypeProp ??
    (nodeClass?.template?.model?.model_type === "language"
      ? "llm"
      : "embeddings");

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

  const groupedOptions = useMemo(() => {
    const grouped: Record<string, ModelOption[]> = {};
    const seen = new Set<string>();

    for (const option of options) {
      if (option.metadata?.is_disabled_provider) continue;
      const provider = option.provider || "Unknown";

      const isStickyNotEnabled = option.metadata?.not_enabled_locally === true;
      if (isStickyNotEnabled) {
        const providerConfigured = providersData?.some(
          (p) => p.provider === provider && p.is_configured,
        );
        if (providerConfigured) continue;
      }

      if (!isStickyNotEnabled && enabledModelsData?.enabled_models) {
        const providerModels = enabledModelsData.enabled_models[provider];
        if (providerModels && providerModels[option.name] !== true) {
          continue;
        }
      }

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

    if (enabledModelsData?.enabled_models && providersData) {
      for (const providerInfo of providersData) {
        const providerName = providerInfo.provider;
        const providerModels = enabledModelsData.enabled_models[providerName];
        if (!providerModels) continue;

        for (const model of providerInfo.models ?? []) {
          const modelName = model.model_name;
          if (providerModels[modelName] !== true) continue;

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

  const flatOptions = useMemo(
    () => Object.values(groupedOptions).flat(),
    [groupedOptions],
  );

  const selectedModel = useMemo(() => {
    if (isConnectionMode) {
      return {
        name: t("modelInput.connectOtherModels"),
        icon: externalOptions?.fields?.data?.node?.icon || "CornerDownLeft",
        provider: "",
      } as SelectedModel;
    }

    const saved = recoverModelOption(value?.[0]);
    const currentName = saved?.name;
    if (!currentName) {
      if (flatOptions.length > 0 && !hasProcessedEmptyRef.current) {
        return flatOptions[0];
      }
      return null;
    }

    const match = flatOptions.find((option) => option.name === currentName);
    if (match) return match;

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

    if (!isEmpty && !isSavedValueStale) return;

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
    hasProcessedEmptyRef.current = true;
  }, [flatOptions, value, handleOnNewValue, isConnectionMode, providersData]);

  /**
   * Handles model selection from the dropdown.
   */
  const handleModelSelect = useCallback(
    (modelName: string) => {
      setConnectionMode(false);
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
    } finally {
      setRefreshOptions(false);
    }
  }, [refreshAllModelInputs]);

  const handleManageProvidersDialogClose = useCallback(
    (opts?: { hasChanges?: boolean }) => {
      setOpenManageProvidersDialog(false);
      if (opts?.hasChanges) {
        setIsRefreshingAfterClose(true);
      }
    },
    [],
  );

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
      className="w-full flex cursor-pointer items-center justify-start gap-2 truncate py-2 text-xs text-muted-foreground px-3 hover:bg-accent group focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-ring"
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
      editNode || inspectionPanel || inspectionPanelVisible
        ? PopoverContent
        : PopoverContentWithoutPortal;
    return (
      <PopoverContentInput
        side="bottom"
        avoidCollisions
        onOpenAutoFocus={focusCommandListOnOpen}
        collisionPadding={{
          bottom: showingBuildPanel ? BUILD_PANEL_COLLISION_PADDING_PX : 0,
        }}
        className="noflow nowheel nopan nodelete nodrag z-[70] p-0"
        style={{ minWidth: refButton?.current?.clientWidth ?? "200px" }}
      >
        {/* Section 1 — the option list (a self-contained listbox). Keeping the
            footer actions out of <Command> stops them from being swept into the
            listbox's composite keyboard/focus model. */}
        <Command label={t("model.selectModel")} className="flex flex-col">
          <ModelList
            groupedOptions={groupedOptions}
            selectedModel={selectedModel}
            onSelect={handleModelSelect}
          />
        </Command>
        {/* Section 2 — footer actions, a plain group of buttons reachable by Tab
            after the list. */}
        <div className="flex flex-col border-t border-border bg-background">
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
        </div>
      </PopoverContentInput>
    );
  };

  if (!showParameter) {
    return null;
  }

  if (hasInitialLoadError) {
    return <div className="w-full">{renderErrorButton()}</div>;
  }

  if (isLoading || isRefreshingAfterClose || refreshOptions) {
    return <div className="w-full">{renderLoadingButton()}</div>;
  }

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
