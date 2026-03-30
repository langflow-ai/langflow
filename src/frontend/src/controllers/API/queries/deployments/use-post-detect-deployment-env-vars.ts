import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type DetectDeploymentEnvVarsPayload = {
  reference_ids: string[];
};

export type DetectedEnvVar = {
  key: string;
  global_variable_name?: string | null;
};

export type DetectDeploymentEnvVarsResponse = {
  variables: DetectedEnvVar[];
};

export const usePostDetectDeploymentEnvVars: useMutationFunctionType<
  undefined,
  DetectDeploymentEnvVarsPayload,
  DetectDeploymentEnvVarsResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const fn = async (
    payload: DetectDeploymentEnvVarsPayload,
  ): Promise<DetectDeploymentEnvVarsResponse> => {
    const { data } = await api.post<DetectDeploymentEnvVarsResponse>(
      `${getURL("DEPLOYMENTS")}/variables/detections`,
      payload,
    );
    return data;
  };

  return mutate(["usePostDetectDeploymentEnvVars"], fn, options);
};
