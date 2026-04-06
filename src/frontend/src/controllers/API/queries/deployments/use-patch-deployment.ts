import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type {
  DeploymentConnectionPayload,
  DeploymentCreateUpsertToolItem,
} from "./use-post-deployment";

export interface DeploymentUpdateFlowItem {
  flow_version_id: string;
  add_app_ids: string[];
  remove_app_ids: string[];
  tool_name?: string;
}

export interface DeploymentUpdateUpsertToolItem
  extends DeploymentCreateUpsertToolItem {
  remove_app_ids?: string[];
}

export interface DeploymentUpdateProviderData {
  llm?: string;
  connections?: DeploymentConnectionPayload[];
  upsert_flows?: DeploymentUpdateFlowItem[];
  remove_flows?: string[];
  upsert_tools?: DeploymentUpdateUpsertToolItem[];
  remove_tools?: string[];
}

export interface DeploymentUpdateRequest {
  deployment_id: string;
  name?: string;
  description?: string;
  provider_data?: DeploymentUpdateProviderData;
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
