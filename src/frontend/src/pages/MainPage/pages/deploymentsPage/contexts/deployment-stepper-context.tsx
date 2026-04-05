import {
  createContext,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import type { ProviderAccountCreateRequest } from "@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account";
import type { DeploymentCreateRequest } from "@/controllers/API/queries/deployments/use-post-deployment";
import type { DeploymentUpdateRequest } from "@/controllers/API/queries/deployments/use-patch-deployment";
import type {
  ConnectionItem,
  Deployment,
  DeploymentProvider,
  DeploymentType,
  ProviderAccount,
  ProviderCredentials,
} from "../types";

interface DeploymentStepperInitialState {
  selectedVersionByFlow?: Map<
    string,
    { versionId: string; versionTag: string }
  >;
  initialFlowId?: string;
  initialProvider?: DeploymentProvider;
  initialInstance?: ProviderAccount;
  initialStep?: number;
  /** When provided, the stepper opens in edit mode. */
  editingDeployment?: Deployment;
  /** Pre-populated initial LLM from provider (edit mode). */
  initialLlm?: string;
  /** Pre-populated tool names from provider (edit mode). Key = flowId. */
  initialToolNameByFlow?: Map<string, string>;
  /** Pre-populated connection bindings from provider (edit mode). Key = flowId. */
  initialConnectionsByFlow?: Map<string, string[]>;
}

interface DeploymentStepperContextType {
  // Mode
  isEditMode: boolean;
  editingDeployment: Deployment | null;

  // Navigation
  currentStep: number;
  totalSteps: number;
  minStep: number;
  canGoNext: boolean;
  handleNext: () => void;
  handleBack: () => void;

  // Step 1: Provider (create mode only)
  selectedProvider: DeploymentProvider | null;
  setSelectedProvider: (provider: DeploymentProvider) => void;
  selectedInstance: ProviderAccount | null;
  setSelectedInstance: (instance: ProviderAccount | null) => void;
  credentials: ProviderCredentials;
  setCredentials: (credentials: ProviderCredentials) => void;

  // Step 2: Type
  deploymentType: DeploymentType;
  setDeploymentType: (type: DeploymentType) => void;
  deploymentName: string;
  setDeploymentName: (name: string) => void;
  deploymentDescription: string;
  setDeploymentDescription: (description: string) => void;
  selectedLlm: string;
  setSelectedLlm: (llm: string) => void;

  // Step 3: Attach Flows
  initialFlowId: string | null;
  connections: ConnectionItem[];
  setConnections: Dispatch<SetStateAction<ConnectionItem[]>>;
  selectedVersionByFlow: Map<string, { versionId: string; versionTag: string }>;
  handleSelectVersion: (
    flowId: string,
    versionId: string,
    versionTag: string,
  ) => void;
  attachedConnectionByFlow: Map<string, string[]>;
  setAttachedConnectionByFlow: Dispatch<SetStateAction<Map<string, string[]>>>;
  /** User-provided tool names per flow. Key = flowId. */
  toolNameByFlow: Map<string, string>;
  setToolNameByFlow: Dispatch<SetStateAction<Map<string, string>>>;
  /** Flow IDs that were already attached before this edit session (edit mode). */
  preExistingFlowIds: Set<string>;
  /** Flow IDs that were originally attached but the user chose to detach (edit mode). */
  removedFlowIds: Set<string>;
  handleRemoveAttachedFlow: (flowId: string) => void;
  handleUndoRemoveFlow: (flowId: string) => void;

  // Deploy / Update
  needsProviderAccountCreation: boolean;
  buildProviderAccountPayload: () => ProviderAccountCreateRequest | null;
  buildDeploymentPayload: (providerId: string) => DeploymentCreateRequest;
  buildDeploymentUpdatePayload: () => DeploymentUpdateRequest;
}

const DeploymentStepperContext =
  createContext<DeploymentStepperContextType | null>(null);

export function DeploymentStepperProvider({
  children,
  initialState,
}: {
  children: ReactNode;
  initialState?: DeploymentStepperInitialState;
}) {
  const editingDeployment = initialState?.editingDeployment ?? null;
  const isEditMode = editingDeployment !== null;

  // In edit mode: 3 steps (Type → Attach → Review), skip Provider.
  const totalSteps = isEditMode ? 3 : 4;
  const minStep = initialState?.initialStep ?? 1;
  const [currentStep, setCurrentStep] = useState(minStep);

  const [selectedProvider, setSelectedProviderState] =
    useState<DeploymentProvider | null>(initialState?.initialProvider ?? null);
  const [selectedInstance, setSelectedInstance] =
    useState<ProviderAccount | null>(initialState?.initialInstance ?? null);
  const [credentials, setCredentials] = useState<ProviderCredentials>({
    name: "",
    provider_key: "",
    provider_url: "",
    api_key: "",
  });

  // Pre-fill from editing deployment when in edit mode.
  const [deploymentType, setDeploymentType] = useState<DeploymentType>(
    editingDeployment?.type ?? "agent",
  );
  const [deploymentName, setDeploymentName] = useState(
    editingDeployment?.name ?? "",
  );
  const [deploymentDescription, setDeploymentDescription] = useState(
    editingDeployment?.description ?? "",
  );
  const [selectedLlm, setSelectedLlm] = useState(
    initialState?.initialLlm ?? "",
  );

  const [selectedVersionByFlow, setSelectedVersionByFlow] = useState<
    Map<string, { versionId: string; versionTag: string }>
  >(initialState?.selectedVersionByFlow ?? new Map());
  const [connections, setConnections] = useState<ConnectionItem[]>([]);
  const [toolNameByFlow, setToolNameByFlow] = useState<Map<string, string>>(
    initialState?.initialToolNameByFlow ?? new Map(),
  );
  const [attachedConnectionByFlow, setAttachedConnectionByFlow] = useState<
    Map<string, string[]>
  >(initialState?.initialConnectionsByFlow ?? new Map());

  // Edit mode: track which pre-existing flows the user wants to detach.
  const [removedFlowIds, setRemovedFlowIds] = useState<Set<string>>(new Set());
  // Cache removed flow data so undo can restore it.
  const initialVersionByFlow = useMemo(
    () => initialState?.selectedVersionByFlow ?? new Map(),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
  const preExistingFlowIds = useMemo(
    () => new Set(initialVersionByFlow.keys()),
    [initialVersionByFlow],
  );
  const initialToolNameByFlow = useMemo(
    () => initialState?.initialToolNameByFlow ?? new Map<string, string>(),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const handleRemoveAttachedFlow = useCallback((flowId: string) => {
    setRemovedFlowIds((prev) => new Set([...Array.from(prev), flowId]));
    setSelectedVersionByFlow((prev) => {
      const next = new Map(prev);
      next.delete(flowId);
      return next;
    });
    setAttachedConnectionByFlow((prev) => {
      const next = new Map(prev);
      next.delete(flowId);
      return next;
    });
  }, []);

  const handleUndoRemoveFlow = useCallback(
    (flowId: string) => {
      setRemovedFlowIds((prev) => {
        const next = new Set(prev);
        next.delete(flowId);
        return next;
      });
      const originalVersion = initialVersionByFlow.get(flowId);
      if (originalVersion) {
        setSelectedVersionByFlow((prev) => {
          const next = new Map(prev);
          next.set(flowId, originalVersion);
          return next;
        });
      }
    },
    [initialVersionByFlow],
  );

  const hasValidCredentials =
    credentials.name.trim() !== "" &&
    credentials.api_key.trim() !== "" &&
    credentials.provider_url.trim() !== "";

  // In edit mode, steps are shifted: 1=Type, 2=Attach, 3=Review.
  const getLogicalStep = useCallback(
    (step: number) => (isEditMode ? step + 1 : step),
    [isEditMode],
  );

  const canGoNext = useMemo(() => {
    const logical = getLogicalStep(currentStep);
    if (logical === 1) {
      return (
        selectedProvider !== null &&
        (selectedInstance !== null || hasValidCredentials)
      );
    }
    if (logical === 2) {
      return deploymentName.trim() !== "" && selectedLlm.trim() !== "";
    }
    if (logical === 3) {
      // In edit mode, user can proceed without new attachments (may just change desc/LLM).
      return isEditMode || selectedVersionByFlow.size > 0;
    }
    return true;
  }, [
    currentStep,
    getLogicalStep,
    selectedProvider,
    selectedInstance,
    hasValidCredentials,
    deploymentName,
    selectedLlm,
    selectedVersionByFlow,
    isEditMode,
  ]);

  const handleNext = useCallback(() => {
    setCurrentStep((prev) => (prev < totalSteps ? prev + 1 : prev));
  }, [totalSteps]);

  const handleBack = useCallback(() => {
    setCurrentStep((prev) => (prev > minStep ? prev - 1 : prev));
  }, [minStep]);

  const setSelectedProvider = useCallback((provider: DeploymentProvider) => {
    setSelectedProviderState(provider);
    setSelectedInstance(null);
    setCredentials({
      name: "",
      provider_key: "",
      provider_url: "",
      api_key: "",
    });
  }, []);

  const handleSelectVersion = useCallback(
    (flowId: string, versionId: string, versionTag: string) => {
      setSelectedVersionByFlow((prev) => {
        const next = new Map(prev);
        next.set(flowId, { versionId, versionTag });
        return next;
      });
    },
    [],
  );

  const needsProviderAccountCreation =
    selectedInstance === null && hasValidCredentials;

  const buildProviderAccountPayload =
    useCallback((): ProviderAccountCreateRequest | null => {
      if (!hasValidCredentials) return null;
      return {
        name: credentials.name.trim(),
        provider_key: "watsonx-orchestrate",
        provider_url: credentials.provider_url.trim(),
        provider_data: { api_key: credentials.api_key.trim() },
      };
    }, [credentials, hasValidCredentials]);

  const buildDeploymentPayload = useCallback(
    (providerId: string): DeploymentCreateRequest => {
      const allConnectionIds = new Set<string>();
      Array.from(attachedConnectionByFlow.values()).forEach((ids) => {
        ids.forEach((id) => allConnectionIds.add(id));
      });

      const rawPayloads: Array<{
        app_id: string;
        environment_variables: Record<
          string,
          { value: string; source: "raw" | "variable" }
        >;
      }> = [];

      Array.from(allConnectionIds).forEach((id) => {
        const conn = connections.find((c) => c.id === id);
        if (conn?.isNew) {
          const envVarsWrapped: Record<
            string,
            { value: string; source: "raw" | "variable" }
          > = {};
          Object.entries(conn.environmentVariables).forEach(([k, v]) => {
            const isGlobalVar = conn.globalVarKeys?.has(k) ?? false;
            envVarsWrapped[k] = {
              value: v,
              source: isGlobalVar ? "variable" : "raw",
            };
          });
          rawPayloads.push({
            app_id: id,
            environment_variables: envVarsWrapped,
          });
        }
      });

      const operations: DeploymentCreateRequest["provider_data"]["operations"] =
        [];
      for (const [flowId, versionEntry] of Array.from(selectedVersionByFlow)) {
        const connectionIds = attachedConnectionByFlow.get(flowId) ?? [];
        const customToolName = toolNameByFlow.get(flowId)?.trim();
        operations.push({
          op: "bind",
          flow_version_id: versionEntry.versionId,
          app_ids: connectionIds,
          ...(customToolName && { tool_name: customToolName }),
        });
      }

      return {
        provider_id: providerId,
        spec: {
          name: deploymentName,
          description: deploymentDescription,
          type: deploymentType,
        },
        provider_data: {
          llm: selectedLlm,
          operations,
          connections: {
            raw_payloads: rawPayloads,
          },
        },
      };
    },
    [
      attachedConnectionByFlow,
      connections,
      deploymentDescription,
      deploymentName,
      deploymentType,
      selectedLlm,
      selectedVersionByFlow,
      toolNameByFlow,
    ],
  );

  const buildDeploymentUpdatePayload =
    useCallback((): DeploymentUpdateRequest => {
      if (!editingDeployment) {
        throw new Error(
          "buildDeploymentUpdatePayload called outside edit mode",
        );
      }

      const result: DeploymentUpdateRequest = {
        deployment_id: editingDeployment.id,
      };

      // Spec changes (description only — name is not editable after creation).
      const descriptionChanged =
        deploymentDescription !== (editingDeployment.description ?? "");
      if (descriptionChanged) {
        result.spec = { description: deploymentDescription };
      }

      // Build provider_data with operations for attach/detach + LLM.
      const operations: Array<Record<string, unknown>> = [];

      // New flows attached during this edit session.
      for (const [flowId, versionEntry] of Array.from(selectedVersionByFlow)) {
        if (initialVersionByFlow.has(flowId)) continue; // pre-existing, skip
        const connectionIds = attachedConnectionByFlow.get(flowId) ?? [];
        const customToolName = toolNameByFlow.get(flowId)?.trim();
        operations.push({
          op: "bind",
          flow_version_id: versionEntry.versionId,
          app_ids: connectionIds,
          ...(customToolName && { tool_name: customToolName }),
        });
      }

      // Renamed tools on pre-existing flows.
      for (const [flowId, versionEntry] of Array.from(selectedVersionByFlow)) {
        if (!initialVersionByFlow.has(flowId)) continue; // new flow, handled above
        const currentName = toolNameByFlow.get(flowId)?.trim() ?? "";
        const originalName = initialToolNameByFlow.get(flowId)?.trim() ?? "";
        if (currentName && currentName !== originalName) {
          operations.push({
            op: "rename_tool",
            flow_version_id: versionEntry.versionId,
            tool_name: currentName,
          });
        }
      }

      // Detached flows.
      for (const flowId of Array.from(removedFlowIds)) {
        const originalVersion = initialVersionByFlow.get(flowId);
        if (originalVersion) {
          operations.push({
            op: "remove_tool",
            flow_version_id: originalVersion.versionId,
          });
        }
      }

      // Collect connection details for new binds.
      const newConnectionIds = new Set<string>();
      const bindFlowVersionIds = new Set(
        operations
          .filter((o) => o.op === "bind")
          .map((o) => o.flow_version_id as string),
      );
      for (const [flowId, connectionIds] of Array.from(
        attachedConnectionByFlow,
      )) {
        const versionEntry = selectedVersionByFlow.get(flowId);
        if (!versionEntry || !bindFlowVersionIds.has(versionEntry.versionId))
          continue;
        connectionIds.forEach((id) => newConnectionIds.add(id));
      }

      const rawPayloads: Array<{
        app_id: string;
        environment_variables: Record<
          string,
          { value: string; source: "raw" | "variable" }
        >;
      }> = [];

      Array.from(newConnectionIds).forEach((id) => {
        const conn = connections.find((c) => c.id === id);
        if (!conn?.isNew) return; // existing connections are referenced via bind op app_ids
        const envVarsWrapped: Record<
          string,
          { value: string; source: "raw" | "variable" }
        > = {};
        Object.entries(conn.environmentVariables).forEach(([k, v]) => {
          const isGlobalVar = conn.globalVarKeys?.has(k) ?? false;
          envVarsWrapped[k] = {
            value: v,
            source: isGlobalVar ? "variable" : "raw",
          };
        });
        rawPayloads.push({
          app_id: id,
          environment_variables: envVarsWrapped,
        });
      });

      const hasOperations = operations.length > 0;
      const hasNewConnections = rawPayloads.length > 0;
      const llmToSend = selectedLlm;

      if (llmToSend || hasOperations || hasNewConnections) {
        result.provider_data = {
          ...(llmToSend && { llm: llmToSend }),
          ...(hasOperations && { operations }),
          ...(hasNewConnections && {
            connections: {
              raw_payloads: rawPayloads,
            },
          }),
        };
      }

      // Backend requires at least one field.
      if (!result.spec && !result.provider_data) {
        result.spec = { description: deploymentDescription };
      }

      return result;
    }, [
      editingDeployment,
      deploymentDescription,
      selectedLlm,
      initialVersionByFlow,
      initialToolNameByFlow,
      removedFlowIds,
      selectedVersionByFlow,
      toolNameByFlow,
      attachedConnectionByFlow,
      connections,
    ]);

  const value = useMemo<DeploymentStepperContextType>(
    () => ({
      isEditMode,
      editingDeployment,
      currentStep,
      totalSteps,
      minStep,
      canGoNext,
      handleNext,
      handleBack,
      selectedProvider,
      setSelectedProvider,
      selectedInstance,
      setSelectedInstance,
      credentials,
      setCredentials,
      deploymentType,
      setDeploymentType,
      deploymentName,
      setDeploymentName,
      deploymentDescription,
      setDeploymentDescription,
      selectedLlm,
      setSelectedLlm,
      initialFlowId: initialState?.initialFlowId ?? null,
      connections,
      setConnections,
      selectedVersionByFlow,
      handleSelectVersion,
      toolNameByFlow,
      setToolNameByFlow,
      attachedConnectionByFlow,
      setAttachedConnectionByFlow,
      preExistingFlowIds,
      removedFlowIds,
      handleRemoveAttachedFlow,
      handleUndoRemoveFlow,
      needsProviderAccountCreation,
      buildProviderAccountPayload,
      buildDeploymentPayload,
      buildDeploymentUpdatePayload,
    }),
    [
      isEditMode,
      editingDeployment,
      currentStep,
      totalSteps,
      minStep,
      canGoNext,
      handleNext,
      handleBack,
      selectedProvider,
      setSelectedProvider,
      selectedInstance,
      credentials,
      deploymentType,
      deploymentName,
      deploymentDescription,
      selectedLlm,
      connections,
      selectedVersionByFlow,
      handleSelectVersion,
      toolNameByFlow,
      attachedConnectionByFlow,
      preExistingFlowIds,
      removedFlowIds,
      handleRemoveAttachedFlow,
      handleUndoRemoveFlow,
      needsProviderAccountCreation,
      buildProviderAccountPayload,
      buildDeploymentPayload,
      buildDeploymentUpdatePayload,
    ],
  );

  return (
    <DeploymentStepperContext.Provider value={value}>
      {children}
    </DeploymentStepperContext.Provider>
  );
}

export function useDeploymentStepper() {
  const context = useContext(DeploymentStepperContext);
  if (!context) {
    throw new Error(
      "useDeploymentStepper must be used within a DeploymentStepperProvider",
    );
  }
  return context;
}
