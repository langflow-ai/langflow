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
import type {
  DeploymentUpdateFlowItem,
  DeploymentUpdateProviderData,
  DeploymentUpdateRequest,
} from "@/controllers/API/queries/deployments/use-patch-deployment";
import type {
  DeploymentConnectionPayload,
  DeploymentCreateRequest,
} from "@/controllers/API/queries/deployments/use-post-deployment";
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
    url: "",
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
  const initialConnectionsByFlow = useMemo(
    () => initialState?.initialConnectionsByFlow ?? new Map<string, string[]>(),
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
      const originalConnections = initialConnectionsByFlow.get(flowId);
      if (originalConnections) {
        setAttachedConnectionByFlow((prev) => {
          const next = new Map(prev);
          next.set(flowId, originalConnections);
          return next;
        });
      }
    },
    [initialVersionByFlow, initialConnectionsByFlow],
  );

  const hasValidCredentials =
    credentials.name.trim() !== "" &&
    credentials.api_key.trim() !== "" &&
    credentials.url.trim() !== "";

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
      url: "",
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
        url: credentials.url.trim(),
        provider_data: { api_key: credentials.api_key.trim() },
      };
    }, [credentials, hasValidCredentials]);

  const buildConnectionPayloads = useCallback(
    (
      connectionIds: Iterable<string>,
    ): DeploymentCreateRequest["provider_data"]["connections"] => {
      const payloads: DeploymentCreateRequest["provider_data"]["connections"] =
        [];
      const uniqueIds = Array.from(new Set(connectionIds));

      for (const id of uniqueIds) {
        const conn = connections.find((item) => item.id === id);
        if (!conn?.isNew) continue;

        const credentials: DeploymentConnectionPayload["credentials"] =
          Object.entries(conn.environmentVariables).map(([key, value]) => {
            const isGlobalVar = conn.globalVarKeys?.has(key) ?? false;
            return {
              key,
              value,
              source: isGlobalVar ? "variable" : "raw",
            };
          });

        payloads.push({
          app_id: id,
          credentials,
        });
      }

      return payloads;
    },
    [connections],
  );

  const buildDeploymentPayload = useCallback(
    (providerId: string): DeploymentCreateRequest => {
      const allConnectionIds = new Set<string>();
      Array.from(attachedConnectionByFlow.values()).forEach((ids) => {
        ids.forEach((id) => allConnectionIds.add(id));
      });

      const addFlows: DeploymentCreateRequest["provider_data"]["add_flows"] =
        [];
      for (const [flowId, versionEntry] of Array.from(selectedVersionByFlow)) {
        const connectionIds = attachedConnectionByFlow.get(flowId) ?? [];
        const customToolName = toolNameByFlow.get(flowId)?.trim();
        addFlows.push({
          flow_version_id: versionEntry.versionId,
          app_ids: connectionIds,
          ...(customToolName && { tool_name: customToolName }),
        });
      }

      const connectionPayloads = buildConnectionPayloads(allConnectionIds);

      return {
        provider_id: providerId,
        name: deploymentName,
        description: deploymentDescription,
        type: deploymentType,
        provider_data: {
          llm: selectedLlm,
          add_flows: addFlows,
          connections: connectionPayloads,
        },
      };
    },
    [
      attachedConnectionByFlow,
      buildConnectionPayloads,
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

      // Metadata changes (description only — name is not editable after creation).
      const descriptionChanged =
        deploymentDescription !== (editingDeployment.description ?? "");
      if (descriptionChanged) {
        result.description = deploymentDescription;
      }

      const upsertFlows: DeploymentUpdateFlowItem[] = [];

      // New flows attached during this edit session.
      for (const [flowId, versionEntry] of Array.from(selectedVersionByFlow)) {
        if (initialVersionByFlow.has(flowId)) continue;
        const connectionIds = attachedConnectionByFlow.get(flowId) ?? [];
        const customToolName = toolNameByFlow.get(flowId)?.trim();
        upsertFlows.push({
          flow_version_id: versionEntry.versionId,
          add_app_ids: connectionIds,
          remove_app_ids: [],
          ...(customToolName && { tool_name: customToolName }),
        });
      }

      // Changes on pre-existing flows (tool name and/or connections).
      for (const [flowId, versionEntry] of Array.from(selectedVersionByFlow)) {
        if (!initialVersionByFlow.has(flowId)) continue;
        const currentName = toolNameByFlow.get(flowId)?.trim() ?? "";
        const originalName = initialToolNameByFlow.get(flowId)?.trim() ?? "";
        const nameChanged = currentName && currentName !== originalName;

        const currentConnections = attachedConnectionByFlow.get(flowId) ?? [];
        const originalConnections = initialConnectionsByFlow.get(flowId) ?? [];
        const originalSet = new Set(originalConnections);
        const currentSet = new Set(currentConnections);
        const addAppIds = currentConnections.filter(
          (id) => !originalSet.has(id),
        );
        const removeAppIds = originalConnections.filter(
          (id) => !currentSet.has(id),
        );
        const connectionsChanged =
          addAppIds.length > 0 || removeAppIds.length > 0;

        if (nameChanged || connectionsChanged) {
          upsertFlows.push({
            flow_version_id: versionEntry.versionId,
            add_app_ids: addAppIds,
            remove_app_ids: removeAppIds,
            ...(nameChanged && { tool_name: currentName }),
          });
        }
      }

      const removeFlows: string[] = [];
      for (const flowId of Array.from(removedFlowIds)) {
        const originalVersion = initialVersionByFlow.get(flowId);
        if (originalVersion) {
          removeFlows.push(originalVersion.versionId);
        }
      }

      // Collect connection details for newly added binds only.
      const newConnectionIds = new Set<string>();
      upsertFlows.forEach((flowItem) => {
        flowItem.add_app_ids.forEach((id) => newConnectionIds.add(id));
      });
      const connectionPayloads = buildConnectionPayloads(newConnectionIds);

      const llmToSend = selectedLlm;
      if (
        llmToSend ||
        upsertFlows.length > 0 ||
        removeFlows.length > 0 ||
        connectionPayloads.length > 0
      ) {
        const providerData: DeploymentUpdateProviderData = {
          ...(llmToSend && { llm: llmToSend }),
          ...(upsertFlows.length > 0 && { upsert_flows: upsertFlows }),
          ...(removeFlows.length > 0 && { remove_flows: removeFlows }),
          ...(connectionPayloads.length > 0 && {
            connections: connectionPayloads,
          }),
        };
        result.provider_data = providerData;
      }

      // Backend requires at least one field.
      if (result.description === undefined && !result.provider_data) {
        result.description = deploymentDescription;
      }

      return result;
    }, [
      editingDeployment,
      deploymentDescription,
      selectedLlm,
      initialVersionByFlow,
      initialToolNameByFlow,
      initialConnectionsByFlow,
      removedFlowIds,
      selectedVersionByFlow,
      toolNameByFlow,
      attachedConnectionByFlow,
      buildConnectionPayloads,
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
