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
import type { ConnectionItem, EnvVarEntry } from "../types";
import type { ConnectionTab } from "./step-attach-flows-connection-panel";
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
  const [connectionTab, setConnectionTab] =
    useState<ConnectionTab>("available");
  const [selectedConnections, setSelectedConnections] = useState<Set<string>>(
    new Set(),
  );
  const [newConnectionName, setNewConnectionName] = useState("");
  const [envVars, setEnvVars] = useState<EnvVarEntry[]>(() => [
    { id: crypto.randomUUID(), key: "", value: "" },
  ]);
  const [detectedVarCount, setDetectedVarCount] = useState(0);

  const { mutateAsync: detectEnvVars } = usePostDetectEnvVars();
  const { data: globalVariables } = useGetGlobalVariables();
  const globalVariableOptions = (globalVariables ?? []).map((v) => v.name);

  // When a flow+version are pre-selected from outside (e.g., canvas deploy button),
  // auto-advance to the connections panel and detect env vars for the pre-selected version.
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
        const detected = result.variables ?? [];
        if (detected.length > 0) {
          setDetectedVarCount(detected.length);
          setEnvVars(
            detected.map((variableName) => ({
              id: crypto.randomUUID(),
              key: variableName,
              value: variableName,
              globalVar: true,
            })),
          );
        }
      } catch {
        setErrorData({
          title: "Could not auto-detect environment variables",
          list: ["Add them manually in the connection form."],
        });
      }
    };
    detect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isDuplicateConnectionName = useMemo(() => {
    const trimmed = newConnectionName.trim().toLowerCase();
    if (!trimmed) return false;
    return connections.some((c) => c.name.trim().toLowerCase() === trimmed);
  }, [newConnectionName, connections]);

  const effectiveFlowId = selectedFlowId ?? flows[0]?.id ?? null;

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
      setSelectedConnections(
        new Set(attachedConnectionByFlow.get(effectiveFlowId) ?? []),
      );
      // Default to "create" tab when there are no existing connections
      if (connections.length === 0) {
        setConnectionTab("create");
      }

      // Auto-detect global variable references via the backend detection endpoint
      try {
        const result = await detectEnvVars({
          flow_version_ids: [versionId],
        });
        const detected = result.variables ?? [];
        if (detected.length > 0) {
          setDetectedVarCount(detected.length);
          setEnvVars(
            detected.map((variableName) => ({
              id: crypto.randomUUID(),
              key: variableName,
              value: variableName,
              globalVar: true,
            })),
          );
        } else {
          setDetectedVarCount(0);
          setEnvVars([{ id: crypto.randomUUID(), key: "", value: "" }]);
        }
      } catch {
        setDetectedVarCount(0);
        setEnvVars([{ id: crypto.randomUUID(), key: "", value: "" }]);
        setErrorData({
          title: "Could not auto-detect environment variables",
          list: ["Add them manually in the connection form."],
        });
      }
    },
    [
      effectiveFlowId,
      versions,
      connections,
      detectEnvVars,
      attachedConnectionByFlow,
      setErrorData,
    ],
  );

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

  const handleAttachConnection = useCallback(() => {
    if (!effectiveFlowId) return;
    if (connectionTab === "available" && selectedConnections.size > 0) {
      commitPendingAttachment();
      onAttachConnection((prev) => {
        const next = new Map(prev);
        next.set(effectiveFlowId, Array.from(selectedConnections));
        return next;
      });
      setRightPanel("versions");
      setSelectedConnections(new Set());
    }
  }, [
    effectiveFlowId,
    connectionTab,
    selectedConnections,
    onAttachConnection,
    commitPendingAttachment,
  ]);

  const handleCreateConnection = useCallback(() => {
    const filteredVars = envVars.filter((v) => v.key.trim());
    const environmentVariables: Record<string, string> = {};
    const globalVarKeys = new Set<string>();
    for (const v of filteredVars) {
      const key = v.key.trim();
      environmentVariables[key] = v.value;
      if (v.globalVar) {
        globalVarKeys.add(key);
      }
    }
    const sanitizedId = newConnectionName
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "_")
      .replace(/[^a-z0-9_]/g, "");
    const newConn = {
      id: sanitizedId,
      name: newConnectionName.trim(),
      variableCount: filteredVars.length,
      isNew: true,
      environmentVariables,
      globalVarKeys,
    };
    setConnections((prev) => [...prev, newConn]);
    setSelectedConnections(
      (prev) => new Set([...Array.from(prev), newConn.id]),
    );
    setConnectionTab("available");
    setNewConnectionName("");
    setEnvVars([{ id: crypto.randomUUID(), key: "", value: "" }]);
  }, [envVars, newConnectionName, setConnections]);

  const handleSkipConnection = useCallback(() => {
    commitPendingAttachment();
    if (effectiveFlowId) {
      onAttachConnection((prev) => {
        const next = new Map(prev);
        next.delete(effectiveFlowId);
        return next;
      });
    }
    setRightPanel("versions");
    setSelectedConnections(new Set());
  }, [effectiveFlowId, onAttachConnection, commitPendingAttachment]);

  const handleChangeFlow = useCallback(() => {
    setPendingAttachment(null);
    setRightPanel("versions");
    setSelectedConnections(new Set());
    setDetectedVarCount(0);
    setEnvVars([{ id: crypto.randomUUID(), key: "", value: "" }]);
  }, []);

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

  const handleSelectFlow = useCallback((flowId: string) => {
    setSelectedFlowId(flowId);
    setRightPanel("versions");
    setSelectedConnections(new Set());
    setDetectedVarCount(0);
    setEnvVars([{ id: crypto.randomUUID(), key: "", value: "" }]);
  }, []);

  const handleAddEnvVar = useCallback(() => {
    setEnvVars((prev) => [
      ...prev,
      { id: crypto.randomUUID(), key: "", value: "" },
    ]);
  }, []);

  const handleEnvVarChange = useCallback(
    (id: string, field: "key" | "value", val: string) => {
      setEnvVars((prev) =>
        prev.map((item) =>
          item.id === id ? { ...item, [field]: val, globalVar: false } : item,
        ),
      );
    },
    [],
  );

  const handleEnvVarSelectGlobalVar = useCallback(
    (id: string, selected: string) => {
      setEnvVars((prev) =>
        prev.map((item) =>
          item.id === id
            ? {
                ...item,
                key:
                  selected !== "" &&
                  (item.key.trim() === "" ||
                    (item.globalVar && item.key === item.value))
                    ? selected
                    : item.key,
                value: selected,
                globalVar: selected !== "",
              }
            : item,
        ),
      );
    },
    [],
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
