import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { ApiResponse, UpdateVersionRequest, PromptVersion } from "./types";

interface UpdateVersionPayload extends UpdateVersionRequest {
  promptId: string;
  version: number;
}

export const useUpdateVersion: useMutationFunctionType<
  undefined,
  UpdateVersionPayload
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateVersionFn = async (payload: UpdateVersionPayload): Promise<PromptVersion> => {
    const { promptId, version, ...versionData } = payload;
    const response = await api.put<ApiResponse<PromptVersion>>(
      `${getURL("PROMPT_LIBRARY")}/prompts/${promptId}/versions/${version}`,
      versionData
    );
    return response.data.data;
  };

  const mutation: UseMutationResult<PromptVersion, any, UpdateVersionPayload> = mutate(
    ["useUpdateVersion"],
    updateVersionFn,
    {
      ...options,
      onSettled: (_data, _error, variables) => {
        queryClient.invalidateQueries({ queryKey: ["useGetPromptVersions", variables.promptId] });
        queryClient.invalidateQueries({ queryKey: ["useGetPrompts"] });
      },
    }
  );

  return mutation;
};
