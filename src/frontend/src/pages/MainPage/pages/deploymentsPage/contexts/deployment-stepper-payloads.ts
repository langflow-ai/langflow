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
  DeploymentType,
  ProviderCredentials,
} from "../types";

type FlowVersionEntry = {
  versionId: string;
  versionTag: string;
};

interface BaseConnectionPayloadArgs {
  connectionIds: Iterable<string>;
  connections: ConnectionItem[];
}

interface ProviderAccountPayloadArgs {
  credentials: ProviderCredentials;
  hasValidCredentials: boolean;
}

interface DeploymentCreatePayloadArgs {
  providerId: string;
  projectId?: string;
  deploymentName: string;
  deploymentDescription: string;
  deploymentType: DeploymentType;
  selectedLlm: string;
  selectedVersionByFlow: Map<string, FlowVersionEntry>;
  attachedConnectionByFlow: Map<string, string[]>;
  toolNameByFlow: Map<string, string>;
  connections: ConnectionItem[];
}

interface DeploymentUpdatePayloadArgs {
  editingDeployment: Deployment | null;
  deploymentDescription: string;
  selectedLlm: string;
  selectedVersionByFlow: Map<string, FlowVersionEntry>;
  attachedConnectionByFlow: Map<string, string[]>;
  toolNameByFlow: Map<string, string>;
  removedFlowIds: Set<string>;
  initialVersionByFlow: Map<string, FlowVersionEntry>;
  initialToolNameByFlow: Map<string, string>;
  initialConnectionsByFlow: Map<string, string[]>;
  connections: ConnectionItem[];
}

function createConnectionsById(connections: ConnectionItem[]) {
  return new Map(connections.map((connection) => [connection.id, connection]));
}

export function buildConnectionPayloads({
  connectionIds,
  connections,
}: BaseConnectionPayloadArgs): DeploymentCreateRequest["provider_data"]["connections"] {
  const payloads: DeploymentCreateRequest["provider_data"]["connections"] = [];
  const connectionsById = createConnectionsById(connections);
  const uniqueIds = Array.from(new Set(connectionIds));

  for (const id of uniqueIds) {
    const connection = connectionsById.get(id);
    if (!connection?.isNew) continue;

    const credentials: DeploymentConnectionPayload["credentials"] =
      Object.entries(connection.environmentVariables).map(([key, value]) => ({
        key,
        value,
        source: connection.globalVarKeys?.has(key) ? "variable" : "raw",
      }));

    payloads.push({
      app_id: id,
      credentials,
    });
  }

  return payloads;
}

export function buildProviderAccountPayload({
  credentials,
  hasValidCredentials,
}: ProviderAccountPayloadArgs): ProviderAccountCreateRequest | null {
  if (!hasValidCredentials) return null;

  return {
    name: credentials.name.trim(),
    provider_key: "watsonx-orchestrate",
    provider_data: {
      url: credentials.url.trim(),
      api_key: credentials.api_key.trim(),
      api_key_source: credentials.api_key_source,
    },
  };
}

export function buildDeploymentPayload({
  providerId,
  projectId,
  deploymentName,
  deploymentDescription,
  deploymentType,
  selectedLlm,
  selectedVersionByFlow,
  attachedConnectionByFlow,
  toolNameByFlow,
  connections,
}: DeploymentCreatePayloadArgs): DeploymentCreateRequest {
  const allConnectionIds = new Set<string>();
  attachedConnectionByFlow.forEach((ids) => {
    ids.forEach((id) => {
      allConnectionIds.add(id);
    });
  });

  const addFlows: DeploymentCreateRequest["provider_data"]["add_flows"] = [];
  for (const [flowId, versionEntry] of Array.from(selectedVersionByFlow)) {
    const connectionIds = attachedConnectionByFlow.get(flowId) ?? [];
    const customToolName = toolNameByFlow.get(flowId)?.trim();
    addFlows.push({
      flow_version_id: versionEntry.versionId,
      app_ids: connectionIds,
      ...(customToolName && { tool_name: customToolName }),
    });
  }

  return {
    provider_id: providerId,
    ...(projectId ? { project_id: projectId } : {}),
    name: deploymentName,
    description: deploymentDescription,
    type: deploymentType,
    provider_data: {
      llm: selectedLlm,
      add_flows: addFlows,
      connections: buildConnectionPayloads({
        connectionIds: allConnectionIds,
        connections,
      }),
    },
  };
}

export function buildDeploymentUpdatePayload({
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
}: DeploymentUpdatePayloadArgs): DeploymentUpdateRequest {
  if (!editingDeployment) {
    throw new Error("buildDeploymentUpdatePayload called outside edit mode");
  }

  const result: DeploymentUpdateRequest = {
    deployment_id: editingDeployment.id,
  };

  const descriptionChanged =
    deploymentDescription !== (editingDeployment.description ?? "");
  if (descriptionChanged) {
    result.description = deploymentDescription;
  }

  const upsertFlows: DeploymentUpdateFlowItem[] = [];

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

  for (const [flowId, versionEntry] of Array.from(selectedVersionByFlow)) {
    if (!initialVersionByFlow.has(flowId)) continue;

    const currentName = toolNameByFlow.get(flowId)?.trim() ?? "";
    const originalName = initialToolNameByFlow.get(flowId)?.trim() ?? "";
    const nameChanged = currentName !== "" && currentName !== originalName;

    const currentConnections = attachedConnectionByFlow.get(flowId) ?? [];
    const originalConnections = initialConnectionsByFlow.get(flowId) ?? [];
    const originalSet = new Set(originalConnections);
    const currentSet = new Set(currentConnections);

    const addAppIds = currentConnections.filter((id) => !originalSet.has(id));
    const removeAppIds = originalConnections.filter(
      (id) => !currentSet.has(id),
    );
    const connectionsChanged = addAppIds.length > 0 || removeAppIds.length > 0;

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

  const newConnectionIds = new Set<string>();
  upsertFlows.forEach((flowItem) => {
    flowItem.add_app_ids.forEach((id) => {
      newConnectionIds.add(id);
    });
  });

  const connectionPayloads = buildConnectionPayloads({
    connectionIds: newConnectionIds,
    connections,
  });

  if (
    selectedLlm ||
    upsertFlows.length > 0 ||
    removeFlows.length > 0 ||
    connectionPayloads.length > 0
  ) {
    const providerData: DeploymentUpdateProviderData = {
      ...(selectedLlm && { llm: selectedLlm }),
      ...(upsertFlows.length > 0 && { upsert_flows: upsertFlows }),
      ...(removeFlows.length > 0 && { remove_flows: removeFlows }),
      ...(connectionPayloads.length > 0 && { connections: connectionPayloads }),
    };
    result.provider_data = providerData;
  }

  if (result.description === undefined && !result.provider_data) {
    result.description = deploymentDescription;
  }

  return result;
}
