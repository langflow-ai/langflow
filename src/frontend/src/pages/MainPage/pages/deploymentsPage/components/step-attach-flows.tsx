import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useGetDeploymentConfigs } from "@/controllers/API/queries/deployments/use-get-deployment-configs";
import { useGetFlowVersions } from "@/controllers/API/queries/flow-version/use-get-flow-versions";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import { usePostDetectEnvVars } from "@/controllers/API/queries/variables/use-post-detect-env-vars";
import useAlertStore from "@/stores/alertStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";
import { useConnectionPanelState } from "../hooks/use-connection-panel-state";
import type { ConnectionItem } from "../types";
import { ConnectionPanel } from "./step-attach-flows-connection-panel";
import { FlowListPanel } from "./step-attach-flows-flow-list-panel";
import { VersionPanel } from "./step-attach-flows-version-panel";

type RightPanelView = "versions" | "connections";

export default function StepAttachFlows() {
  const {
    isEditMode,
    initialFlowId,
    selectedInstance,
    connections,
    setConnections,
    selectedVersionByFlow,
    handleSelectVersion: onSelectVersion,
    toolNameByFlow,
    setToolNameByFlow,
    attachedConnectionByFlow,
    setAttachedConnectionByFlow: onAttachConnection,
    removedFlowIds,
    handleRemoveAttachedFlow,
    handleUndoRemoveFlow,
  } = useDeploymentStepper();

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
        const aAttached = selectedVersionByFlow.has(a.id) ? 0 : 1;
        const bAttached = selectedVersionByFlow.has(b.id) ? 0 : 1;
        return aAttached - bAttached;
      });
    }
    return filtered;
  }, [flowsData, currentFolderId, initialFlowId, selectedVersionByFlow]);

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

    const existingConnections: ConnectionItem[] = configsData.configs.map(
      (cfg) => ({
        id: cfg.app_id,
        connectionId: cfg.connection_id,
        name: cfg.app_id,
        variableCount: 0,
        isNew: false,
        environmentVariables: {},
      }),
    );

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
    flowId: string;
    versionId: string;
    versionTag: string;
  } | null>(null);
  const [rightPanel, setRightPanel] = useState<RightPanelView>("versions");

  const commitPendingAttachment = useCallback(() => {
    if (pendingAttachment) {
      onSelectVersion(
        pendingAttachment.flowId,
        pendingAttachment.versionId,
        pendingAttachment.versionTag,
      );
      setPendingAttachment(null);
    }
  }, [pendingAttachment, onSelectVersion]);

  const resetPendingAttachment = useCallback(() => {
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
    effectiveFlowId,
    attachedConnectionByFlow,
    onAttachConnection,
    commitPendingAttachment,
    resetPendingAttachment,
    setRightPanel,
  });

  const { mutateAsync: detectEnvVars } = usePostDetectEnvVars();
  const { data: globalVariables } = useGetGlobalVariables();
  const globalVariableOptions = (globalVariables ?? []).map((v) => v.name);

  // When a flow+version are pre-selected from outside (e.g., canvas deploy button),
  // auto-advance to the connections panel and detect env vars for the pre-selected version.
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentionally run only on mount
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const preSelected = initialFlowId
      ? selectedVersionByFlow.get(initialFlowId)
      : undefined;
    if (!preSelected) return;

    setRightPanel("connections");

    const detect = async () => {
      try {
        const result = await detectEnvVars({
          flow_version_ids: [preSelected.versionId],
        });
        updateDetectedEnvVars(result.variables ?? []);
      } catch {
        setErrorData({
          title: "Could not auto-detect environment variables",
          list: ["Add them manually in the connection form."],
        });
      }
    };
    detect();
  }, []);

  const { data: versionResponse, isLoading: isLoadingVersions } =
    useGetFlowVersions(
      { flowId: effectiveFlowId ?? "" },
      { enabled: !!effectiveFlowId },
    );
  const versions = versionResponse?.entries ?? [];

  const selectedFlow = flows.find((f) => f.id === effectiveFlowId);

  const handleAttachFlow = useCallback(
    async (versionId: string) => {
      if (!effectiveFlowId) return;
      const version = versions.find((v) => v.id === versionId);
      // Don't commit to context yet — wait for connection step to complete.
      setPendingAttachment({
        flowId: effectiveFlowId,
        versionId,
        versionTag: version?.version_tag ?? "",
      });
      setRightPanel("connections");
      initConnectionsForFlow(effectiveFlowId);

      // Auto-detect global variable references via the backend detection endpoint
      try {
        const result = await detectEnvVars({
          flow_version_ids: [versionId],
        });
        updateDetectedEnvVars(result.variables ?? []);
      } catch {
        updateDetectedEnvVars([]);
        setErrorData({
          title: "Could not auto-detect environment variables",
          list: ["Add them manually in the connection form."],
        });
      }
    },
    [
      effectiveFlowId,
      versions,
      detectEnvVars,
      setErrorData,
      initConnectionsForFlow,
      updateDetectedEnvVars,
    ],
  );

  const handleDetachFlow = useCallback(
    (flowId: string) => {
      handleRemoveAttachedFlow(flowId);
      setToolNameByFlow((prev) => {
        const next = new Map(prev);
        next.delete(flowId);
        return next;
      });
      // Reset right panel to versions if we're currently viewing the detached flow
      setRightPanel("versions");
    },
    [handleRemoveAttachedFlow, setToolNameByFlow],
  );

  const handleSelectFlow = useCallback(
    (flowId: string) => {
      setSelectedFlowId(flowId);
      setRightPanel("versions");
      setSelectedConnections(new Set());
    },
    [setSelectedConnections],
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 py-3">
      <h2 className="text-lg font-semibold">Attach Flows</h2>

      <div className="flex min-h-0 flex-1 overflow-hidden rounded-xl border border-border">
        <FlowListPanel
          flows={flows}
          selectedFlowId={effectiveFlowId}
          selectedVersionByFlow={selectedVersionByFlow}
          attachedConnectionByFlow={attachedConnectionByFlow}
          connections={connections}
          removedFlowIds={isEditMode ? removedFlowIds : undefined}
          onSelectFlow={handleSelectFlow}
          onRemoveFlow={handleDetachFlow}
          onUndoRemoveFlow={isEditMode ? handleUndoRemoveFlow : undefined}
        />

        {/* Right panel */}
        <div className="flex min-w-0 flex-1 flex-col">
          {rightPanel === "versions" ? (
            <VersionPanel
              selectedFlow={selectedFlow}
              versions={versions}
              isLoadingVersions={isLoadingVersions}
              selectedVersionByFlow={selectedVersionByFlow}
              onAttach={handleAttachFlow}
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
