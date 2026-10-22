import { useCallback, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { BUILD_PANEL_COLLISION_PADDING_PX } from "@/constants/constants";
import { getEnabledModelsForType } from "@/controllers/API/helpers/enabled-model-policy";
import {
  getAxiosErrorDetail,
  isAccessRefusal,
} from "@/controllers/API/helpers/get-axios-error-message";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import { useRefreshModelInputs } from "@/hooks/use-refresh-model-inputs";
import ModelProviderModal from "@/modals/modelProviderModal";
import { providerServesFilter } from "@/modals/modelProviderModal/helpers/view-kinds";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { NodeDataType } from "@/types/flow";
import type { ModelType } from "@/types/models";
import { isUserOwnedModelKind, modelKindOfField } from "@/utils/model-kind";
import ForwardedIconComponent from "../../../../common/genericIconComponent";
import { Command } from "../../../../ui/command";

/**
 * cmdk unconditionally renders a hidden `<label htmlFor={inputId}>` inside
 * <Command>, even when no CommandInput exists for that id — a label whose
 * `for` references nothing (IBM label_ref_valid, WCAG 1.3.1). The listbox
 * carries the picker's accessible name, so the reference is pure debt.
 * Only the `for` ATTRIBUTE is removed — never the node (React owns it and
 * would fight its removal during reconciliation; attribute edits are safe
 * because React only rewrites props it sees change, and `htmlFor` never
 * changes here). The `label` prop stays so the element keeps inner text:
 * an EMPTY label just trades `label_ref_valid` for `label_content_exists`
 * (which ignores aria-hidden), while a text-bearing label with no `for`
 * passes every rule and is inert to screen readers — nothing references it.
 */
export function stripDanglingCmdkLabelFor(root: HTMLElement | null): void {
  const label = root?.querySelector("label[cmdk-label][for]");
  if (label && !document.getElementById(label.getAttribute("for") ?? "")) {
    label.removeAttribute("for");
  }
}

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
  ModelInputNotice,
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
  fieldName = "model",
  providerScope,
  "aria-label": ariaLabel,
  ariaLabelledBy,
  ariaDescribedBy,
  ariaInvalid,
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

  const nodeConnectionMode = useFlowStore((state) => {
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

  const { handleExternalOptions } = useModelConnectionLogic({
    nodeId: nodeId || "",
    fieldName,
    closePopover: () => setOpen(false),
    clearSelection: () => {
      setConnectionMode(true);
    },
  });

  const modelField = nodeClass?.template?.[fieldName];
  // An unknown kind is refused below rather than guessed: a guess would offer
  // models the field cannot run.
  const fieldKind = modelTypeProp ?? modelKindOfField(modelField);
  const isUnsupportedKind = fieldKind === null;
  const modelType: ModelType = fieldKind ?? "llm";
  // Connection mode is stored per node, and a decision field never connects
  // other models, so on Smart Router it belongs to the language field only.
  const isConnectionMode =
    nodeConnectionMode && !isUserOwnedModelKind(modelType);

  const modelFilters = useMemo(() => {
    const raw = (
      modelField as { filters?: Record<string, unknown> } | undefined
    )?.filters;
    if (!raw || typeof raw !== "object") return undefined;
    const entries = Object.entries(raw).filter(
      ([, v]) => v !== null && v !== undefined,
    );
    if (entries.length === 0) return undefined;
    return Object.fromEntries(entries) as Record<string, unknown>;
  }, [modelField]);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const hasExplicitProviderScope = providerScope !== undefined;
  const resolvedProviderScope = hasExplicitProviderScope
    ? providerScope
    : { flowId: currentFlowId };
  const hasExplicitFlowScopeKey =
    hasExplicitProviderScope && Object.hasOwn(resolvedProviderScope, "flowId");
  const hasExplicitProjectScopeKey =
    hasExplicitProviderScope &&
    Object.hasOwn(resolvedProviderScope, "projectId");
  const explicitScopeKeyCount =
    Number(hasExplicitFlowScopeKey) + Number(hasExplicitProjectScopeKey);
  const hasValidExplicitProviderScope =
    explicitScopeKeyCount === 0 ||
    (explicitScopeKeyCount === 1 &&
      (hasExplicitFlowScopeKey
        ? Boolean(resolvedProviderScope.flowId?.trim())
        : Boolean(resolvedProviderScope.projectId?.trim())));
  const hasProviderPolicyContext = hasExplicitProviderScope
    ? hasValidExplicitProviderScope
    : Boolean(currentFlowId);

  const {
    data: providersData = [],
    isLoading: isLoadingProviders,
    isFetching: isFetchingProviders,
    fetchStatus: providersFetchStatus,
    error: providersError,
    refetch: refetchProviders,
  } = useGetModelProviders(
    { ...resolvedProviderScope, purpose: "use" },
    { enabled: hasProviderPolicyContext },
  );
  const {
    data: enabledModelsData,
    isLoading: isLoadingEnabledModels,
    isFetching: isFetchingEnabledModels,
    fetchStatus: enabledModelsFetchStatus,
    error: enabledModelsError,
    refetch: refetchEnabledModels,
  } = useGetEnabledModels({
    ...resolvedProviderScope,
    purpose: "use",
    enabled: hasProviderPolicyContext,
  });

  const isLoading =
    !hasProviderPolicyContext || isLoadingProviders || isLoadingEnabledModels;
  const isPolicyPaused =
    providersFetchStatus === "paused" || enabledModelsFetchStatus === "paused";
  const isFetching =
    isFetchingProviders || isFetchingEnabledModels || isPolicyPaused;
  const hasPolicyError = !!providersError || !!enabledModelsError;
  const providerStatusIsReliable =
    hasProviderPolicyContext &&
    !isFetchingProviders &&
    providersFetchStatus !== "paused" &&
    !providersError;
  const modelStatusIsReliable =
    providerStatusIsReliable &&
    !isFetchingEnabledModels &&
    enabledModelsFetchStatus !== "paused" &&
    !enabledModelsError;
  const enabledModelsForType = useMemo(
    () =>
      enabledModelsData
        ? getEnabledModelsForType(enabledModelsData, modelType)
        : undefined,
    [enabledModelsData, modelType],
  );

  // A provider counts only when it serves this field's kind: a TypeSafe key
  // alone leaves a language field nothing to pick, so it still says Setup Provider.
  const hasEnabledProviders = useMemo(() => {
    return (
      modelStatusIsReliable &&
      providersData?.some(
        (provider) =>
          (provider.is_enabled || provider.is_configured) &&
          providerServesFilter(
            provider.models,
            modelType,
            provider.live_discovery,
          ),
      )
    );
  }, [modelStatusIsReliable, providersData, modelType]);

  const groupedOptions = useMemo(() => {
    // Query data remains cached during background refreshes and after
    // refresh errors. Do not turn that potentially revoked snapshot into
    // selectable options until both policy queries have settled cleanly.
    if (!modelStatusIsReliable || isUnsupportedKind) return {};
    return buildGroupedOptions({
      options,
      enabledModels: enabledModelsForType,
      providers: providersData,
      modelType,
      savedValue: value?.[0],
      modelFilters,
      providerStatusIsReliable,
    });
  }, [
    options,
    enabledModelsForType,
    providersData,
    modelType,
    value,
    modelFilters,
    providerStatusIsReliable,
    modelStatusIsReliable,
    isUnsupportedKind,
  ]);

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
        enabledModels: enabledModelsForType,
        modelStatusIsReliable,
        modelType,
      }),
    [
      value,
      flatOptions,
      isConnectionMode,
      externalOptions,
      providersData,
      providerStatusIsReliable,
      enabledModelsForType,
      modelStatusIsReliable,
      modelType,
    ],
  );

  useAutoSelectModel({
    flatOptions,
    value,
    handleOnNewValue,
    isConnectionMode,
    providers: providersData,
    modelStatusIsReliable,
    enabledModels: enabledModelsForType,
    modelType,
  });

  /**
   * Handles model selection from the dropdown.
   */
  const handleModelSelect = useCallback(
    (modelName: string, provider?: string) => {
      if (!modelStatusIsReliable) return;
      if (isConnectionMode) setConnectionMode(false);
      if (nodeId) {
        const store = useFlowStore.getState();
        const node = store.getNode(nodeId);
        const nodeData = node?.data as NodeDataType | undefined;
        if (nodeData?.node?.template?.[fieldName]?._connection_mode) {
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
                    [fieldName]: {
                      ...(prev.data as NodeDataType).node.template[fieldName],
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
    [
      flatOptions,
      handleOnNewValue,
      modelStatusIsReliable,
      fieldName,
      isConnectionMode,
      setConnectionMode,
    ],
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

  // Keep the configuration dialog mounted while its own mutations invalidate
  // the picker's policy queries. The picker still fails closed below, but the
  // dialog must retain its selection and in-flight save state until it closes.
  const manageProvidersDialog = openManageProvidersDialog ? (
    <ModelProviderModal
      open={openManageProvidersDialog}
      onClose={handleManageProvidersDialogClose}
      modelType={modelType}
      flowId={resolvedProviderScope.flowId}
      projectId={resolvedProviderScope.projectId}
    />
  ) : null;

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
        {/* The picker's accessible name lives on the CommandList (the
            listbox). cmdk also renders a hidden <label htmlFor={inputId}>
            for a CommandInput that does not exist here — the ref strips
            that dangling reference; see stripDanglingCmdkLabelFor. */}
        <Command
          ref={stripDanglingCmdkLabelFor}
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

  if (isUnsupportedKind) {
    return (
      <ModelInputNotice
        label={t("modelInput.unsupportedKind")}
        testId="model-input-unsupported-kind"
      />
    );
  }

  if (hasPolicyError && !isFetching) {
    // A server refusal, such as a policy denial, says why; a network failure
    // keeps the generic retry message.
    const serverReason = [providersError, enabledModelsError]
      .map((error) => getAxiosErrorDetail(error, ""))
      .find(Boolean);
    // A refusal fails the same way on retry, so it is a notice, as in Model Providers, naming the
    // refusal's own reason.
    const refusal = [providersError, enabledModelsError].find(isAccessRefusal);
    return (
      <>
        <div className="w-full">
          {refusal ? (
            <ModelInputNotice
              label={
                getAxiosErrorDetail(refusal, "") ||
                t("modelProviders.errorNoAccess")
              }
              testId="model-input-load-failed"
              ariaLabelledBy={ariaLabelledBy}
            />
          ) : (
            <ModelInputErrorButton
              label={serverReason || t("modelInput.loadFailed")}
              onRetry={handleRetryLoad}
            />
          )}
        </div>
        {manageProvidersDialog}
      </>
    );
  }

  if (isLoading || isFetching || isRefreshingAfterClose || refreshOptions) {
    return (
      <>
        <div className="w-full">
          <ModelInputLoadingButton />
        </div>
        {manageProvidersDialog}
      </>
    );
  }

  const keepsSavedModel =
    isUserOwnedModelKind(modelType) && !!selectedModel?.name;
  const showConfigureAffordance =
    selectedModel?.metadata?.not_enabled_locally === true &&
    (keepsSavedModel ||
      !isSetupProviderState({
        hasEnabledProviders: hasEnabledProviders ?? false,
        showEmptyState,
        optionCount: flatOptions.length,
      }));

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
              keepsSavedModel={keepsSavedModel}
              id={id}
              refButton={refButton}
              showEmptyState={showEmptyState}
              aria-label={ariaLabel}
              ariaLabelledBy={ariaLabelledBy}
              ariaDescribedBy={ariaDescribedBy}
              ariaInvalid={ariaInvalid}
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
              aria-label={
                selectedModel?.metadata?.switched_off === true
                  ? t("model.turnOnInProviders")
                  : t("model.configureProvider")
              }
              title={
                selectedModel?.metadata?.switched_off === true
                  ? t("model.switchedOffTitle")
                  : t("model.notEnabledTitle")
              }
              className="shrink-0 inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-primary"
            >
              <ForwardedIconComponent name="Wrench" className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        {renderPopoverContent()}
      </Popover>

      {manageProvidersDialog}
    </>
  );
}
