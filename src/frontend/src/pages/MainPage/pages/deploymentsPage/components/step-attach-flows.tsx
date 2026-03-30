import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { usePostDetectDeploymentEnvVars } from "@/controllers/API/queries/deployments";
import { useGetFlowVersions } from "@/controllers/API/queries/flow-version/use-get-flow-versions";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import { useFolderStore } from "@/stores/foldersStore";
import type { FlowType } from "@/types/flow";
import type { FlowVersionEntry } from "@/types/flow/version";
import { cn } from "@/utils/utils";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";
import type { ConnectionItem } from "../types";
import { CheckboxSelectItem, RadioSelectItem } from "./radio-select-item";

type RightPanelView = "versions" | "connections";
type ConnectionTab = "available" | "create";

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
  const [envVars, setEnvVars] = useState<
    { id: string; key: string; value: string; globalVar?: boolean }[]
  >([{ id: crypto.randomUUID(), key: "", value: "" }]);
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
    const newConn: ConnectionItem = {
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

  const getVersionLabel = (flowId: string) => {
    const entry = selectedVersionByFlow.get(flowId);
    if (!entry) return null;
    return entry.versionTag || null;
  };

  const isFlowAttached = (flowId: string) =>
    attachedConnectionByFlow.has(flowId);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 py-3">
      <h2 className="text-lg font-semibold">Attach Flows</h2>

      <div className="flex min-h-0 flex-1 overflow-hidden rounded-xl border border-border">
        {/* Left panel — flow list */}
        <div className="flex w-[280px] flex-shrink-0 flex-col border-r border-border">
          <div className="border-b border-border p-4 text-sm text-muted-foreground">
            Available Flows
          </div>
          <div className="flex-1 space-y-1 overflow-y-auto p-2">
            {flows.map((flow) => {
              const versionLabel = getVersionLabel(flow.id);
              const attached = isFlowAttached(flow.id);
              return (
                <button
                  key={flow.id}
                  type="button"
                  data-testid={`flow-item-${flow.id}`}
                  onClick={() => handleSelectFlow(flow.id)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors",
                    selectedFlowId === flow.id
                      ? "bg-muted"
                      : "hover:bg-muted/60",
                  )}
                >
                  <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-border bg-muted">
                    <ForwardedIconComponent
                      name={flow.icon ?? "Workflow"}
                      className="h-4 w-4 text-muted-foreground"
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="truncate text-sm font-semibold">
                        {flow.name}
                      </span>
                      {versionLabel && (
                        <Badge
                          variant="secondaryStatic"
                          size="tag"
                          className="bg-accent-purple-muted text-accent-purple-muted-foreground"
                        >
                          {versionLabel}
                        </Badge>
                      )}
                      {attached && (
                        <Badge
                          variant="secondaryStatic"
                          size="tag"
                          className="bg-accent-blue-muted text-accent-blue-muted-foreground"
                        >
                          ATTACHED
                        </Badge>
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

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

/* ── Version selection panel ── */

function VersionPanel({
  selectedFlow,
  versions,
  isLoadingVersions,
  pendingVersion,
  selectedVersionByFlow,
  attachedConnectionByFlow,
  onSelectPending,
  onAttach,
}: {
  selectedFlow: FlowType | undefined;
  versions: FlowVersionEntry[];
  isLoadingVersions: boolean;
  pendingVersion: string | null;
  selectedVersionByFlow: Map<string, { versionId: string; versionTag: string }>;
  attachedConnectionByFlow: Map<string, string[]>;
  onSelectPending: (id: string) => void;
  onAttach: () => void;
}) {
  if (!selectedFlow) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        Select a flow to see versions
      </div>
    );
  }

  const attachedEntry = selectedVersionByFlow.get(selectedFlow.id);
  const hasConnection = attachedConnectionByFlow.has(selectedFlow.id);

  return (
    <>
      <div className="border-b border-border p-4 text-sm text-muted-foreground">
        Select a version to attach to this deployment
      </div>
      <div className="flex flex-1 flex-col overflow-hidden px-4 py-2">
        <h3 className="py-2 text-lg font-semibold">{selectedFlow.name}</h3>
        <div
          className="flex-1 space-y-3 overflow-y-auto py-3"
          role="radiogroup"
          aria-label="Flow versions"
        >
          {isLoadingVersions ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              Loading versions...
            </div>
          ) : versions.length === 0 ? (
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              No versions found
            </div>
          ) : (
            versions.map((version) => {
              const isAttachedVersion = attachedEntry?.versionId === version.id;
              const isSelected = pendingVersion === version.id;
              return (
                <RadioSelectItem
                  key={version.id}
                  name="flow-version"
                  value={version.id}
                  selected={isSelected}
                  onChange={() => onSelectPending(version.id)}
                  data-testid={`version-item-${version.id}`}
                >
                  <span className="flex flex-col">
                    <span className="flex items-center gap-2 text-sm font-medium leading-tight">
                      {version.version_tag}
                      {isAttachedVersion && hasConnection && (
                        <Badge
                          variant="secondaryStatic"
                          size="tag"
                          className="bg-accent-blue-muted text-accent-blue-muted-foreground"
                        >
                          ATTACHED
                        </Badge>
                      )}
                    </span>
                    <span className="text-sm leading-tight text-muted-foreground">
                      Created:{" "}
                      {new Date(version.created_at).toLocaleDateString()}
                    </span>
                  </span>
                </RadioSelectItem>
              );
            })
          )}
        </div>
        <Button
          className="w-full"
          disabled={!pendingVersion}
          onClick={onAttach}
        >
          Attach Flow
        </Button>
      </div>
    </>
  );
}

/* ── Connection panel (after attaching a flow) ── */

function ConnectionPanel({
  connectionTab,
  onTabChange,
  connections,
  selectedConnections,
  onToggleConnection,
  newConnectionName,
  onNameChange,
  newConnectionDescription,
  onDescriptionChange,
  envVars,
  detectedVarCount,
  globalVariableOptions,
  onEnvVarChange,
  onEnvVarSelectGlobalVar,
  onAddEnvVar,
  onChangeFlow,
  onAttachConnection,
  onCreateConnection,
}: {
  connectionTab: ConnectionTab;
  onTabChange: (tab: ConnectionTab) => void;
  connections: ConnectionItem[];
  selectedConnections: Set<string>;
  onToggleConnection: (id: string) => void;
  newConnectionName: string;
  onNameChange: (v: string) => void;
  newConnectionDescription: string;
  onDescriptionChange: (v: string) => void;
  envVars: { id: string; key: string; value: string; globalVar?: boolean }[];
  detectedVarCount: number;
  globalVariableOptions: string[];
  onEnvVarChange: (id: string, field: "key" | "value", val: string) => void;
  onEnvVarSelectGlobalVar: (id: string, selected: string) => void;
  onAddEnvVar: () => void;
  onChangeFlow: () => void;
  onAttachConnection: () => void;
  onCreateConnection: () => void;
}) {
  return (
    <>
      <div className="border-b border-border p-4 text-sm text-muted-foreground">
        Select or Create New Connection
      </div>
      <div className="flex flex-1 flex-col overflow-hidden px-4 py-4">
        {/* Tab toggle */}
        <div className="rounded-xl border border-border bg-muted p-1">
          <div className="grid grid-cols-2">
            {(["available", "create"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => onTabChange(tab)}
                className={cn(
                  "rounded-lg py-2 text-sm transition-colors",
                  connectionTab === tab
                    ? "bg-background"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {tab === "available"
                  ? "Available Connections"
                  : "Create Connection"}
              </button>
            ))}
          </div>
        </div>

        {/* Tab content */}
        <div className="mt-4 flex-1 overflow-y-auto">
          {connectionTab === "available" ? (
            <div className="space-y-3">
              {connections.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
                  <ForwardedIconComponent
                    name="PlugZap"
                    className="h-8 w-8 text-muted-foreground/50"
                  />
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      No connections yet
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground/70">
                      Create a connection to attach credentials to this flow.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onTabChange("create")}
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    Create your first connection
                  </button>
                </div>
              ) : (
                connections.map((conn) => (
                  <CheckboxSelectItem
                    key={conn.id}
                    value={conn.id}
                    checked={selectedConnections.has(conn.id)}
                    onChange={() => onToggleConnection(conn.id)}
                    data-testid={`connection-item-${conn.id}`}
                  >
                    <span className="flex flex-col">
                      <span className="text-sm font-medium leading-tight">
                        {conn.name}
                      </span>
                      <span className="text-sm leading-tight text-muted-foreground">
                        {conn.variableCount} variables
                      </span>
                    </span>
                  </CheckboxSelectItem>
                ))
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="flex flex-col">
                <span className="pb-2 text-sm font-medium">
                  Connection Name<span className="text-destructive">*</span>
                </span>
                <Input
                  placeholder="e.g., SALES_BOT_PROD"
                  className="bg-muted"
                  value={newConnectionName}
                  onChange={(e) => onNameChange(e.target.value)}
                />
              </div>
              <div className="flex flex-col">
                <span className="pb-2 text-sm font-medium">Description</span>
                <Input
                  placeholder="e.g., Production sales bot connection"
                  className="bg-muted"
                  value={newConnectionDescription}
                  onChange={(e) => onDescriptionChange(e.target.value)}
                />
              </div>
              <div className="flex flex-col">
                <span className="pb-2 text-sm font-medium">
                  Environment Variables
                  <span className="text-destructive">*</span>
                </span>
                {detectedVarCount > 0 && (
                  <p className="mb-2 text-xs text-muted-foreground">
                    {detectedVarCount} variable
                    {detectedVarCount > 1 ? "s" : ""} auto-detected from the
                    selected flow version.
                  </p>
                )}
                <div className="space-y-2">
                  {envVars.map((envVar) => (
                    <div key={envVar.id} className="grid grid-cols-2 gap-2">
                      <Input
                        placeholder="Key"
                        className="bg-muted"
                        value={envVar.key}
                        onChange={(e) =>
                          onEnvVarChange(envVar.id, "key", e.target.value)
                        }
                      />
                      <InputComponent
                        nodeStyle
                        password
                        id={`env-val-${envVar.id}`}
                        placeholder="Value"
                        value={envVar.value}
                        options={globalVariableOptions}
                        optionsPlaceholder="Global Variables"
                        optionsIcon="Globe"
                        selectedOption={envVar.globalVar ? envVar.value : ""}
                        setSelectedOption={(sel) =>
                          onEnvVarSelectGlobalVar(envVar.id, sel)
                        }
                        onChange={(text) =>
                          onEnvVarChange(envVar.id, "value", text)
                        }
                      />
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={onAddEnvVar}
                    className="text-sm text-muted-foreground hover:text-foreground"
                  >
                    + Add variable
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer buttons */}
        <div className="flex items-center gap-3 pt-4">
          <Button variant="outline" onClick={onChangeFlow}>
            Change Flow
          </Button>
          {connectionTab === "available" ? (
            <Button
              className="flex-1"
              disabled={selectedConnections.size === 0}
              onClick={onAttachConnection}
            >
              Attach Connection to Flow
            </Button>
          ) : (
            <Button
              className="flex-1"
              disabled={newConnectionName.trim() === ""}
              onClick={onCreateConnection}
            >
              Create Connection
            </Button>
          )}
        </div>
      </div>
    </>
  );
}
