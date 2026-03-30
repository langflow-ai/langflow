import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { usePostDetectDeploymentEnvVars } from "@/controllers/API/queries/deployments";
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
    connections,
    setConnections,
    selectedVersionByFlow,
    handleSelectVersion: onSelectVersion,
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
      (f) => !f.is_component && f.folder_id === currentFolderId,
    );
  }, [flowsData, currentFolderId]);
  // TODO: replace with real API data

  const [selectedFlowId, setSelectedFlowId] = useState<string | null>(null);
  const [pendingVersion, setPendingVersion] = useState<string | null>(null);
  const [rightPanel, setRightPanel] = useState<RightPanelView>("versions");
  const [connectionTab, setConnectionTab] =
    useState<ConnectionTab>("available");
  const [selectedConnections, setSelectedConnections] = useState<Set<string>>(
    new Set(),
  );
  const [newConnectionName, setNewConnectionName] = useState("");
  const [newConnectionDescription, setNewConnectionDescription] = useState("");
  const [envVars, setEnvVars] = useState<EnvVarEntry[]>([
    { id: crypto.randomUUID(), key: "", value: "" },
  ]);
  const [detectedVarCount, setDetectedVarCount] = useState(0);
  const { mutateAsync: detectEnvVars } = usePostDetectDeploymentEnvVars();
  const { data: globalVariables } = useGetGlobalVariables();
  const globalVariableOptions = (globalVariables ?? []).map((v) => v.name);

  useEffect(() => {
    if (!selectedFlowId && flows.length > 0) {
      setSelectedFlowId(flows[0].id);
    }
  }, [flows, selectedFlowId]);

  const { data: versionResponse, isLoading: isLoadingVersions } =
    useGetFlowVersions(
      { flowId: selectedFlowId! },
      { enabled: !!selectedFlowId },
    );
  const versions = versionResponse?.entries ?? [];

  const selectedFlow = flows.find((f) => f.id === selectedFlowId);

  const handleAttachFlow = async () => {
    if (selectedFlowId && pendingVersion) {
      const version = versions.find((v) => v.id === pendingVersion);
      onSelectVersion(
        selectedFlowId,
        pendingVersion,
        version?.version_tag ?? "",
      );
      setPendingVersion(null);
      setRightPanel("connections");
      setSelectedConnections(
        new Set(attachedConnectionByFlow.get(selectedFlowId) ?? []),
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
  };

  const handleAttachConnection = () => {
    if (!selectedFlowId) return;
    if (connectionTab === "available" && selectedConnections.size > 0) {
      onAttachConnection((prev) => {
        const next = new Map(prev);
        next.set(selectedFlowId, Array.from(selectedConnections));
        return next;
      });
      setRightPanel("versions");
      setSelectedConnections(new Set());
    }
  };

  const handleCreateConnection = () => {
    const filteredVars = envVars.filter((v) => v.key.trim());
    const environmentVariables: Record<string, string> = {};
    for (const v of filteredVars) {
      environmentVariables[v.key.trim()] = v.value;
    }
    const newConn = {
      id: `conn_${crypto.randomUUID().replace(/-/g, "_")}`,
      name: newConnectionName.trim(),
      variableCount: filteredVars.length,
      isNew: true,
      environmentVariables,
    };
    setConnections((prev) => [...prev, newConn]);
    setSelectedConnections(
      (prev) => new Set([...Array.from(prev), newConn.id]),
    );
    setConnectionTab("available");
    setNewConnectionName("");
    setNewConnectionDescription("");
    setEnvVars([{ id: crypto.randomUUID(), key: "", value: "" }]);
  };

  const handleChangeFlow = () => {
    setRightPanel("versions");
    setSelectedConnections(new Set());
    setDetectedVarCount(0);
    setEnvVars([{ id: crypto.randomUUID(), key: "", value: "" }]);
  };

  const handleSelectFlow = (flowId: string) => {
    setSelectedFlowId(flowId);
    setPendingVersion(null);
    setRightPanel("versions");
    setSelectedConnections(new Set());
    setDetectedVarCount(0);
    setEnvVars([{ id: crypto.randomUUID(), key: "", value: "" }]);
  };

  const handleAddEnvVar = () => {
    setEnvVars([...envVars, { id: crypto.randomUUID(), key: "", value: "" }]);
  };

  const handleEnvVarChange = (
    id: string,
    field: "key" | "value",
    val: string,
  ) => {
    setEnvVars((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, [field]: val, globalVar: false } : item,
      ),
    );
  };

  const handleEnvVarSelectGlobalVar = (id: string, selected: string) => {
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
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 py-3">
      <h2 className="text-lg font-semibold">Attach Flows</h2>

      <div className="flex min-h-0 flex-1 overflow-hidden rounded-xl border border-border">
        <FlowListPanel
          flows={flows}
          selectedFlowId={selectedFlowId}
          selectedVersionByFlow={selectedVersionByFlow}
          attachedConnectionByFlow={attachedConnectionByFlow}
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
              attachedConnectionByFlow={attachedConnectionByFlow}
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
              onAttachConnection={handleAttachConnection}
              onCreateConnection={handleCreateConnection}
            />
          )}
        </div>
      </div>
    </div>
  );
}
