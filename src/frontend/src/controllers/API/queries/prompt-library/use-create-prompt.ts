import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { ApiResponse, CreatePromptRequest, PromptTemplate } from "./types";

export const useCreatePrompt: useMutationFunctionType<
  undefined,
  CreatePromptRequest
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createPromptFn = async (payload: CreatePromptRequest): Promise<PromptTemplate> => {
    const response = await api.post<ApiResponse<PromptTemplate>>(
      `${getURL("PROMPT_LIBRARY")}/prompts/`,
      payload
    );
    return response.data.data;
  };

  const mutation: UseMutationResult<PromptTemplate, any, CreatePromptRequest> = mutate(
    ["useCreatePrompt"],
    createPromptFn,
    {
      ...options,
      onSettled: () => {
        queryClient.invalidateQueries({ queryKey: ["useGetPrompts"] });
      },
    }
  );

  return mutation;
};
