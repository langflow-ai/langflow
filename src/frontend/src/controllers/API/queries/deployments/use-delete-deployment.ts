import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteDeploymentParams {
  deployment_id: string;
}

export const useDeleteDeployment: useMutationFunctionType<
  undefined,
  DeleteDeploymentParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async ({ deployment_id }: DeleteDeploymentParams) => {
    await api.delete(`${getURL("DEPLOYMENTS")}/${deployment_id}`);
  };

  return mutate(["useDeleteDeployment"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.refetchQueries({ queryKey: ["useGetDeployments"] });
      options?.onSuccess?.(...args);
    },
  });
};
