import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { DeploymentExecutionResponse } from "./use-post-deployment-execution";

export interface GetDeploymentExecutionParams {
  deployment_id: string;
  execution_id: string;
}

export const useGetDeploymentExecution: useMutationFunctionType<
  undefined,
  GetDeploymentExecutionParams,
  DeploymentExecutionResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const fn = async ({
    deployment_id,
    execution_id,
  }: GetDeploymentExecutionParams): Promise<DeploymentExecutionResponse> => {
    const res = await api.get<DeploymentExecutionResponse>(
      `${getURL("DEPLOYMENTS")}/${encodeURIComponent(deployment_id)}/executions/${encodeURIComponent(execution_id)}`,
    );
    return res.data;
  };

  return mutate(["useGetDeploymentExecution"], fn, options);
};
