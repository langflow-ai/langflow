import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useMemo,
  useState,
} from "react";
import type { ConnectionTab } from "../components/step-attach-flows-connection-panel";
import type { ConnectionItem, EnvVarEntry } from "../types";

interface UseConnectionPanelStateParams {
  connections: ConnectionItem[];
  setConnections: Dispatch<SetStateAction<ConnectionItem[]>>;
  effectiveFlowId: string | null;
  attachedConnectionByFlow: Map<string, string[]>;
  onAttachConnection: Dispatch<SetStateAction<Map<string, string[]>>>;
  commitPendingAttachment: () => void;
  resetPendingAttachment: () => void;
  setRightPanel: (panel: "versions" | "connections") => void;
}

export function useConnectionPanelState({
  connections,
  setConnections,
  effectiveFlowId,
  attachedConnectionByFlow,
  onAttachConnection,
  commitPendingAttachment,
  resetPendingAttachment,
  setRightPanel,
}: UseConnectionPanelStateParams) {
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

  const isDuplicateConnectionName = useMemo(() => {
    const trimmed = newConnectionName.trim().toLowerCase();
    if (!trimmed) return false;
    return connections.some((c) => c.name.trim().toLowerCase() === trimmed);
  }, [newConnectionName, connections]);

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
    setRightPanel,
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
    const newConn: ConnectionItem = {
      id: sanitizedId,
      connectionId: sanitizedId,
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
  }, [
    effectiveFlowId,
    onAttachConnection,
    commitPendingAttachment,
    setRightPanel,
  ]);

  const handleChangeFlow = useCallback(() => {
    resetPendingAttachment();
    setRightPanel("versions");
    setSelectedConnections(new Set());
    setDetectedVarCount(0);
    setEnvVars([{ id: crypto.randomUUID(), key: "", value: "" }]);
  }, [resetPendingAttachment, setRightPanel]);

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

  const initConnectionsForFlow = useCallback(
    (flowId: string) => {
      setSelectedConnections(
        new Set(attachedConnectionByFlow.get(flowId) ?? []),
      );
      if (connections.length === 0) {
        setConnectionTab("create");
      }
    },
    [attachedConnectionByFlow, connections.length],
  );

  const updateDetectedEnvVars = useCallback((names: string[]) => {
    if (names.length > 0) {
      setDetectedVarCount(names.length);
      setEnvVars(
        names.map((name) => ({
          id: crypto.randomUUID(),
          key: name,
          value: name,
          globalVar: true,
        })),
      );
    } else {
      setDetectedVarCount(0);
      setEnvVars([{ id: crypto.randomUUID(), key: "", value: "" }]);
    }
  }, []);

  return {
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
  };
}
