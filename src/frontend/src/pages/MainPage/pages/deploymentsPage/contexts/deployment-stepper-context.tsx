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
import type {
  ConnectionItem,
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
}

interface DeploymentStepperContextType {
  // Navigation
  currentStep: number;
  canGoNext: boolean;
  handleNext: () => void;
  handleBack: () => void;

  // Step 1: Provider
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

  // Deploy
  needsProviderAccountCreation: boolean;
  buildProviderAccountPayload: () => ProviderAccountCreateRequest | null;
  buildDeploymentPayload: (providerId: string) => DeploymentCreateRequest;
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
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedProvider, setSelectedProviderState] =
    useState<DeploymentProvider | null>(null);
  const [selectedInstance, setSelectedInstance] =
    useState<ProviderAccount | null>(null);
  const [credentials, setCredentials] = useState<ProviderCredentials>({
    name: "",
    provider_key: "",
    provider_url: "",
    api_key: "",
  });
  const [deploymentType, setDeploymentType] = useState<DeploymentType>("agent");
  const [deploymentName, setDeploymentName] = useState("");
  const [deploymentDescription, setDeploymentDescription] = useState("");
  const [selectedLlm, setSelectedLlm] = useState("");
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

  const canGoNext =
    (currentStep === 1 &&
      selectedProvider !== null &&
      (selectedInstance !== null || hasValidCredentials)) ||
    (currentStep === 2 &&
      deploymentName.trim() !== "" &&
      selectedLlm.trim() !== "") ||
    (currentStep === 3 && attachedConnectionByFlow.size > 0) ||
    currentStep === 4;

  const handleNext = useCallback(() => {
    setCurrentStep((prev) => (prev < 4 ? prev + 1 : prev));
  }, []);

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
        // derive from selectedProvider.id when multi-provider support is added
        provider_key: "watsonx-orchestrate",
        provider_url: credentials.provider_url.trim(),
        provider_data: { api_key: credentials.api_key.trim() },
      };
    }, [credentials, hasValidCredentials]);

  const buildDeploymentPayload = useCallback(
    (providerId: string): DeploymentCreateRequest => {
      // Collect all unique connection IDs referenced across all flows
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

  const value = useMemo<DeploymentStepperContextType>(
    () => ({
      currentStep,
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
    }),
    [
      currentStep,
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
