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
import type { DeploymentUpdateRequest } from "@/controllers/API/queries/deployments/use-patch-deployment";
import type { DeploymentCreateRequest } from "@/controllers/API/queries/deployments/use-post-deployment";
import {
  buildDeploymentPayload as buildDeploymentPayloadValue,
  buildDeploymentUpdatePayload as buildDeploymentUpdatePayloadValue,
  buildProviderAccountPayload as buildProviderAccountPayloadValue,
} from "../helpers/deployment-payload-builders";
import { normalizeSelectedFlowVersions } from "../helpers/version-scope";
import type {
  ConnectionItem,
  Deployment,
  DeploymentProvider,
  DeploymentType,
  ProviderAccount,
  ProviderCredentials,
  SelectedFlowVersion,
} from "../types";
import { getDeploymentDisplayName, getSelectedFlowVersionKey } from "../types";

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

interface SelectFlowVersionParams {
  flowId: string;
  flowName: string;
  versionId: string;
  versionTag: string;
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
  handleSelectVersion: (params: SelectFlowVersionParams) => void;
  attachedConnectionByFlow: Map<string, string[]>;
  setAttachedConnectionByFlow: Dispatch<SetStateAction<Map<string, string[]>>>;
  /** User-provided tool names per attached version. Key = attachment key. */
  toolNameByFlow: Map<string, string>;
  setToolNameByFlow: Dispatch<SetStateAction<Map<string, string>>>;
  /** Original tool names from provider before this edit session (edit mode). Key = attachment key. */
  initialToolNameByFlow: Map<string, string>;
  /** Attachment keys that were already attached before this edit session (edit mode). */
  preExistingFlowIds: Set<string>;
  /** Attachment keys that were originally attached but the user chose to detach (edit mode). */
  removedFlowIds: Set<string>;
  handleRemoveAttachedFlow: (attachmentKey: string) => void;
  handleUndoRemoveFlow: (attachmentKey: string) => void;

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
  });

  // Pre-fill from editing deployment when in edit mode.
  const [deploymentType, setDeploymentType] = useState<DeploymentType>(
    editingDeployment?.type ?? "agent",
  );
  const [deploymentName, setDeploymentName] = useState(
    getDeploymentDisplayName(editingDeployment),
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
  const [attachedConnectionByFlow, setAttachedConnectionByFlow] = useState<
    Map<string, string[]>
  >(normalizedInitialConnections);

  const [hasToolNameErrors, setHasToolNameErrors] = useState(false);
  const trimmedDeploymentName = deploymentName.trim();
  const hasDeploymentNameFormatError =
    deploymentName !== "" && trimmedDeploymentName === "";
  const isDeploymentNameValid = trimmedDeploymentName !== "";

  // Edit mode: track which pre-existing flows the user wants to detach.
  const [removedFlowIds, setRemovedFlowIds] = useState<Set<string>>(new Set());
  // Cache removed flow data so undo can restore it.
  const initialVersionByFlow = normalizedInitialVersions;
  const preExistingFlowIds = useMemo(
    () =>
      isEditMode ? new Set(initialVersionByFlow.keys()) : new Set<string>(),
    [isEditMode, initialVersionByFlow],
  );
  const initialToolNameByFlow = normalizedInitialToolNames;
  const initialConnectionsByFlow = normalizedInitialConnections;

  const handleRemoveAttachedFlow = useCallback(
    (attachmentKeyOrFlowId: string) => {
      const resolvedKey = selectedVersionByFlow.has(attachmentKeyOrFlowId)
        ? attachmentKeyOrFlowId
        : Array.from(selectedVersionByFlow.values()).find(
            (entry) => entry.flowId === attachmentKeyOrFlowId,
          )?.key;
      if (!resolvedKey) return;
      if (preExistingFlowIds.has(resolvedKey)) {
        setRemovedFlowIds(
          (prev) => new Set([...Array.from(prev), resolvedKey]),
        );
        return;
      }
      setSelectedVersionByFlow((prev) => {
        const next = new Map(prev);
        next.delete(resolvedKey);
        return next;
      });
      setToolNameByFlow((prev) => {
        const next = new Map(prev);
        next.delete(resolvedKey);
        return next;
      });
      setAttachedConnectionByFlow((prev) => {
        const next = new Map(prev);
        next.delete(resolvedKey);
        return next;
      });
    },
    [preExistingFlowIds, selectedVersionByFlow],
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
      return isDeploymentNameValid && selectedLlm.trim() !== "";
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
    ({ flowId, flowName, versionId, versionTag }: SelectFlowVersionParams) => {
      setSelectedVersionByFlow((prev) => {
        const next = new Map(prev);
        const key = getSelectedFlowVersionKey(flowId, versionId);
        next.set(key, {
          key,
          flowId,
          flowName,
          versionId,
          versionTag,
        });
        return next;
      });
    },
    [],
  );

  const needsProviderAccountCreation =
    selectedInstance === null && hasValidCredentials;

  const buildProviderAccountPayload = useCallback(
    () =>
      buildProviderAccountPayloadValue({
        credentials,
        hasValidCredentials,
      }),
    [credentials, hasValidCredentials],
  );

  const buildDeploymentPayload = useCallback(
    (providerId: string): DeploymentCreateRequest =>
      buildDeploymentPayloadValue({
        attachedConnectionByFlow,
        connections,
        deploymentDescription,
        deploymentName,
        deploymentType,
        isDeploymentNameValid,
        projectId: initialState?.projectId,
        providerId,
        removedFlowIds,
        selectedLlm,
        selectedVersionByFlow,
        toolNameByFlow,
      }),
    [
      attachedConnectionByFlow,
      connections,
      deploymentDescription,
      deploymentName,
      deploymentType,
      initialState?.projectId,
      isDeploymentNameValid,
      removedFlowIds,
      selectedLlm,
      selectedVersionByFlow,
      toolNameByFlow,
    ],
  );

  const buildDeploymentUpdatePayload =
    useCallback((): DeploymentUpdateRequest => {
      return buildDeploymentUpdatePayloadValue({
        attachedConnectionByFlow,
        connections,
        deploymentDescription,
        deploymentName,
        editingDeployment,
        initialLlm: initialState?.initialLlm ?? "",
        initialConnectionsByFlow,
        initialToolNameByFlow,
        initialVersionByFlow,
        isDeploymentNameValid,
        removedFlowIds,
        selectedLlm,
        selectedVersionByFlow,
        toolNameByFlow,
      });
    }, [
      attachedConnectionByFlow,
      connections,
      deploymentDescription,
      deploymentName,
      editingDeployment,
      initialConnectionsByFlow,
      initialToolNameByFlow,
      initialVersionByFlow,
      isDeploymentNameValid,
      removedFlowIds,
      selectedLlm,
      selectedVersionByFlow,
      toolNameByFlow,
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
      isDeploymentNameValid,
      hasDeploymentNameFormatError,
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
