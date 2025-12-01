import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { ApiResponse, CreateVersionRequest, PromptVersion } from "./types";

interface CreateVersionPayload extends CreateVersionRequest {
  promptId: string;
}

export const useCreateVersion: useMutationFunctionType<
  undefined,
  CreateVersionPayload
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createVersionFn = async (payload: CreateVersionPayload): Promise<PromptVersion> => {
    const { promptId, ...versionData } = payload;
    const response = await api.post<ApiResponse<PromptVersion>>(
      `${getURL("PROMPT_LIBRARY")}/prompts/${promptId}/versions`,
      versionData
    );
    return response.data.data;
  };

  const mutation: UseMutationResult<PromptVersion, any, CreateVersionPayload> = mutate(
    ["useCreateVersion"],
    createVersionFn,
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
