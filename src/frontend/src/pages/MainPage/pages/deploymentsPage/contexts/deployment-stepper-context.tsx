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
  /** When provided, the stepper opens in edit mode. */
  editingDeployment?: Deployment;
  /** The provider account associated with the deployment being edited. */
  editingProviderAccount?: ProviderAccount | null;
  /** Pre-populated attachment info for edit mode (provider_snapshot_id per flow). */
  initialAttachedConnectionByFlow?: Map<string, string[]>;
  /** Provider tool IDs (provider_snapshot_id) per flow for existing attachments. */
  initialSnapshotByFlow?: Map<string, string>;
  /** Tool display names from the provider per flow for existing attachments. */
  initialToolNameByFlow?: Map<string, string>;
  /** LLM model from the provider (fetched via attachments endpoint). */
  initialLlmFromProvider?: string;
}

interface DeploymentStepperContextType {
  // Mode
  isEditMode: boolean;
  editingDeployment: Deployment | null;

  // Navigation
  currentStep: number;
  /** Total number of steps (3 for edit mode, 4 for create mode) */
  totalSteps: number;
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
  /** Flow IDs that were originally attached but the user chose to remove. */
  removedFlowIds: Set<string>;
  /** Detach an existing flow (edit mode only). */
  handleRemoveAttachedFlow: (flowId: string) => void;
  /** Re-attach a previously removed flow (undo). */
  handleUndoRemoveFlow: (flowId: string) => void;

  // Deploy / Update
  needsProviderAccountCreation: boolean;
  buildProviderAccountPayload: () => ProviderAccountCreateRequest | null;
  buildDeploymentPayload: (providerId: string) => DeploymentCreateRequest;
  buildDeploymentUpdatePayload: () => DeploymentUpdateRequest;
  /** Returns snapshot updates needed for version changes on existing tools. */
  getSnapshotUpdates: () => Array<{
    provider_snapshot_id: string;
    flow_version_id: string;
  }>;
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

  // In edit mode, we skip the provider step. Steps are 1-based.
  // Create mode: 1=Provider, 2=Type, 3=AttachFlows, 4=Review
  // Edit mode:   1=Type, 2=AttachFlows, 3=Review
  const totalSteps = isEditMode ? 3 : 4;
  const [currentStep, setCurrentStep] = useState(1);

  const [selectedProvider, setSelectedProviderState] =
    useState<DeploymentProvider | null>(null);
  const [selectedInstance, setSelectedInstance] =
    useState<ProviderAccount | null>(
      initialState?.editingProviderAccount ?? null,
    );
  const [credentials, setCredentials] = useState<ProviderCredentials>({
    name: "",
    provider_key: "",
    provider_url: "",
    api_key: "",
  });

  // Pre-fill from editing deployment
  const [deploymentType, setDeploymentType] = useState<DeploymentType>(
    editingDeployment?.type ?? "agent",
  );
  const [deploymentName, setDeploymentName] = useState(
    editingDeployment?.name ?? "",
  );
  const [deploymentDescription, setDeploymentDescription] = useState(
    editingDeployment?.description ?? "",
  );

  // Extract LLM: prefer the provider-sourced value from the attachments endpoint,
  // fall back to provider_data on the deployment object.
  const initialLlm =
    initialState?.initialLlmFromProvider ??
    (typeof editingDeployment?.provider_data?.llm === "string"
      ? editingDeployment.provider_data.llm
      : "");
  const [selectedLlm, setSelectedLlm] = useState(initialLlm);

  const [selectedVersionByFlow, setSelectedVersionByFlow] = useState<
    Map<string, { versionId: string; versionTag: string }>
  >(initialState?.selectedVersionByFlow ?? new Map());
  const [toolNameByFlow, setToolNameByFlow] = useState<Map<string, string>>(
    initialState?.initialToolNameByFlow ?? new Map(),
  );
  const [connections, setConnections] = useState<ConnectionItem[]>([]);
  const initialAttachedRef = useMemo(
    () =>
      initialState?.initialAttachedConnectionByFlow ??
      new Map<string, string[]>(),
    // Only compute once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
  const [attachedConnectionByFlow, setAttachedConnectionByFlow] =
    useState<Map<string, string[]>>(initialAttachedRef);
  const [removedFlowIds, setRemovedFlowIds] = useState<Set<string>>(new Set());

  const handleRemoveAttachedFlow = useCallback((flowId: string) => {
    setRemovedFlowIds((prev) => new Set([...Array.from(prev), flowId]));
    // Remove from the visible attached maps so the UI updates
    setAttachedConnectionByFlow((prev) => {
      const next = new Map(prev);
      next.delete(flowId);
      return next;
    });
    setSelectedVersionByFlow((prev) => {
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
      // Restore the original attachment data
      const originalConnections = initialAttachedRef.get(flowId);
      const originalVersion = initialState?.selectedVersionByFlow?.get(flowId);
      if (originalConnections) {
        setAttachedConnectionByFlow((prev) => {
          const next = new Map(prev);
          next.set(flowId, originalConnections);
          return next;
        });
      }
      if (originalVersion) {
        setSelectedVersionByFlow((prev) => {
          const next = new Map(prev);
          next.set(flowId, originalVersion);
          return next;
        });
      }
    },
    [initialAttachedRef, initialState?.selectedVersionByFlow],
  );

  const hasValidCredentials =
    credentials.name.trim() !== "" &&
    credentials.api_key.trim() !== "" &&
    credentials.provider_url.trim() !== "";

  // Map logical step → validation. In edit mode steps are shifted.
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
      // In edit mode, the user can skip attaching new flows (they may only update name/LLM)
      return isEditMode || selectedVersionByFlow.size > 0;
    }
    // Review step — always true
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
    setCurrentStep((prev) => (prev > 1 ? prev - 1 : prev));
  }, []);

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
        ids.forEach((id) => {
          allConnectionIds.add(id);
        });
      });

      const existingAppIds: string[] = [];
      const rawPayloads: Array<{
        app_id: string;
        environment_variables: Record<string, { value: string; source: "raw" }>;
      }> = [];

      Array.from(allConnectionIds).forEach((id) => {
        const conn = connections.find((c) => c.id === id);
        if (conn?.isNew) {
          const envVarsWrapped: Record<
            string,
            { value: string; source: "raw" }
          > = {};
          Object.entries(conn.environmentVariables).forEach(([k, v]) => {
            envVarsWrapped[k] = { value: v, source: "raw" };
          });
          rawPayloads.push({
            app_id: id,
            environment_variables: envVarsWrapped,
          });
        } else {
          existingAppIds.push(id);
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
            existing_app_ids: existingAppIds,
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

      // Spec changes (description only — name is not editable after creation)
      const descriptionChanged =
        deploymentDescription !== (editingDeployment.description ?? "");
      if (descriptionChanged) {
        result.spec = { description: deploymentDescription };
      }

      // Watsonx requires ALL flow version and config changes to go through
      // provider_data (not top-level add_flow_version_ids / config fields).
      // The LLM field is always required in provider_data by the Watsonx schema.

      // Build operations for flow changes.
      // Version changes on existing tools are handled separately via
      // PATCH /snapshots/{id} (getSnapshotUpdates), NOT here.
      // This payload only handles:
      //   - Brand new flows → bind (creates new tool)
      //   - Removed flows → remove_tool (detaches existing tool + deletes DB attachment)
      const operations: Array<Record<string, unknown>> = [];
      const initialVersionByFlow = initialState?.selectedVersionByFlow;
      const snapshotByFlow = initialState?.initialSnapshotByFlow;

      // Check all flows in selectedVersionByFlow for new additions
      for (const [flowId, versionEntry] of Array.from(selectedVersionByFlow)) {
        const originalVersion = initialVersionByFlow?.get(flowId);
        if (originalVersion) {
          // Existing flow — version changes are handled by getSnapshotUpdates
          continue;
        }
        // Brand new flow → bind (with or without connections)
        const connectionIds = attachedConnectionByFlow.get(flowId) ?? [];
        const customToolName = toolNameByFlow.get(flowId)?.trim();
        operations.push({
          op: "bind",
          flow_version_id: versionEntry.versionId,
          app_ids: connectionIds,
          ...(customToolName && { tool_name: customToolName }),
        });
      }

      // Emit operations for flows in removedFlowIds.
      for (const flowId of Array.from(removedFlowIds)) {
        const originalVersion = initialVersionByFlow?.get(flowId);

        if (selectedVersionByFlow.has(flowId)) {
          // User removed then re-attached — need to remove the old tool
          // AND bind the new one (may be different version / tool name).
          if (originalVersion) {
            operations.push({
              op: "remove_tool",
              flow_version_id: originalVersion.versionId,
            });
          }
          const versionEntry = selectedVersionByFlow.get(flowId)!;
          const connectionIds = attachedConnectionByFlow.get(flowId) ?? [];
          const customToolName = toolNameByFlow.get(flowId)?.trim();
          operations.push({
            op: "bind",
            flow_version_id: versionEntry.versionId,
            app_ids: connectionIds,
            ...(customToolName && { tool_name: customToolName }),
          });
          continue;
        }

        // Fully detached — just remove
        if (originalVersion) {
          operations.push({
            op: "remove_tool",
            flow_version_id: originalVersion.versionId,
          });
        }
      }

      // Collect connection details for flows that have bind operations
      // (new flows + flows with changed versions)
      const bindFlowVersionIds = new Set(
        operations.filter((o) => o.op === "bind").map((o) => o.flow_version_id),
      );
      const newConnectionIds = new Set<string>();
      for (const [flowId, connectionIds] of Array.from(
        attachedConnectionByFlow,
      )) {
        const versionEntry = selectedVersionByFlow.get(flowId);
        if (!versionEntry || !bindFlowVersionIds.has(versionEntry.versionId))
          continue;
        connectionIds.forEach((id) => newConnectionIds.add(id));
      }

      const existingAppIds: string[] = [];
      const rawPayloads: Array<{
        app_id: string;
        environment_variables: Record<string, { value: string; source: "raw" }>;
      }> = [];

      Array.from(newConnectionIds).forEach((id) => {
        const conn = connections.find((c) => c.id === id);
        if (conn?.isNew) {
          const envVarsWrapped: Record<
            string,
            { value: string; source: "raw" }
          > = {};
          Object.entries(conn.environmentVariables).forEach(([k, v]) => {
            envVarsWrapped[k] = { value: v, source: "raw" };
          });
          rawPayloads.push({
            app_id: id,
            environment_variables: envVarsWrapped,
          });
        } else {
          existingAppIds.push(id);
        }
      });

      // Build provider_data with the current LLM and any operations / connection changes.
      // Watsonx requires LLM whenever provider_data is sent.
      const hasOperations = operations.length > 0;
      const hasConnections =
        existingAppIds.length > 0 || rawPayloads.length > 0;
      const llmToSend = selectedLlm || initialLlm;

      if (llmToSend || hasOperations || hasConnections) {
        result.provider_data = {
          ...(llmToSend && { llm: llmToSend }),
          ...(hasOperations && { operations }),
          ...(hasConnections && {
            connections: {
              existing_app_ids: existingAppIds,
              raw_payloads: rawPayloads,
            },
          }),
        };
      }

      // Backend requires at least one field. If nothing changed, send current
      // description so the request is still valid (backend treats same-value as no-op).
      if (!result.spec && !result.provider_data) {
        result.spec = { description: deploymentDescription };
      }

      return result;
    }, [
      editingDeployment,
      deploymentName,
      deploymentDescription,
      selectedLlm,
      initialLlm,
      initialAttachedRef,
      removedFlowIds,
      selectedVersionByFlow,
      toolNameByFlow,
      attachedConnectionByFlow,
      connections,
    ]);

  const getSnapshotUpdates = useCallback((): Array<{
    provider_snapshot_id: string;
    flow_version_id: string;
  }> => {
    const initialVersionByFlow = initialState?.selectedVersionByFlow;
    const snapshotByFlow = initialState?.initialSnapshotByFlow;
    if (!initialVersionByFlow || !snapshotByFlow) return [];

    const updates: Array<{
      provider_snapshot_id: string;
      flow_version_id: string;
    }> = [];

    for (const [flowId, originalVersion] of Array.from(initialVersionByFlow)) {
      // Skip removed flows — they're handled by remove_tool_by_id
      if (removedFlowIds.has(flowId)) continue;
      const currentVersion = selectedVersionByFlow.get(flowId);
      if (!currentVersion) continue;
      if (currentVersion.versionId === originalVersion.versionId) continue;

      const snapshotId = snapshotByFlow.get(flowId);
      if (!snapshotId) continue;

      updates.push({
        provider_snapshot_id: snapshotId,
        flow_version_id: currentVersion.versionId,
      });
    }
    return updates;
  }, [initialState, removedFlowIds, selectedVersionByFlow]);

  const value = useMemo<DeploymentStepperContextType>(
    () => ({
      isEditMode,
      editingDeployment,
      currentStep,
      totalSteps,
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
      removedFlowIds,
      handleRemoveAttachedFlow,
      handleUndoRemoveFlow,
      needsProviderAccountCreation,
      buildProviderAccountPayload,
      buildDeploymentPayload,
      buildDeploymentUpdatePayload,
      getSnapshotUpdates,
    }),
    [
      isEditMode,
      editingDeployment,
      currentStep,
      totalSteps,
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
      removedFlowIds,
      handleRemoveAttachedFlow,
      handleUndoRemoveFlow,
      needsProviderAccountCreation,
      buildProviderAccountPayload,
      buildDeploymentPayload,
      buildDeploymentUpdatePayload,
      getSnapshotUpdates,
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
