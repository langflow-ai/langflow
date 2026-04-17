import { useCallback } from "react";
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
  DeploymentStepperInitialState,
  FlowVersionSelection,
} from "../contexts/deployment-stepper.types";
import type {
  ConnectionItem,
  Deployment,
  DeploymentType,
  ProviderAccount,
  ProviderCredentials,
} from "../types";

interface UseDeploymentPayloadBuildersParams {
  initialState?: DeploymentStepperInitialState;
  editingDeployment: Deployment | null;
  selectedInstance: ProviderAccount | null;
  credentials: ProviderCredentials;
  hasValidCredentials: boolean;
  deploymentType: DeploymentType;
  deploymentName: string;
  deploymentDescription: string;
  selectedLlm: string;
  connections: ConnectionItem[];
  selectedVersionByFlow: Map<string, FlowVersionSelection>;
  attachedConnectionByFlow: Map<string, string[]>;
  toolNameByFlow: Map<string, string>;
  initialVersionByFlow: Map<string, FlowVersionSelection>;
  initialToolNameByFlow: Map<string, string>;
  initialConnectionsByFlow: Map<string, string[]>;
  removedFlowIds: Set<string>;
}

export function useDeploymentPayloadBuilders({
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
}: UseDeploymentPayloadBuildersParams) {
  const needsProviderAccountCreation =
    selectedInstance === null && hasValidCredentials;

  const buildProviderAccountPayload =
    useCallback((): ProviderAccountCreateRequest | null => {
      if (!hasValidCredentials) {
        return null;
      }

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
        const connection = connections.find((item) => item.id === id);
        if (!connection?.isNew) {
          continue;
        }

        const connectionCredentials: DeploymentConnectionPayload["credentials"] =
          Object.entries(connection.environmentVariables).map(
            ([key, value]) => {
              const isGlobalVar = connection.globalVarKeys?.has(key) ?? false;

              return {
                key,
                value,
                source: isGlobalVar ? "variable" : "raw",
              };
            },
          );

        payloads.push({
          app_id: id,
          credentials: connectionCredentials,
        });
      }

      return payloads;
    },
    [connections],
  );

  const buildDeploymentPayload = useCallback(
    (providerId: string): DeploymentCreateRequest => {
      const allConnectionIds = new Set<string>();
      Array.from(attachedConnectionByFlow.values()).forEach((ids) => {
        ids.forEach((id) => allConnectionIds.add(id));
      });

      const addFlows: DeploymentCreateRequest["provider_data"]["add_flows"] =
        [];
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
        ...(initialState?.projectId
          ? { project_id: initialState.projectId }
          : {}),
        name: deploymentName,
        description: deploymentDescription,
        type: deploymentType,
        provider_data: {
          llm: selectedLlm,
          add_flows: addFlows,
          connections: buildConnectionPayloads(allConnectionIds),
        },
      };
    },
    [
      attachedConnectionByFlow,
      buildConnectionPayloads,
      deploymentDescription,
      deploymentName,
      deploymentType,
      initialState?.projectId,
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

      if (deploymentDescription !== (editingDeployment.description ?? "")) {
        result.description = deploymentDescription;
      }

      const upsertFlows: DeploymentUpdateFlowItem[] = [];

      for (const [flowId, versionEntry] of Array.from(selectedVersionByFlow)) {
        if (initialVersionByFlow.has(flowId)) {
          continue;
        }

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
        if (!initialVersionByFlow.has(flowId)) {
          continue;
        }

        const currentName = toolNameByFlow.get(flowId)?.trim() ?? "";
        const originalName = initialToolNameByFlow.get(flowId)?.trim() ?? "";
        const nameChanged = currentName && currentName !== originalName;

        const currentConnections = attachedConnectionByFlow.get(flowId) ?? [];
        const originalConnections = initialConnectionsByFlow.get(flowId) ?? [];
        const originalSet = new Set(originalConnections);
        const currentSet = new Set(currentConnections);
        const addAppIds = currentConnections.filter(
          (id) => !originalSet.has(id),
        );
        const removeAppIds = originalConnections.filter(
          (id) => !currentSet.has(id),
        );

        if (nameChanged || addAppIds.length > 0 || removeAppIds.length > 0) {
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
        flowItem.add_app_ids.forEach((id) => newConnectionIds.add(id));
      });
      const connectionPayloads = buildConnectionPayloads(newConnectionIds);

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
          ...(connectionPayloads.length > 0 && {
            connections: connectionPayloads,
          }),
        };
        result.provider_data = providerData;
      }

      if (result.description === undefined && !result.provider_data) {
        result.description = deploymentDescription;
      }

      return result;
    }, [
      attachedConnectionByFlow,
      buildConnectionPayloads,
      deploymentDescription,
      editingDeployment,
      initialConnectionsByFlow,
      initialToolNameByFlow,
      initialVersionByFlow,
      removedFlowIds,
      selectedLlm,
      selectedVersionByFlow,
      toolNameByFlow,
    ]);

  return {
    needsProviderAccountCreation,
    buildProviderAccountPayload,
    buildDeploymentPayload,
    buildDeploymentUpdatePayload,
  };
}
