import type { ReactNode } from "react";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";
import { useDeploymentEditSession } from "../hooks/use-deployment-edit-session";
import { useDeploymentPayloadBuilders } from "../hooks/use-deployment-payload-builders";
import { useDeploymentStepperNavigation } from "../hooks/use-deployment-stepper-navigation";
import type {
  ConnectionItem,
  DeploymentProvider,
  DeploymentType,
  ProviderAccount,
  ProviderCredentials,
} from "../types";
import type {
  DeploymentStepperContextType,
  DeploymentStepperInitialState,
} from "./deployment-stepper.types";

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
  const [connections, setConnections] = useState<ConnectionItem[]>([]);
  const [hasToolNameErrors, setHasToolNameErrors] = useState(false);

  const hasValidCredentials =
    credentials.name.trim() !== "" &&
    credentials.api_key.trim() !== "" &&
    credentials.url.trim() !== "";

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

  const {
    selectedVersionByFlow,
    toolNameByFlow,
    attachedConnectionByFlow,
    removedFlowIds,
    initialVersionByFlow,
    initialToolNameByFlow,
    initialConnectionsByFlow,
    preExistingFlowIds,
    setToolNameByFlow,
    setAttachedConnectionByFlow,
    handleSelectVersion,
    handleRemoveAttachedFlow,
    handleUndoRemoveFlow,
  } = useDeploymentEditSession(initialState);

  const {
    currentStep,
    totalSteps,
    minStep,
    canGoNext,
    handleNext,
    handleBack,
  } = useDeploymentStepperNavigation({
    isEditMode,
    initialStep: initialState?.initialStep,
    selectedProvider,
    selectedInstance,
    hasValidCredentials,
    deploymentName,
    selectedLlm,
    attachedFlowCount: selectedVersionByFlow.size,
    hasToolNameErrors,
  });

  const {
    needsProviderAccountCreation,
    buildProviderAccountPayload,
    buildDeploymentPayload,
    buildDeploymentUpdatePayload,
  } = useDeploymentPayloadBuilders({
    initialState,
    editingDeployment,
    selectedInstance,
    credentials,
    hasValidCredentials,
    deploymentType,
    deploymentName,
    deploymentDescription,
    selectedLlm,
    connections,
    selectedVersionByFlow,
    attachedConnectionByFlow,
    toolNameByFlow,
    initialVersionByFlow,
    initialToolNameByFlow,
    initialConnectionsByFlow,
    removedFlowIds,
  });

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
