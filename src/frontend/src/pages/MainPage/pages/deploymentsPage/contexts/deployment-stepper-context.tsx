import {
  createContext,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useCallback,
  useContext,
  useMemo,
  useReducer,
  useState,
} from "react";
import type { ProviderAccountCreateRequest } from "@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account";
import type { DeploymentUpdateRequest } from "@/controllers/API/queries/deployments/use-patch-deployment";
import type { DeploymentCreateRequest } from "@/controllers/API/queries/deployments/use-post-deployment";
import type {
  ConnectionItem,
  Deployment,
  DeploymentProvider,
  DeploymentType,
  ProviderAccount,
  ProviderCredentials,
} from "../types";
import {
  createDeploymentStepperAttachmentsState,
  createSetAttachedConnectionByFlowDispatch,
  deploymentStepperAttachmentsReducer,
} from "./deployment-stepper-attachments-reducer";
import {
  buildDeploymentPayload as buildDeploymentPayloadFromState,
  buildDeploymentUpdatePayload as buildDeploymentUpdatePayloadFromState,
  buildProviderAccountPayload as buildProviderAccountPayloadFromState,
} from "./deployment-stepper-payloads";

interface DeploymentStepperInitialState {
  projectId?: string;
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
  /** Pre-populated connection assignments from provider (edit mode). Key = flowId. */
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
  /** Original tool names from provider before this edit session (edit mode). Key = flowId. */
  initialToolNameByFlow: Map<string, string>;
  /** Flow IDs that were already attached before this edit session (edit mode). */
  preExistingFlowIds: Set<string>;
  /** Flow IDs that were originally attached but the user chose to detach (edit mode). */
  removedFlowIds: Set<string>;
  handleRemoveAttachedFlow: (flowId: string) => void;
  handleUndoRemoveFlow: (flowId: string) => void;

  // Tool name validation
  hasToolNameErrors: boolean;
  setHasToolNameErrors: Dispatch<SetStateAction<boolean>>;

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
    api_key_source: "raw", // pragma: allowlist secret
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

  const [connections, setConnections] = useState<ConnectionItem[]>([]);
  const [toolNameByFlow, setToolNameByFlow] = useState<Map<string, string>>(
    initialState?.initialToolNameByFlow ?? new Map(),
  );

  const [hasToolNameErrors, setHasToolNameErrors] = useState(false);
  const [attachmentsState, attachmentsDispatch] = useReducer(
    deploymentStepperAttachmentsReducer,
    undefined,
    () =>
      createDeploymentStepperAttachmentsState({
        selectedVersionByFlow: initialState?.selectedVersionByFlow,
        initialConnectionsByFlow: initialState?.initialConnectionsByFlow,
      }),
  );
  const { selectedVersionByFlow, attachedConnectionByFlow, removedFlowIds } =
    attachmentsState;
  const setAttachedConnectionByFlow = useMemo(
    () => createSetAttachedConnectionByFlowDispatch(attachmentsDispatch),
    [attachmentsDispatch],
  );

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

  const handleRemoveAttachedFlow = useCallback(
    (flowId: string) => {
      attachmentsDispatch({
        type: "removeAttachedFlow",
        flowId,
      });
    },
    [attachmentsDispatch],
  );

  const handleUndoRemoveFlow = useCallback(
    (flowId: string) => {
      attachmentsDispatch({
        type: "undoRemoveFlow",
        flowId,
        initialVersionByFlow,
        initialConnectionsByFlow,
      });
    },
    [attachmentsDispatch, initialVersionByFlow, initialConnectionsByFlow],
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
    selectedLlm,
    selectedVersionByFlow,
    isEditMode,
    hasToolNameErrors,
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
      api_key_source: "raw", // pragma: allowlist secret
    });
  }, []);

  const handleSelectVersion = useCallback(
    (flowId: string, versionId: string, versionTag: string) => {
      attachmentsDispatch({
        type: "selectVersion",
        flowId,
        versionId,
        versionTag,
      });
    },
    [attachmentsDispatch],
  );

  const needsProviderAccountCreation =
    selectedInstance === null && hasValidCredentials;

  const buildProviderAccountPayload = useCallback(
    (): ProviderAccountCreateRequest | null =>
      buildProviderAccountPayloadFromState({
        credentials,
        hasValidCredentials,
      }),
    [credentials, hasValidCredentials],
  );

  const buildDeploymentPayload = useCallback(
    (providerId: string): DeploymentCreateRequest =>
      buildDeploymentPayloadFromState({
        providerId,
        projectId: initialState?.projectId,
        deploymentName,
        deploymentDescription,
        deploymentType,
        selectedLlm,
        selectedVersionByFlow,
        attachedConnectionByFlow,
        toolNameByFlow,
        connections,
      }),
    [
      attachedConnectionByFlow,
      connections,
      initialState?.projectId,
      deploymentDescription,
      deploymentName,
      deploymentType,
      selectedLlm,
      selectedVersionByFlow,
      toolNameByFlow,
    ],
  );

  const buildDeploymentUpdatePayload = useCallback(
    (): DeploymentUpdateRequest =>
      buildDeploymentUpdatePayloadFromState({
        editingDeployment,
        deploymentDescription,
        selectedLlm,
        selectedVersionByFlow,
        attachedConnectionByFlow,
        toolNameByFlow,
        removedFlowIds,
        initialVersionByFlow,
        initialToolNameByFlow,
        initialConnectionsByFlow,
        connections,
      }),
    [
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
      connections,
    ],
  );

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
      initialToolNameByFlow,
      attachedConnectionByFlow,
      setAttachedConnectionByFlow,
      preExistingFlowIds,
      removedFlowIds,
      handleRemoveAttachedFlow,
      handleUndoRemoveFlow,
      hasToolNameErrors,
      setHasToolNameErrors,
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
      initialToolNameByFlow,
      attachedConnectionByFlow,
      preExistingFlowIds,
      removedFlowIds,
      handleRemoveAttachedFlow,
      handleUndoRemoveFlow,
      hasToolNameErrors,
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
