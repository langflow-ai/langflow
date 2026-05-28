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
  SelectedFlowVersion,
} from "../types";
import {
  DEFAULT_FLOW_NAME,
  getDefaultDeploymentToolName,
  getDeploymentDisplayName,
  WXO_PROVIDER_KEY,
} from "../types";
import {
  getFlowVersionCount,
  getScopedValueForUniqueFlowVersion,
  getValueByAttachmentKeyOrFlowId,
} from "./version-scope";

function getScopedToolName(
  map: Map<string, string>,
  attachmentKey: string,
  flowId: string,
  versionMap: Map<string, SelectedFlowVersion>,
): string | undefined {
  return getScopedValueForUniqueFlowVersion(
    map,
    attachmentKey,
    flowId,
    getFlowVersionCount(versionMap.values(), flowId),
  );
}

export function buildProviderAccountPayload({
  credentials,
  hasValidCredentials,
}: {
  credentials: ProviderCredentials;
  hasValidCredentials: boolean;
}): ProviderAccountCreateRequest | null {
  if (!hasValidCredentials) return null;
  return {
    name: credentials.name.trim(),
    provider_key: WXO_PROVIDER_KEY,
    provider_data: {
      url: credentials.url.trim(),
      api_key: credentials.api_key.trim(),
    },
  };
}

export function buildConnectionPayloads({
  connectionIds,
  connections,
}: {
  connectionIds: Iterable<string>;
  connections: ConnectionItem[];
}): DeploymentCreateRequest["provider_data"]["connections"] {
  const payloads: DeploymentCreateRequest["provider_data"]["connections"] = [];
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
}

export function buildDeploymentPayload({
  attachedConnectionByFlow,
  connections,
  deploymentDescription,
  deploymentName,
  deploymentType,
  isDeploymentNameValid,
  projectId,
  providerId,
  removedFlowIds,
  selectedLlm,
  selectedVersionByFlow,
  toolNameByFlow,
}: {
  attachedConnectionByFlow: Map<string, string[]>;
  connections: ConnectionItem[];
  deploymentDescription: string;
  deploymentName: string;
  deploymentType: DeploymentType;
  isDeploymentNameValid: boolean;
  projectId?: string;
  providerId: string;
  removedFlowIds: Set<string>;
  selectedLlm: string;
  selectedVersionByFlow: Map<string, SelectedFlowVersion>;
  toolNameByFlow: Map<string, string>;
}): DeploymentCreateRequest {
  if (!isDeploymentNameValid) {
    throw new Error("Deployment name is required");
  }
  const allConnectionIds = new Set<string>();
  Array.from(attachedConnectionByFlow.values()).forEach((ids) => {
    ids.forEach((id) => allConnectionIds.add(id));
  });

  const addFlows: DeploymentCreateRequest["provider_data"]["add_flows"] = [];
  for (const [attachmentKey, versionEntry] of Array.from(
    selectedVersionByFlow,
  )) {
    if (removedFlowIds.has(attachmentKey)) continue;
    const connectionIds =
      getValueByAttachmentKeyOrFlowId(
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
      getDefaultDeploymentToolName(versionEntry.flowName ?? DEFAULT_FLOW_NAME);
    addFlows.push({
      flow_version_id: versionEntry.versionId,
      app_ids: connectionIds,
      tool_display_name: resolvedToolName,
    });
  }

  const connectionPayloads = buildConnectionPayloads({
    connectionIds: allConnectionIds,
    connections,
  });

  return {
    provider_id: providerId,
    ...(projectId ? { project_id: projectId } : {}),
    description: deploymentDescription,
    type: deploymentType,
    provider_data: {
      display_name: deploymentName.trim(),
      llm: selectedLlm,
      add_flows: addFlows,
      connections: connectionPayloads,
    },
  };
}

export function buildDeploymentUpdatePayload({
  attachedConnectionByFlow,
  connections,
  deploymentDescription,
  deploymentName,
  editingDeployment,
  initialLlm,
  initialConnectionsByFlow,
  initialToolNameByFlow,
  initialVersionByFlow,
  isDeploymentNameValid,
  removedFlowIds,
  selectedLlm,
  selectedVersionByFlow,
  toolNameByFlow,
}: {
  attachedConnectionByFlow: Map<string, string[]>;
  connections: ConnectionItem[];
  deploymentDescription: string;
  deploymentName: string;
  editingDeployment: Deployment | null;
  initialLlm: string;
  initialConnectionsByFlow: Map<string, string[]>;
  initialToolNameByFlow: Map<string, string>;
  initialVersionByFlow: Map<string, SelectedFlowVersion>;
  isDeploymentNameValid: boolean;
  removedFlowIds: Set<string>;
  selectedLlm: string;
  selectedVersionByFlow: Map<string, SelectedFlowVersion>;
  toolNameByFlow: Map<string, string>;
}): DeploymentUpdateRequest {
  if (!editingDeployment) {
    throw new Error("buildDeploymentUpdatePayload called outside edit mode");
  }
  if (!isDeploymentNameValid) {
    throw new Error("Deployment name is required");
  }

  const result: DeploymentUpdateRequest = {
    deployment_id: editingDeployment.id,
  };

  if (deploymentDescription !== (editingDeployment.description ?? "")) {
    result.description = deploymentDescription;
  }
  const displayNameChanged =
    deploymentName.trim() !== getDeploymentDisplayName(editingDeployment);

  const upsertFlows: DeploymentUpdateFlowItem[] = [];

  for (const [attachmentKey, versionEntry] of Array.from(
    selectedVersionByFlow,
  )) {
    if (removedFlowIds.has(attachmentKey)) continue;
    if (initialVersionByFlow.has(attachmentKey)) continue;
    const connectionIds =
      getValueByAttachmentKeyOrFlowId(
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
      getDefaultDeploymentToolName(versionEntry.flowName ?? DEFAULT_FLOW_NAME);
    upsertFlows.push({
      flow_version_id: versionEntry.versionId,
      add_app_ids: connectionIds,
      remove_app_ids: [],
      tool_display_name: resolvedToolName,
    });
  }

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
      getValueByAttachmentKeyOrFlowId(
        attachedConnectionByFlow,
        attachmentKey,
        versionEntry.flowId,
      ) ?? [];
    const originalConnections =
      getValueByAttachmentKeyOrFlowId(
        initialConnectionsByFlow,
        attachmentKey,
        versionEntry.flowId,
      ) ?? [];
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
        ...(nameChanged && { tool_display_name: currentName }),
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

  const newConnectionIds = new Set<string>();
  upsertFlows.forEach((flowItem) => {
    flowItem.add_app_ids.forEach((id) => newConnectionIds.add(id));
  });
  const connectionPayloads = buildConnectionPayloads({
    connectionIds: newConnectionIds,
    connections,
  });

  const llmChanged = selectedLlm !== initialLlm;
  const llmToSend = llmChanged ? selectedLlm : undefined;
  if (
    llmToSend ||
    displayNameChanged ||
    upsertFlows.length > 0 ||
    removeFlows.length > 0 ||
    connectionPayloads.length > 0
  ) {
    const providerData: DeploymentUpdateProviderData = {
      ...(displayNameChanged && { display_name: deploymentName.trim() }),
      ...(llmToSend && { llm: llmToSend }),
      ...(upsertFlows.length > 0 && { upsert_flows: upsertFlows }),
      ...(removeFlows.length > 0 && { remove_flows: removeFlows }),
      ...(connectionPayloads.length > 0 && {
        connections: connectionPayloads,
      }),
    };
    result.provider_data = providerData;
  }

  return result;
}

export function isDeploymentUpdatePayloadEmpty(
  payload: DeploymentUpdateRequest,
): boolean {
  return (
    payload.description === undefined && payload.provider_data === undefined
  );
}
