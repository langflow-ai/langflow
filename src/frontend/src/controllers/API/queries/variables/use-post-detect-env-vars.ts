import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type DetectEnvVarsPayload = {
  flow_version_ids: string[];
};

export type DetectEnvVarsResponse = {
  variables: string[];
};

export const usePostDetectEnvVars: useMutationFunctionType<
  undefined,
  DetectEnvVarsPayload,
  DetectEnvVarsResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const fn = async (
    payload: DetectEnvVarsPayload,
  ): Promise<DetectEnvVarsResponse> => {
    const { data } = await api.post<DetectEnvVarsResponse>(
      `${getURL("VARIABLES")}/detections`,
      payload,
    );
    return data;
  };

  return mutate(["usePostDetectEnvVars"], fn, options);
};
