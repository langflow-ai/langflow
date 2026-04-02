import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DeploymentCreateRequest {
  provider_id: string;
  spec: {
    name: string;
    description: string;
    type: string;
  };
  provider_data: {
    llm: string;
    operations: Array<{
      op: "bind";
      flow_version_id: string;
      app_ids: string[];
      tool_name?: string;
    }>;
    connections: {
      existing_app_ids: string[];
      raw_payloads: Array<{
        app_id: string;
        environment_variables: Record<string, { value: string; source: "raw" }>;
      }>;
    };
  };
}

export const usePostDeployment: useMutationFunctionType<
  undefined,
  DeploymentCreateRequest
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async (payload: DeploymentCreateRequest) => {
    const res = await api.post(`${getURL("DEPLOYMENTS")}`, payload);
    return res.data;
  };

  return mutate(["usePostDeployment"], fn, {
    ...options,
    onSuccess: () => {
      return queryClient.refetchQueries({ queryKey: ["useGetDeployments"] });
    },
  });
};
