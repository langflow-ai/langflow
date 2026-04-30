import {
  createContext,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
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
  SelectedFlowVersion,
} from "../types";
import {
  createDeploymentToolNameScopeId,
  getDefaultDeploymentToolName,
  getSelectedFlowVersionKey,
} from "../types";

interface DeploymentStepperInitialState {
  projectId?: string;
  selectedVersionByFlow?: Map<string, SelectedFlowVersion>;
  initialFlowId?: string;
  initialProvider?: DeploymentProvider;
  initialInstance?: ProviderAccount;
  initialStep?: number;
  /** When provided, the stepper opens in edit mode. */
  editingDeployment?: Deployment;
  /** Pre-populated initial LLM from provider (edit mode). */
  initialLlm?: string;
  /** Pre-populated tool names from provider (edit mode). Key = attachment key. */
  initialToolNameByFlow?: Map<string, string>;
  /** Pre-populated connection assignments from provider (edit mode). Key = attachment key. */
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
  isDeploymentNameValid: boolean;
  hasDeploymentNameFormatError: boolean;
  deploymentDescription: string;
  setDeploymentDescription: (description: string) => void;
  selectedLlm: string;
  setSelectedLlm: (llm: string) => void;

  // Step 3: Attach Flows
  initialFlowId: string | null;
  connections: ConnectionItem[];
  setConnections: Dispatch<SetStateAction<ConnectionItem[]>>;
  selectedVersionByFlow: Map<string, SelectedFlowVersion>;
  handleSelectVersion: (
    flowId: string,
    flowNameOrVersionId: string,
    versionIdOrVersionTag: string,
    versionTag?: string,
  ) => void;
  attachedConnectionByFlow: Map<string, string[]>;
  setAttachedConnectionByFlow: Dispatch<SetStateAction<Map<string, string[]>>>;
  /** User-provided tool names per attached version. Key = attachment key. */
  toolNameByFlow: Map<string, string>;
  setToolNameByFlow: Dispatch<SetStateAction<Map<string, string>>>;
  /** Original tool names from provider before this edit session (edit mode). Key = attachment key. */
  initialToolNameByFlow: Map<string, string>;
  defaultToolNameScopeId: string | null;
  /** Attachment keys that were already attached before this edit session (edit mode). */
  preExistingFlowIds: Set<string>;
  /** Attachment keys that were originally attached but the user chose to detach (edit mode). */
  removedFlowIds: Set<string>;
  handleRemoveAttachedFlow: (attachmentKey: string) => void;
  handleUndoRemoveFlow: (attachmentKey: string) => void;

  // Tool name validation
  hasToolNameErrors: boolean;
  setHasToolNameErrors: Dispatch<SetStateAction<boolean>>;

  // Agent name validation
  hasAgentNameErrors: boolean;
  setHasAgentNameErrors: Dispatch<SetStateAction<boolean>>;
  isAgentNameValidationPending: boolean;
  setIsAgentNameValidationPending: Dispatch<SetStateAction<boolean>>;

  // Deploy / Update
  needsProviderAccountCreation: boolean;
  buildProviderAccountPayload: () => ProviderAccountCreateRequest | null;
  buildDeploymentPayload: (providerId: string) => DeploymentCreateRequest;
  buildDeploymentUpdatePayload: () => DeploymentUpdateRequest;
}

const DeploymentStepperContext =
  createContext<DeploymentStepperContextType | null>(null);

function normalizeSelectedFlowVersions(
  versions?: Map<string, SelectedFlowVersion>,
): Map<string, SelectedFlowVersion> {
  const next = new Map<string, SelectedFlowVersion>();
  for (const [key, value] of versions ?? new Map()) {
    const flowId = value.flowId ?? key;
    const versionId = value.versionId;
    const normalizedKey = value.flowId
      ? getSelectedFlowVersionKey(flowId, versionId)
      : key;
    next.set(normalizedKey, {
      key: normalizedKey,
      flowId,
      flowName: value.flowName,
      versionId,
      versionTag: value.versionTag,
    });
  }
  return next;
}

function getScopedValue<T>(
  map: Map<string, T>,
  attachmentKey: string,
  flowId: string,
): T | undefined {
  return map.get(attachmentKey) ?? map.get(flowId);
}

function getScopedToolName(
  map: Map<string, string>,
  attachmentKey: string,
  flowId: string,
  versionMap: Map<string, SelectedFlowVersion>,
): string | undefined {
  const strictValue = map.get(attachmentKey);
  if (strictValue !== undefined) {
    return strictValue;
  }

  const flowVersionCount = Array.from(versionMap.values()).filter(
    (entry) => entry.flowId === flowId,
  ).length;

  if (flowVersionCount > 1) {
    return undefined;
  }

  return map.get(flowId);
}

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

  const normalizedInitialVersions = useMemo(
    () => normalizeSelectedFlowVersions(initialState?.selectedVersionByFlow),
    [initialState?.selectedVersionByFlow],
  );
  const normalizedInitialToolNames = useMemo(
    () => initialState?.initialToolNameByFlow ?? new Map<string, string>(),
    [initialState?.initialToolNameByFlow],
  );
  const normalizedInitialConnections = useMemo(
    () => initialState?.initialConnectionsByFlow ?? new Map<string, string[]>(),
    [initialState?.initialConnectionsByFlow],
  );

  const [selectedVersionByFlow, setSelectedVersionByFlow] = useState<
    Map<string, SelectedFlowVersion>
  >(normalizedInitialVersions);
  const [connections, setConnections] = useState<ConnectionItem[]>([]);
  const [toolNameByFlow, setToolNameByFlow] = useState<Map<string, string>>(
    normalizedInitialToolNames,
  );
  const [defaultToolNameScopeId] = useState<string | null>(() =>
    isEditMode
      ? (editingDeployment?.id ?? createDeploymentToolNameScopeId())
      : createDeploymentToolNameScopeId(),
  );
  const [attachedConnectionByFlow, setAttachedConnectionByFlow] = useState<
    Map<string, string[]>
  >(normalizedInitialConnections);

  const [hasToolNameErrors, setHasToolNameErrors] = useState(false);
  const trimmedDeploymentName = deploymentName.trim();
  const hasDeploymentNameFormatError =
    trimmedDeploymentName !== "" && !/^\p{L}/u.test(trimmedDeploymentName);
  const isDeploymentNameValid =
    trimmedDeploymentName !== "" && !hasDeploymentNameFormatError;
  const [hasAgentNameErrors, setHasAgentNameErrors] = useState(false);
  const [isAgentNameValidationPending, setIsAgentNameValidationPending] =
    useState(false);

  // Edit mode: track which pre-existing flows the user wants to detach.
  const [removedFlowIds, setRemovedFlowIds] = useState<Set<string>>(new Set());
  // Cache removed flow data so undo can restore it.
  const initialVersionByFlow = normalizedInitialVersions;
  const preExistingFlowIds = useMemo(
    () => new Set(initialVersionByFlow.keys()),
    [initialVersionByFlow],
  );
  const initialToolNameByFlow = normalizedInitialToolNames;
  const initialConnectionsByFlow = normalizedInitialConnections;
  const hasHydratedEditStateRef = useRef(false);

  useEffect(() => {
    if (!isEditMode) return;
    if (hasHydratedEditStateRef.current) return;
    if (
      normalizedInitialVersions.size === 0 &&
      normalizedInitialToolNames.size === 0 &&
      normalizedInitialConnections.size === 0
    ) {
      return;
    }
    hasHydratedEditStateRef.current = true;
    setSelectedVersionByFlow(normalizedInitialVersions);
    setToolNameByFlow(normalizedInitialToolNames);
    setAttachedConnectionByFlow(normalizedInitialConnections);
  }, [
    isEditMode,
    normalizedInitialConnections,
    normalizedInitialToolNames,
    normalizedInitialVersions,
  ]);

  const handleRemoveAttachedFlow = useCallback(
    (attachmentKeyOrFlowId: string) => {
      const resolvedKey = selectedVersionByFlow.has(attachmentKeyOrFlowId)
        ? attachmentKeyOrFlowId
        : Array.from(selectedVersionByFlow.values()).find(
            (entry) => entry.flowId === attachmentKeyOrFlowId,
          )?.key;
      if (!resolvedKey) return;
      setRemovedFlowIds((prev) => new Set([...Array.from(prev), resolvedKey]));
    },
    [selectedVersionByFlow],
  );

  const handleUndoRemoveFlow = useCallback((attachmentKey: string) => {
    setRemovedFlowIds((prev) => {
      const next = new Set(prev);
      next.delete(attachmentKey);
      return next;
    });
  }, []);

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
      return (
        isDeploymentNameValid &&
        selectedLlm.trim() !== "" &&
        !hasAgentNameErrors &&
        !isAgentNameValidationPending
      );
    }
    if (logical === 3) {
      // In edit mode, user can proceed without new attachments (may just change desc/LLM).
      return isEditMode || selectedVersionByFlow.size > 0;
    }
    if (logical === 4) {
      return !hasToolNameErrors;
    }
    return true;
  }, [
    currentStep,
    getLogicalStep,
    selectedProvider,
    selectedInstance,
    hasValidCredentials,
    deploymentName,
    isDeploymentNameValid,
    selectedLlm,
    selectedVersionByFlow,
    isEditMode,
    hasToolNameErrors,
    hasAgentNameErrors,
    isAgentNameValidationPending,
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
    (
      flowId: string,
      flowNameOrVersionId: string,
      versionIdOrVersionTag: string,
      versionTag?: string,
    ) => {
      const flowName = versionTag ? flowNameOrVersionId : "Flow";
      const versionId = versionTag
        ? versionIdOrVersionTag
        : flowNameOrVersionId;
      const resolvedVersionTag = versionTag ?? versionIdOrVersionTag;
      setSelectedVersionByFlow((prev) => {
        const next = new Map(prev);
        const key = getSelectedFlowVersionKey(flowId, versionId);
        next.set(key, {
          key,
          flowId,
          flowName,
          versionId,
          versionTag: resolvedVersionTag,
        });
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
        provider_data: {
          url: credentials.url.trim(),
          api_key: credentials.api_key.trim(),
        },
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
      if (!isDeploymentNameValid) {
        throw new Error("Deployment name must start with a letter");
      }
      const allConnectionIds = new Set<string>();
      Array.from(attachedConnectionByFlow.values()).forEach((ids) => {
        ids.forEach((id) => allConnectionIds.add(id));
      });

      const addFlows: DeploymentCreateRequest["provider_data"]["add_flows"] =
        [];
      for (const [attachmentKey, versionEntry] of Array.from(
        selectedVersionByFlow,
      )) {
        if (removedFlowIds.has(attachmentKey)) continue;
        const connectionIds =
          getScopedValue(
            attachedConnectionByFlow,
            attachmentKey,
            versionEntry.flowId,
          ) ?? [];
        const strictToolName = getScopedToolName(
          toolNameByFlow,
          attachmentKey,
          versionEntry.flowId,
          selectedVersionByFlow,
        )?.trim();
        const resolvedToolName =
          strictToolName ||
          getDefaultDeploymentToolName(
            versionEntry.flowName ?? "Flow",
            versionEntry.versionId,
            defaultToolNameScopeId,
          );
        addFlows.push({
          flow_version_id: versionEntry.versionId,
          app_ids: connectionIds,
          tool_name: resolvedToolName,
        });
      }

      const connectionPayloads = buildConnectionPayloads(allConnectionIds);

      return {
        provider_id: providerId,
        ...(initialState?.projectId
          ? { project_id: initialState.projectId }
          : {}),
        name: trimmedDeploymentName,
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
      initialState?.projectId,
      defaultToolNameScopeId,
      deploymentDescription,
      deploymentType,
      isDeploymentNameValid,
      removedFlowIds,
      selectedLlm,
      selectedVersionByFlow,
      trimmedDeploymentName,
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
      if (!isDeploymentNameValid) {
        throw new Error("Deployment name must start with a letter");
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
      for (const [attachmentKey, versionEntry] of Array.from(
        selectedVersionByFlow,
      )) {
        if (removedFlowIds.has(attachmentKey)) continue;
        if (initialVersionByFlow.has(attachmentKey)) continue;
        const connectionIds =
          getScopedValue(
            attachedConnectionByFlow,
            attachmentKey,
            versionEntry.flowId,
          ) ?? [];
        const strictToolName = getScopedToolName(
          toolNameByFlow,
          attachmentKey,
          versionEntry.flowId,
          selectedVersionByFlow,
        )?.trim();
        const resolvedToolName =
          strictToolName ||
          getDefaultDeploymentToolName(
            versionEntry.flowName ?? "Flow",
            versionEntry.versionId,
            defaultToolNameScopeId,
          );
        upsertFlows.push({
          flow_version_id: versionEntry.versionId,
          add_app_ids: connectionIds,
          remove_app_ids: [],
          tool_name: resolvedToolName,
        });
      }

      // Changes on pre-existing flows (tool name and/or connections).
      for (const [attachmentKey, versionEntry] of Array.from(
        selectedVersionByFlow,
      )) {
        if (removedFlowIds.has(attachmentKey)) continue;
        if (!initialVersionByFlow.has(attachmentKey)) continue;
        const currentName =
          getScopedToolName(
            toolNameByFlow,
            attachmentKey,
            versionEntry.flowId,
            selectedVersionByFlow,
          )?.trim() ?? "";
        const originalName =
          getScopedToolName(
            initialToolNameByFlow,
            attachmentKey,
            versionEntry.flowId,
            initialVersionByFlow,
          )?.trim() ?? "";
        const nameChanged = currentName && currentName !== originalName;

        const currentConnections =
          getScopedValue(
            attachedConnectionByFlow,
            attachmentKey,
            versionEntry.flowId,
          ) ?? [];
        const originalConnections =
          getScopedValue(
            initialConnectionsByFlow,
            attachmentKey,
            versionEntry.flowId,
          ) ?? [];
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
      for (const attachmentKey of Array.from(removedFlowIds)) {
        const originalVersion = initialVersionByFlow.get(attachmentKey);
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
      defaultToolNameScopeId,
      isDeploymentNameValid,
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
      isDeploymentNameValid,
      hasDeploymentNameFormatError,
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
      initialToolNameByFlow,
      defaultToolNameScopeId,
      attachedConnectionByFlow,
      setAttachedConnectionByFlow,
      preExistingFlowIds,
      removedFlowIds,
      handleRemoveAttachedFlow,
      handleUndoRemoveFlow,
      hasToolNameErrors,
      setHasToolNameErrors,
      hasAgentNameErrors,
      setHasAgentNameErrors,
      isAgentNameValidationPending,
      setIsAgentNameValidationPending,
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
      isDeploymentNameValid,
      hasDeploymentNameFormatError,
      deploymentDescription,
      selectedLlm,
      connections,
      selectedVersionByFlow,
      handleSelectVersion,
      toolNameByFlow,
      initialToolNameByFlow,
      defaultToolNameScopeId,
      attachedConnectionByFlow,
      preExistingFlowIds,
      removedFlowIds,
      handleRemoveAttachedFlow,
      handleUndoRemoveFlow,
      hasToolNameErrors,
      hasAgentNameErrors,
      isAgentNameValidationPending,
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
