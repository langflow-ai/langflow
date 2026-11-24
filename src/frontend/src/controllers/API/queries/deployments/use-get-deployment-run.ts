import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { DeploymentRunResponse } from "./use-post-deployment-run";

export interface GetDeploymentRunParams {
  deployment_id: string;
  run_id: string;
}

export const useGetDeploymentRun: useMutationFunctionType<
  undefined,
  GetDeploymentRunParams,
  DeploymentRunResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const fn = async ({
    deployment_id,
    run_id,
  }: GetDeploymentRunParams): Promise<DeploymentRunResponse> => {
    const res = await api.get<DeploymentRunResponse>(
      `${getURL("DEPLOYMENTS")}/${encodeURIComponent(deployment_id)}/runs/${encodeURIComponent(run_id)}`,
    );
    return res.data;
  };

  return mutate(["useGetDeploymentRun"], fn, options);
};
