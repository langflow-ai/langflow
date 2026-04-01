import type { FlowDeploymentAttachmentsResponse } from "@/pages/MainPage/pages/deploymentsPage/types";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetFlowDeploymentAttachmentsParams {
  flowId: string;
}

export const useGetFlowDeploymentAttachments: useQueryFunctionType<
  GetFlowDeploymentAttachmentsParams,
  FlowDeploymentAttachmentsResponse
> = ({ flowId }, options) => {
  const { query } = UseRequestProcessor();

  const fn = async (): Promise<FlowDeploymentAttachmentsResponse> => {
    const { data } = await api.get<FlowDeploymentAttachmentsResponse>(
      `${getURL("DEPLOYMENTS")}/flow-attachments/${flowId}`,
    );
    return data;
  };

  return query(["useGetFlowDeploymentAttachments", { flowId }], fn, {
    ...options,
    enabled: !!flowId && options?.enabled !== false,
  });
};
