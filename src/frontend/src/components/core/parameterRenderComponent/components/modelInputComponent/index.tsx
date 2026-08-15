import { useCallback, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

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
import { Command } from "../../../../ui/command";
import {
  Popover,
  PopoverContent,
  PopoverContentWithoutPortal,
} from "../../../../ui/popover";
import type { BaseInputProps } from "../../types";
import {
  focusCommandListOnOpen,
  refocusSelectedCommandItemOnNavigate,
} from "../../utils/focus-command-list-on-open";
import { ModelDropdownFooter } from "./components/ModelDropdownFooter";
import {
  ModelInputErrorButton,
  ModelInputLoadingButton,
} from "./components/ModelInputStates";
import ModelList from "./components/ModelList";
import ModelTrigger, { isSetupProviderState } from "./components/ModelTrigger";
import { buildGroupedOptions } from "./helpers/build-grouped-options";
import { deriveSelectedModel } from "./helpers/derive-selected-model";
import { matchesModelIdentity } from "./helpers/model-option-identity";
import { useAutoSelectModel } from "./hooks/useAutoSelectModel";
import { useModelConnectionLogic } from "./hooks/useModelConnectionLogic";
import { useRefreshAfterProviderClose } from "./hooks/useRefreshAfterProviderClose";
import type { ModelInputComponentType, ModelOption } from "./types";

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
  "aria-label": ariaLabel,
  ariaLabelledBy,
}: BaseInputProps<ModelOption[] | undefined> &
  ModelInputComponentType): JSX.Element | null {
  const { t } = useTranslation();
  const resolvedPlaceholder = placeholder ?? t("model.setupProvider");
  const refButton = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [openManageProvidersDialog, setOpenManageProvidersDialog] =
    useState(false);
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
  const providerStatusIsReliable = !isFetchingProviders && !providersError;
  const modelStatusIsReliable =
    providerStatusIsReliable && !isFetchingEnabledModels && !enabledModelsError;

  const hasEnabledProviders = useMemo(() => {
    return providersData?.some(
      (provider) => provider.is_enabled || provider.is_configured,
    );
  }, [providersData]);

  const groupedOptions = useMemo(
    () =>
      buildGroupedOptions({
        options,
        enabledModels: enabledModelsData?.enabled_models,
        providers: providersData,
        modelType,
        savedValue: value?.[0],
        modelFilters,
        providerStatusIsReliable,
      }),
    [
      options,
      enabledModelsData,
      providersData,
      modelType,
      value,
      modelFilters,
      providerStatusIsReliable,
    ],
  );

  const flatOptions = useMemo(
    () => Object.values(groupedOptions).flat(),
    [groupedOptions],
  );

  const selectedModel = useMemo(
    () =>
      deriveSelectedModel({
        isConnectionMode,
        connectLabel: t("modelInput.connectOtherModels"),
        connectIcon: externalOptions?.fields?.data?.node?.icon,
        savedValue: value?.[0],
        flatOptions,
        providers: providersData,
        providerStatusIsReliable,
      }),
    [
      value,
      flatOptions,
      isConnectionMode,
      externalOptions,
      providersData,
      providerStatusIsReliable,
    ],
  );

  useAutoSelectModel({
    flatOptions,
    value,
    handleOnNewValue,
    isConnectionMode,
    providers: providersData,
    modelStatusIsReliable,
  });

  /**
   * Handles model selection from the dropdown.
   */
  const handleModelSelect = useCallback(
    (modelName: string, provider?: string) => {
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
      const selectedOption = flatOptions.find((option) =>
        matchesModelIdentity(option, { name: modelName, provider }),
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

  const { isRefreshingAfterClose, handleManageProvidersDialogClose } =
    useRefreshAfterProviderClose({
      isFetchingProviders,
      isFetchingEnabledModels,
      setOpenManageProvidersDialog,
    });

  const handleRetryLoad = useCallback(() => {
    void refetchProviders();
    void refetchEnabledModels();
  }, [refetchProviders, refetchEnabledModels]);

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
        <Command
          label={t("model.selectModel")}
          className="flex flex-col"
          defaultValue={
            selectedModel
              ? `${selectedModel.provider}::${selectedModel.name}`
              : undefined
          }
          onKeyDown={refocusSelectedCommandItemOnNavigate}
        >
          <ModelList
            groupedOptions={groupedOptions}
            selectedModel={selectedModel}
            onSelect={handleModelSelect}
          />
        </Command>
        <ModelDropdownFooter
          onRefresh={handleRefreshButtonPress}
          onManageProviders={() => setOpenManageProvidersDialog(true)}
          externalNode={externalOptions?.fields?.data?.node}
          onConnectOtherModels={() =>
            handleExternalOptions("connect_other_models")
          }
        />
      </PopoverContentInput>
    );
  };

  if (!showParameter) {
    return null;
  }

  if (hasInitialLoadError) {
    return (
      <div className="w-full">
        <ModelInputErrorButton onRetry={handleRetryLoad} />
      </div>
    );
  }

  if (isLoading || isRefreshingAfterClose || refreshOptions) {
    return (
      <div className="w-full">
        <ModelInputLoadingButton />
      </div>
    );
  }

  const showConfigureAffordance =
    selectedModel?.metadata?.not_enabled_locally === true &&
    !isSetupProviderState({
      hasEnabledProviders: hasEnabledProviders ?? false,
      showEmptyState,
      optionCount: flatOptions.length,
    });

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
              aria-label={ariaLabel}
              ariaLabelledBy={ariaLabelledBy}
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
