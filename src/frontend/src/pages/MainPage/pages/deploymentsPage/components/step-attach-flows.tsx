import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { useGetDeploymentConfigs } from "@/controllers/API/queries/deployments/use-get-deployment-configs";
import { getFlowVersionEntry } from "@/controllers/API/queries/flow-version/use-get-flow-version-entry";
import { useGetFlowVersions } from "@/controllers/API/queries/flow-version/use-get-flow-versions";
import { usePostCreateSnapshot } from "@/controllers/API/queries/flow-version/use-post-create-snapshot";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import { usePostDetectEnvVars } from "@/controllers/API/queries/variables/use-post-detect-env-vars";
import useAlertStore from "@/stores/alertStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";
import { getWatsonxFlowEligibilityIssue } from "../helpers/watsonx-flow-eligibility";
import { useConnectionPanelState } from "../hooks/use-connection-panel-state";
import {
  type ConnectionItem,
  DEFAULT_FLOW_NAME,
  getDefaultDeploymentToolName,
  getSelectedFlowVersionKey,
  WXO_PROVIDER_KEY,
} from "../types";
import { ConnectionPanel } from "./step-attach-flows-connection-panel";
import { FlowListPanel } from "./step-attach-flows-flow-list-panel";
import { VersionPanel } from "./step-attach-flows-version-panel";

type RightPanelView = "versions" | "connections";

export default function StepAttachFlows() {
  const {
    isEditMode,
    initialFlowId,
    selectedProvider,
    selectedInstance,
    connections,
    setConnections,
    selectedVersionByFlow,
    handleSelectVersion: onSelectVersion,
    setToolNameByFlow,
    attachedConnectionByFlow,
    setAttachedConnectionByFlow: onAttachConnection,
    removedFlowIds,
    handleRemoveAttachedFlow,
    handleUndoRemoveFlow,
  } = useDeploymentStepper();

  const { t } = useTranslation();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const currentFolderId = folderId ?? myCollectionId;
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { data: flowsData } = useGetRefreshFlowsQuery(
    {
      get_all: true,
      remove_example_flows: true,
    },
    { enabled: !!currentFolderId },
  );
  const flows = useMemo(() => {
    const list = Array.isArray(flowsData) ? flowsData : [];
    const filtered = list.filter(
      (f) =>
        !f.is_component &&
        (f.folder_id === currentFolderId || f.id === initialFlowId),
    );
    // In edit mode, sort already-attached flows to the top.
    if (selectedVersionByFlow.size > 0) {
      filtered.sort((a, b) => {
        const aAttached = Array.from(selectedVersionByFlow.values()).some(
          (entry) => entry.flowId === a.id,
        )
          ? 0
          : 1;
        const bAttached = Array.from(selectedVersionByFlow.values()).some(
          (entry) => entry.flowId === b.id,
        )
          ? 0
          : 1;
        return aAttached - bAttached;
      });
    }
    return filtered;
  }, [flowsData, currentFolderId, initialFlowId, selectedVersionByFlow]);
  const isWatsonxProvider =
    selectedInstance?.provider_key === WXO_PROVIDER_KEY ||
    (selectedInstance === null && selectedProvider?.type === "watsonx");
  const wxoDraftEligibilityByFlow = useMemo(() => {
    const issues = new Map<
      string,
      NonNullable<ReturnType<typeof getWatsonxFlowEligibilityIssue>>
    >();
    if (!isWatsonxProvider) return issues;
    flows.forEach((flow) => {
      const issue = getWatsonxFlowEligibilityIssue(flow.data);
      if (issue) issues.set(flow.id, issue);
    });
    return issues;
  }, [flows, isWatsonxProvider]);

  // Fetch existing connections from the provider (tenant-scoped)
  const providerId = selectedInstance?.id ?? "";
  const { data: configsData } = useGetDeploymentConfigs(
    { providerId },
    { enabled: !!providerId },
  );

  // Seed the connections list with existing provider connections (once)
  const seededExistingConnections = useRef(false);
  useEffect(() => {
    if (seededExistingConnections.current || !configsData?.configs?.length)
      return;
    seededExistingConnections.current = true;

    const existingConnections: ConnectionItem[] = configsData.configs
      .filter((cfg) => cfg.environment !== "live")
      .map((cfg) => ({
        id: cfg.app_id,
        connectionId: cfg.connection_id,
        name: cfg.app_id,
        environment: cfg.environment,
        variableCount: 0,
        isNew: false,
        environmentVariables: {},
      }));

    setConnections((prev) => {
      // Avoid duplicates if user already created connections with the same id
      const existingIds = new Set(prev.map((c) => c.id));
      const toAdd = existingConnections.filter((c) => !existingIds.has(c.id));
      return [...toAdd, ...prev];
    });
  }, [configsData, setConnections]);

  const [selectedFlowId, setSelectedFlowId] = useState<string | null>(
    initialFlowId ?? null,
  );
  // Track the version the user clicked but hasn't finished the connection step for yet.
  const [pendingAttachment, setPendingAttachment] = useState<{
    key: string;
    flowId: string;
    flowName: string;
    versionId: string;
    versionTag: string;
    wxoEligibilityIssue?: NonNullable<
      ReturnType<typeof getWatsonxFlowEligibilityIssue>
    > | null;
  } | null>(null);
  const latestAttachmentRequestRef = useRef(0);
  const [rightPanel, setRightPanel] = useState<RightPanelView>("versions");
  const preselectedAttachment = useMemo(
    () =>
      initialFlowId
        ? Array.from(selectedVersionByFlow.values()).find(
            (entry) => entry.flowId === initialFlowId,
          )
        : undefined,
    [initialFlowId, selectedVersionByFlow],
  );

  const commitPendingAttachment = useCallback(() => {
    if (pendingAttachment) {
      onSelectVersion({
        flowId: pendingAttachment.flowId,
        flowName: pendingAttachment.flowName,
        versionId: pendingAttachment.versionId,
        versionTag: pendingAttachment.versionTag,
        wxoEligibilityIssue: pendingAttachment.wxoEligibilityIssue,
      });
      setToolNameByFlow((prev) => {
        if (prev.has(pendingAttachment.key)) {
          return prev;
        }
        const next = new Map(prev);
        next.set(
          pendingAttachment.key,
          getDefaultDeploymentToolName(pendingAttachment.flowName),
        );
        return next;
      });
      setPendingAttachment(null);
    }
  }, [pendingAttachment, onSelectVersion, setToolNameByFlow]);

  const resetPendingAttachment = useCallback(() => {
    latestAttachmentRequestRef.current += 1;
    setPendingAttachment(null);
  }, []);

  const effectiveFlowId = selectedFlowId ?? flows[0]?.id ?? null;

  const {
    connectionTab,
    setConnectionTab,
    selectedConnections,
    setSelectedConnections,
    newConnectionName,
    setNewConnectionName,
    envVars,
    detectedVarCount,
    isDuplicateConnectionName,
    handleAttachConnection,
    handleCreateConnection,
    handleSkipConnection,
    handleChangeFlow,
    handleAddEnvVar,
    handleEnvVarChange,
    handleEnvVarSelectGlobalVar,
    initConnectionsForFlow,
    updateDetectedEnvVars,
  } = useConnectionPanelState({
    connections,
    setConnections,
    effectiveAttachmentKey:
      pendingAttachment?.key ?? preselectedAttachment?.key ?? null,
    attachedConnectionByFlow,
    onAttachConnection,
    commitPendingAttachment,
    resetPendingAttachment,
    setRightPanel,
  });

  const { mutateAsync: detectEnvVars } = usePostDetectEnvVars();
  const { mutateAsync: createSnapshot, isPending: isCreatingDraftVersion } =
    usePostCreateSnapshot();
  const { data: globalVariables } = useGetGlobalVariables();
  const globalVariableOptions = (globalVariables ?? []).map((v) => v.name);
  const handledPreselectedAttachmentRef = useRef<string | null>(null);

  // When a flow+version are pre-selected from outside (e.g., canvas deploy button),
  // auto-advance to the connections panel and detect env vars for the pre-selected version.
  useEffect(() => {
    const preSelected = preselectedAttachment;
    if (!preSelected) {
      return;
    }

    const resolvedFlowName =
      flows.find((flow) => flow.id === preSelected.flowId)?.name ??
      preSelected.flowName;
    if (resolvedFlowName) {
      if (preSelected.flowName !== resolvedFlowName) {
        onSelectVersion({
          flowId: preSelected.flowId,
          flowName: resolvedFlowName,
          versionId: preSelected.versionId,
          versionTag: preSelected.versionTag,
          wxoEligibilityIssue: preSelected.wxoEligibilityIssue,
        });
      }
      setToolNameByFlow((prev) => {
        const defaultFlowToolName =
          getDefaultDeploymentToolName(DEFAULT_FLOW_NAME);
        const nextToolName = getDefaultDeploymentToolName(resolvedFlowName);
        const currentToolName = prev.get(preSelected.key)?.trim();
        if (currentToolName && currentToolName !== defaultFlowToolName) {
          return prev;
        }
        const next = new Map(prev);
        next.set(preSelected.key, nextToolName);
        return next;
      });
    }

    if (handledPreselectedAttachmentRef.current === preSelected.key) return;
    handledPreselectedAttachmentRef.current = preSelected.key;
    setRightPanel("connections");
    initConnectionsForFlow(preSelected.key);

    const detect = async () => {
      if (isWatsonxProvider) {
        try {
          const versionEntry = await getFlowVersionEntry({
            flowId: preSelected.flowId,
            versionId: preSelected.versionId,
          });
          const wxoEligibilityIssue = getWatsonxFlowEligibilityIssue(
            versionEntry.data,
          );
          if (wxoEligibilityIssue !== preSelected.wxoEligibilityIssue) {
            onSelectVersion({
              flowId: preSelected.flowId,
              flowName: resolvedFlowName ?? DEFAULT_FLOW_NAME,
              versionId: preSelected.versionId,
              versionTag: preSelected.versionTag,
              wxoEligibilityIssue,
            });
          }
        } catch {
          // The backend remains authoritative if version inspection is unavailable.
        }
      }
      try {
        const result = await detectEnvVars({
          flow_version_ids: [preSelected.versionId],
        });
        updateDetectedEnvVars(result.variables ?? []);
      } catch {
        setErrorData({
          title: t("deployments.cannotAutoDetectEnvVars"),
          list: [t("deployments.addManuallyInConnection")],
        });
      }
    };
    detect();
  }, [
    flows,
    detectEnvVars,
    initConnectionsForFlow,
    isWatsonxProvider,
    onSelectVersion,
    preselectedAttachment,
    setErrorData,
    setToolNameByFlow,
    updateDetectedEnvVars,
  ]);

  const { data: versionResponse, isLoading: isLoadingVersions } =
    useGetFlowVersions(
      { flowId: effectiveFlowId ?? "" },
      { enabled: !!effectiveFlowId },
    );
  const versions = versionResponse?.entries ?? [];

  const selectedFlow = flows.find((f) => f.id === effectiveFlowId);

  const openConnectionPanelForVersion = useCallback(
    async (
      flowId: string,
      flowName: string,
      versionId: string,
      versionTag: string,
    ) => {
      const requestId = latestAttachmentRequestRef.current + 1;
      latestAttachmentRequestRef.current = requestId;
      const attachmentKey = getSelectedFlowVersionKey(flowId, versionId);
      let wxoEligibilityIssue:
        | NonNullable<ReturnType<typeof getWatsonxFlowEligibilityIssue>>
        | null
        | undefined;
      if (isWatsonxProvider) {
        try {
          const versionEntry = await getFlowVersionEntry({ flowId, versionId });
          wxoEligibilityIssue = getWatsonxFlowEligibilityIssue(
            versionEntry.data,
          );
        } catch {
          // The backend remains authoritative if version inspection is unavailable.
        }
      }
      if (requestId !== latestAttachmentRequestRef.current) return;
      // Don't commit to context yet — wait for connection step to complete.
      setPendingAttachment({
        key: attachmentKey,
        flowId,
        flowName,
        versionId,
        versionTag,
        wxoEligibilityIssue,
      });
      setRightPanel("connections");
      initConnectionsForFlow(attachmentKey);

      // Auto-detect global variable references via the backend detection endpoint
      try {
        const result = await detectEnvVars({
          flow_version_ids: [versionId],
        });
        if (requestId !== latestAttachmentRequestRef.current) return;
        updateDetectedEnvVars(result.variables ?? []);
      } catch {
        if (requestId !== latestAttachmentRequestRef.current) return;
        updateDetectedEnvVars([]);
        setErrorData({
          title: t("deployments.cannotAutoDetectEnvVars"),
          list: [t("deployments.addManuallyInConnection")],
        });
      }
    },
    [
      detectEnvVars,
      initConnectionsForFlow,
      isWatsonxProvider,
      setErrorData,
      updateDetectedEnvVars,
    ],
  );

  const handleAttachFlow = useCallback(
    async (versionId: string) => {
      if (!effectiveFlowId) return;
      const version = versions.find((v) => v.id === versionId);
      await openConnectionPanelForVersion(
        effectiveFlowId,
        selectedFlow?.name ?? DEFAULT_FLOW_NAME,
        versionId,
        version?.version_tag ?? "",
      );
    },
    [effectiveFlowId, openConnectionPanelForVersion, selectedFlow, versions],
  );

  const handleCreateVersionFromDraft = useCallback(async () => {
    if (!effectiveFlowId) return;

    try {
      const snapshot = await createSnapshot({ flowId: effectiveFlowId });
      await openConnectionPanelForVersion(
        effectiveFlowId,
        selectedFlow?.name ?? DEFAULT_FLOW_NAME,
        snapshot.id,
        snapshot.version_tag,
      );
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setErrorData({
        title: t("deployments.createVersionFromDraftError"),
        ...(detail ? { list: [detail] } : {}),
      });
    }
  }, [
    createSnapshot,
    effectiveFlowId,
    openConnectionPanelForVersion,
    selectedFlow,
    setErrorData,
  ]);

  const handleDetachFlow = useCallback(
    (attachmentKey: string) => {
      handleRemoveAttachedFlow(attachmentKey);
      setRightPanel("versions");
    },
    [handleRemoveAttachedFlow],
  );

  const handleSelectFlow = useCallback(
    (flowId: string) => {
      resetPendingAttachment();
      setSelectedFlowId(flowId);
      setRightPanel("versions");
      setSelectedConnections(new Set());
    },
    [resetPendingAttachment, setSelectedConnections],
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 py-3">
      <h2 className="text-lg font-semibold">{t("deployments.stepFlows")}</h2>

      <div className="flex min-h-0 flex-1 overflow-hidden rounded-xl border border-border">
        <FlowListPanel
          flows={flows}
          selectedFlowId={effectiveFlowId}
          selectedVersionByFlow={selectedVersionByFlow}
          attachedConnectionByFlow={attachedConnectionByFlow}
          connections={connections}
          wxoDraftEligibilityByFlow={
            isWatsonxProvider ? wxoDraftEligibilityByFlow : undefined
          }
          removedFlowIds={isEditMode ? removedFlowIds : undefined}
          onSelectFlow={handleSelectFlow}
        />

        {/* Right panel */}
        <div className="flex min-w-0 flex-1 flex-col">
          {rightPanel === "versions" ? (
            <VersionPanel
              selectedFlow={selectedFlow}
              versions={versions}
              isLoadingVersions={isLoadingVersions}
              isCreatingDraftVersion={isCreatingDraftVersion}
              selectedVersionByFlow={selectedVersionByFlow}
              onAttach={handleAttachFlow}
              onCreateFromDraft={handleCreateVersionFromDraft}
              onDetach={handleDetachFlow}
              onUndoRemove={isEditMode ? handleUndoRemoveFlow : undefined}
              removedFlowIds={isEditMode ? removedFlowIds : undefined}
              attachedConnectionByFlow={attachedConnectionByFlow}
              connections={connections}
            />
          ) : (
            <ConnectionPanel
              connectionTab={connectionTab}
              onTabChange={setConnectionTab}
              connections={connections}
              selectedConnections={selectedConnections}
              onToggleConnection={(id) =>
                setSelectedConnections((prev) => {
                  const next = new Set(prev);
                  next.has(id) ? next.delete(id) : next.add(id);
                  return next;
                })
              }
              newConnectionName={newConnectionName}
              onNameChange={setNewConnectionName}
              envVars={envVars}
              detectedVarCount={detectedVarCount}
              globalVariableOptions={globalVariableOptions}
              onEnvVarChange={handleEnvVarChange}
              onEnvVarSelectGlobalVar={handleEnvVarSelectGlobalVar}
              onAddEnvVar={handleAddEnvVar}
              onChangeFlow={handleChangeFlow}
              onSkipConnection={handleSkipConnection}
              onAttachConnection={handleAttachConnection}
              onCreateConnection={handleCreateConnection}
              isDuplicateName={isDuplicateConnectionName}
            />
          )}
        </div>
      </div>
    </div>
  );
}
