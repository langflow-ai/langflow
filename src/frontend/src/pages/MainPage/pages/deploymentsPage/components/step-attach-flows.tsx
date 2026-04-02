import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { usePostDetectDeploymentEnvVars } from "@/controllers/API/queries/deployments/use-post-detect-deployment-env-vars";
import { useGetFlowVersions } from "@/controllers/API/queries/flow-version/use-get-flow-versions";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import useAlertStore from "@/stores/alertStore";
import { useFolderStore } from "@/stores/foldersStore";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";
import type { EnvVarEntry } from "../types";
import type { ConnectionTab } from "./step-attach-flows-connection-panel";
import { ConnectionPanel } from "./step-attach-flows-connection-panel";
import { FlowListPanel } from "./step-attach-flows-flow-list-panel";
import { VersionPanel } from "./step-attach-flows-version-panel";

type RightPanelView = "versions" | "connections";

export default function StepAttachFlows() {
  const {
    initialFlowId,
    connections,
    setConnections,
    selectedVersionByFlow,
    handleSelectVersion: onSelectVersion,
    toolNameByFlow,
    setToolNameByFlow,
    attachedConnectionByFlow,
    setAttachedConnectionByFlow: onAttachConnection,
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
    return list.filter(
      (f) =>
        !f.is_component &&
        (f.folder_id === currentFolderId || f.id === initialFlowId),
    );
  }, [flowsData, currentFolderId, initialFlowId]);
  // TODO: replace with real API data

  const [selectedFlowId, setSelectedFlowId] = useState<string | null>(
    initialFlowId ?? null,
  );
  const [pendingVersion, setPendingVersion] = useState<string | null>(null);
  const [rightPanel, setRightPanel] = useState<RightPanelView>("versions");
  const [connectionTab, setConnectionTab] =
    useState<ConnectionTab>("available");
  const [selectedConnections, setSelectedConnections] = useState<Set<string>>(
    new Set(),
  );
  const [newConnectionName, setNewConnectionName] = useState("");
  const [newConnectionDescription, setNewConnectionDescription] = useState("");
  const [envVars, setEnvVars] = useState<EnvVarEntry[]>(() => [
    { id: crypto.randomUUID(), key: "", value: "" },
  ]);
  const [detectedVarCount, setDetectedVarCount] = useState(0);
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
          reference_ids: [preSelected.versionId],
        });
        const detected = result.variables ?? [];
        if (detected.length > 0) {
          setDetectedVarCount(detected.length);
          setEnvVars(
            detected.map((v) => ({
              id: crypto.randomUUID(),
              key: v.key,
              value: v.global_variable_name ?? "",
              globalVar: Boolean(v.global_variable_name),
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

  const { mutateAsync: detectEnvVars } = usePostDetectDeploymentEnvVars();
  const { data: globalVariables } = useGetGlobalVariables();
  const globalVariableOptions = (globalVariables ?? []).map((v) => v.name);

  const effectiveFlowId = selectedFlowId ?? flows[0]?.id ?? null;

  const { data: versionResponse, isLoading: isLoadingVersions } =
    useGetFlowVersions(
      { flowId: effectiveFlowId ?? "" },
      { enabled: !!effectiveFlowId },
    );
  const versions = versionResponse?.entries ?? [];

  const selectedFlow = flows.find((f) => f.id === effectiveFlowId);

  const handleAttachFlow = useCallback(async () => {
    if (effectiveFlowId && pendingVersion) {
      const version = versions.find((v) => v.id === pendingVersion);
      onSelectVersion(
        effectiveFlowId,
        pendingVersion,
        version?.version_tag ?? "",
      );
      setPendingVersion(null);
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
        const result = await detectEnvVars({ reference_ids: [pendingVersion] });
        const detected = result.variables ?? [];
        if (detected.length > 0) {
          setDetectedVarCount(detected.length);
          setEnvVars(
            detected.map((v) => ({
              id: crypto.randomUUID(),
              key: v.key,
              value: v.global_variable_name ?? "",
              globalVar: Boolean(v.global_variable_name),
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
    }
  }, [
    effectiveFlowId,
    pendingVersion,
    versions,
    connections,
    detectEnvVars,
    onSelectVersion,
    attachedConnectionByFlow,
    setErrorData,
  ]);

  const handleAttachConnection = useCallback(() => {
    if (!effectiveFlowId) return;
    if (connectionTab === "available" && selectedConnections.size > 0) {
      onAttachConnection((prev) => {
        const next = new Map(prev);
        next.set(effectiveFlowId, Array.from(selectedConnections));
        return next;
      });
      setRightPanel("versions");
      setSelectedConnections(new Set());
    }
  }, [effectiveFlowId, connectionTab, selectedConnections, onAttachConnection]);

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
    const newConn = {
      id: `conn_${crypto.randomUUID().replace(/-/g, "_")}`,
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
    setNewConnectionDescription("");
    setEnvVars([{ id: crypto.randomUUID(), key: "", value: "" }]);
  }, [envVars, newConnectionName, setConnections]);

  const handleSkipConnection = useCallback(() => {
    if (effectiveFlowId) {
      onAttachConnection((prev) => {
        const next = new Map(prev);
        next.delete(effectiveFlowId);
        return next;
      });
    }
    setRightPanel("versions");
    setSelectedConnections(new Set());
  }, [effectiveFlowId, onAttachConnection]);

  const handleChangeFlow = useCallback(() => {
    setRightPanel("versions");
    setSelectedConnections(new Set());
    setDetectedVarCount(0);
    setEnvVars([{ id: crypto.randomUUID(), key: "", value: "" }]);
  }, []);

  const handleSelectFlow = useCallback((flowId: string) => {
    setSelectedFlowId(flowId);
    setPendingVersion(null);
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
          onSelectFlow={handleSelectFlow}
        />

        {/* Right panel */}
        <div className="flex flex-1 flex-col">
          {rightPanel === "versions" ? (
            <VersionPanel
              selectedFlow={selectedFlow}
              versions={versions}
              isLoadingVersions={isLoadingVersions}
              pendingVersion={pendingVersion}
              selectedVersionByFlow={selectedVersionByFlow}
              toolName={
                effectiveFlowId
                  ? toolNameByFlow.get(effectiveFlowId) ?? ""
                  : ""
              }
              onToolNameChange={(name) => {
                if (effectiveFlowId) {
                  setToolNameByFlow((prev) => {
                    const next = new Map(prev);
                    if (name) {
                      next.set(effectiveFlowId, name);
                    } else {
                      next.delete(effectiveFlowId);
                    }
                    return next;
                  });
                }
              }}
              onSelectPending={setPendingVersion}
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
              newConnectionDescription={newConnectionDescription}
              onDescriptionChange={setNewConnectionDescription}
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
            />
          )}
        </div>
      </div>
    </div>
  );
}
