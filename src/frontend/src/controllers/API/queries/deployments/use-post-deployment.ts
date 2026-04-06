import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DeploymentConnectionCredential {
  key: string;
  value: string;
  source: "raw" | "variable";
}

export interface DeploymentConnectionPayload {
  app_id: string;
  credentials: DeploymentConnectionCredential[];
}

export interface DeploymentCreateFlowItem {
  flow_version_id: string;
  app_ids: string[];
  tool_name?: string;
}

export interface DeploymentCreateUpsertToolItem {
  tool_id: string;
  add_app_ids: string[];
}

export interface DeploymentCreateProviderData {
  llm: string;
  connections: DeploymentConnectionPayload[];
  add_flows: DeploymentCreateFlowItem[];
  upsert_tools?: DeploymentCreateUpsertToolItem[];
  existing_agent_id?: string;
}

export interface DeploymentCreateRequest {
  provider_id: string;
  name: string;
  description: string;
  type: string;
  provider_data: DeploymentCreateProviderData;
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
