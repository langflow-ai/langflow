import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DeploymentExecutionRequest {
  deployment_id: string;
  provider_data: {
    input: string;
    thread_id?: string;
  };
}

export interface DeploymentExecutionProviderData {
  execution_id?: string | null;
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

export interface DeploymentExecutionResponse {
  deployment_id: string;
  provider_data: DeploymentExecutionProviderData | null;
}

export const usePostDeploymentExecution: useMutationFunctionType<
  undefined,
  DeploymentExecutionRequest,
  DeploymentExecutionResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const fn = async (
    payload: DeploymentExecutionRequest,
  ): Promise<DeploymentExecutionResponse> => {
    const { deployment_id, ...body } = payload;
    const res = await api.post<DeploymentExecutionResponse>(
      `${getURL("DEPLOYMENTS")}/${encodeURIComponent(deployment_id)}/executions`,
      body,
    );
    return res.data;
  };

  return mutate(["usePostDeploymentExecution"], fn, options);
};
