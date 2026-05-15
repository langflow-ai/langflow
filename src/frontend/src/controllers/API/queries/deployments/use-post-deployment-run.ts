import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DeploymentRunRequest {
  deployment_id: string;
  provider_data: {
    input: string;
    thread_id?: string;
  };
}

export interface DeploymentRunProviderData {
  id?: string | null;
  agent_id?: string | null;
  status?: string | null;
  result?: Record<string, unknown> | null;
  thread_id?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  failed_at?: string | null;
  cancelled_at?: string | null;
  last_error?: string | null;
}

export interface DeploymentRunResponse {
  deployment_id: string;
  provider_data: DeploymentRunProviderData | null;
}

export const usePostDeploymentRun: useMutationFunctionType<
  undefined,
  DeploymentRunRequest,
  DeploymentRunResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const fn = async (
    payload: DeploymentRunRequest,
  ): Promise<DeploymentRunResponse> => {
    const { deployment_id, ...body } = payload;
    const res = await api.post<DeploymentRunResponse>(
      `${getURL("DEPLOYMENTS")}/${encodeURIComponent(deployment_id)}/runs`,
      body,
    );
    return res.data;
  };

  return mutate(["usePostDeploymentRun"], fn, options);
};
