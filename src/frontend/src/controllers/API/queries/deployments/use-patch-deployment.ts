import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DeploymentUpdateRequest {
  deployment_id: string;
  spec?: {
    name?: string;
    description?: string;
  };
  provider_data?: Record<string, unknown>;
}

export const usePatchDeployment: useMutationFunctionType<
  undefined,
  DeploymentUpdateRequest
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async (payload: DeploymentUpdateRequest) => {
    const { deployment_id, ...body } = payload;
    const res = await api.patch(
      `${getURL("DEPLOYMENTS")}/${deployment_id}`,
      body,
    );
    return res.data;
  };

  return mutate(["usePatchDeployment"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.refetchQueries({ queryKey: ["useGetDeployments"] });
      queryClient.removeQueries({
        queryKey: ["useGetDeploymentAttachments"],
      });
      queryClient.removeQueries({
        queryKey: ["useGetDeployment"],
      });
      options?.onSuccess?.(...args);
    },
  });
};
