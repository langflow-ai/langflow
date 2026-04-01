import type {
  Deployment,
  DeploymentType,
  FlowDeploymentAttachment,
  FlowDeploymentAttachmentsResponse,
  ProviderAccount,
} from "@/pages/MainPage/pages/deploymentsPage/types";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetFlowDeploymentAttachmentsParams {
  flowId: string;
}

interface ProviderAccountListResponse {
  providers: ProviderAccount[];
}

interface DeploymentListResponse {
  deployments: Deployment[];
}

function flattenToAttachments(
  deployments: Deployment[],
  providerKey: string,
): FlowDeploymentAttachment[] {
  const result: FlowDeploymentAttachment[] = [];
  for (const dep of deployments) {
    if (!dep.matched_attachments) continue;
    for (const att of dep.matched_attachments) {
      if (!att.provider_snapshot_id) continue;
      result.push({
        deployment_id: dep.id,
        deployment_name: dep.name,
        deployment_type: dep.type as DeploymentType,
        provider_snapshot_id: att.provider_snapshot_id,
        provider_key: providerKey,
        flow_version_id: att.flow_version_id,
        updated_at: dep.updated_at,
      });
    }
  }
  return result;
}

export const useGetFlowDeploymentAttachments: useQueryFunctionType<
  GetFlowDeploymentAttachmentsParams,
  FlowDeploymentAttachmentsResponse
> = ({ flowId }, options) => {
  const { query } = UseRequestProcessor();

  const fn = async (): Promise<FlowDeploymentAttachmentsResponse> => {
    const { data: providerData } = await api.get<ProviderAccountListResponse>(
      `${getURL("DEPLOYMENT_PROVIDER_ACCOUNTS")}`,
      { params: { page: 1, size: 50 } },
    );

    const providers = providerData?.providers ?? [];
    const allAttachments: FlowDeploymentAttachment[] = [];

    for (const provider of providers) {
      const { data } = await api.get<DeploymentListResponse>(
        `${getURL("DEPLOYMENTS")}`,
        {
          params: {
            provider_id: provider.id,
            flow_ids: flowId,
            page: 1,
            size: 50,
          },
        },
      );
      allAttachments.push(
        ...flattenToAttachments(data.deployments, provider.provider_key),
      );
    }

    return { attachments: allAttachments };
  };

  return query(["useGetFlowDeploymentAttachments", { flowId }], fn, {
    ...options,
    enabled: !!flowId && options?.enabled !== false,
  });
};
