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
import { toResourceNamePrefix } from "../types";

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

  // Extract LLM from provider_data if available
  const initialLlm =
    typeof editingDeployment?.provider_data?.llm === "string"
      ? editingDeployment.provider_data.llm
      : "";
  const [selectedLlm, setSelectedLlm] = useState(initialLlm);

  const [selectedVersionByFlow, setSelectedVersionByFlow] = useState<
    Map<string, { versionId: string; versionTag: string }>
  >(initialState?.selectedVersionByFlow ?? new Map());
  const [connections, setConnections] = useState<ConnectionItem[]>([]);
  const [attachedConnectionByFlow, setAttachedConnectionByFlow] = useState<
    Map<string, string[]>
  >(new Map());

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
      return isEditMode || attachedConnectionByFlow.size > 0;
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
    attachedConnectionByFlow,
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
      for (const [flowId, connectionIds] of Array.from(
        attachedConnectionByFlow,
      )) {
        const versionEntry = selectedVersionByFlow.get(flowId);
        if (!versionEntry || connectionIds.length === 0) continue;
        operations.push({
          op: "bind",
          flow_version_id: versionEntry.versionId,
          app_ids: connectionIds,
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
          resource_name_prefix: toResourceNamePrefix(deploymentName),
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
    ],
  );

  const buildDeploymentUpdatePayload =
    useCallback((): DeploymentUpdateRequest => {
      if (!editingDeployment) {
        throw new Error("buildDeploymentUpdatePayload called outside edit mode");
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

      // Flow version changes
      const newFlowVersionIds = Array.from(selectedVersionByFlow.values()).map(
        (v) => v.versionId,
      );
      if (newFlowVersionIds.length > 0) {
        result.add_flow_version_ids = newFlowVersionIds;
      }

      // Provider data changes (LLM, connections, operations)
      const providerDataUpdate: Record<string, unknown> = {};

      if (selectedLlm !== initialLlm) {
        providerDataUpdate.llm = selectedLlm;
      }

      // Build operations from attached flows (same structure as create)
      const allConnectionIds = new Set<string>();
      Array.from(attachedConnectionByFlow.values()).forEach((ids) => {
        ids.forEach((id) => allConnectionIds.add(id));
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

      const operations: Array<{
        op: "bind";
        flow_version_id: string;
        app_ids: string[];
      }> = [];
      for (const [flowId, connectionIds] of Array.from(
        attachedConnectionByFlow,
      )) {
        const versionEntry = selectedVersionByFlow.get(flowId);
        if (!versionEntry || connectionIds.length === 0) continue;
        operations.push({
          op: "bind",
          flow_version_id: versionEntry.versionId,
          app_ids: connectionIds,
        });
      }

      if (
        operations.length > 0 ||
        existingAppIds.length > 0 ||
        rawPayloads.length > 0 ||
        Object.keys(providerDataUpdate).length > 0
      ) {
        result.provider_data = {
          ...providerDataUpdate,
          ...(operations.length > 0 && { operations }),
          ...((existingAppIds.length > 0 || rawPayloads.length > 0) && {
            connections: {
              existing_app_ids: existingAppIds,
              raw_payloads: rawPayloads,
            },
          }),
        };
      }

      // Backend requires at least one field. If nothing changed, send current
      // description so the request is still valid (backend treats same-value as no-op).
      if (
        !result.spec &&
        !result.add_flow_version_ids &&
        !result.remove_flow_version_ids &&
        !result.config &&
        !result.provider_data
      ) {
        result.spec = { description: deploymentDescription };
      }

      return result;
    }, [
      editingDeployment,
      deploymentName,
      deploymentDescription,
      selectedLlm,
      initialLlm,
      selectedVersionByFlow,
      attachedConnectionByFlow,
      connections,
    ]);

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
      attachedConnectionByFlow,
      setAttachedConnectionByFlow,
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
      attachedConnectionByFlow,
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
