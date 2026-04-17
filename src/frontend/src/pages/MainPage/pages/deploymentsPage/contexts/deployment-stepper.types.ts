import type { Dispatch, SetStateAction } from "react";
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

export interface FlowVersionSelection {
  versionId: string;
  versionTag: string;
}

export interface DeploymentStepperInitialState {
  projectId?: string;
  selectedVersionByFlow?: Map<string, FlowVersionSelection>;
  initialFlowId?: string;
  initialProvider?: DeploymentProvider;
  initialInstance?: ProviderAccount;
  initialStep?: number;
  editingDeployment?: Deployment;
  initialLlm?: string;
  initialToolNameByFlow?: Map<string, string>;
  initialConnectionsByFlow?: Map<string, string[]>;
}

export interface DeploymentStepperContextType {
  isEditMode: boolean;
  editingDeployment: Deployment | null;
  currentStep: number;
  totalSteps: number;
  minStep: number;
  canGoNext: boolean;
  handleNext: () => void;
  handleBack: () => void;
  selectedProvider: DeploymentProvider | null;
  setSelectedProvider: (provider: DeploymentProvider) => void;
  selectedInstance: ProviderAccount | null;
  setSelectedInstance: (instance: ProviderAccount | null) => void;
  credentials: ProviderCredentials;
  setCredentials: (credentials: ProviderCredentials) => void;
  deploymentType: DeploymentType;
  setDeploymentType: (type: DeploymentType) => void;
  deploymentName: string;
  setDeploymentName: (name: string) => void;
  deploymentDescription: string;
  setDeploymentDescription: (description: string) => void;
  selectedLlm: string;
  setSelectedLlm: (llm: string) => void;
  initialFlowId: string | null;
  connections: ConnectionItem[];
  setConnections: Dispatch<SetStateAction<ConnectionItem[]>>;
  selectedVersionByFlow: Map<string, FlowVersionSelection>;
  handleSelectVersion: (
    flowId: string,
    versionId: string,
    versionTag: string,
  ) => void;
  attachedConnectionByFlow: Map<string, string[]>;
  setAttachedConnectionByFlow: Dispatch<SetStateAction<Map<string, string[]>>>;
  toolNameByFlow: Map<string, string>;
  setToolNameByFlow: Dispatch<SetStateAction<Map<string, string>>>;
  initialToolNameByFlow: Map<string, string>;
  preExistingFlowIds: Set<string>;
  removedFlowIds: Set<string>;
  handleRemoveAttachedFlow: (flowId: string) => void;
  handleUndoRemoveFlow: (flowId: string) => void;
  hasToolNameErrors: boolean;
  setHasToolNameErrors: Dispatch<SetStateAction<boolean>>;
  needsProviderAccountCreation: boolean;
  buildProviderAccountPayload: () => ProviderAccountCreateRequest | null;
  buildDeploymentPayload: (providerId: string) => DeploymentCreateRequest;
  buildDeploymentUpdatePayload: () => DeploymentUpdateRequest;
}
