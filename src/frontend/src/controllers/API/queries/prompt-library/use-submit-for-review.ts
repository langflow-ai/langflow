import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { ApiResponse, PromptVersion } from "./types";

interface SubmitForReviewPayload {
  promptId: string;
  version: number;
  comment?: string;
}

export const useSubmitForReview: useMutationFunctionType<
  undefined,
  SubmitForReviewPayload
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const submitForReviewFn = async (payload: SubmitForReviewPayload): Promise<PromptVersion> => {
    const { promptId, version, comment } = payload;
    const response = await api.post<ApiResponse<PromptVersion>>(
      `${getURL("PROMPT_LIBRARY")}/prompts/${promptId}/versions/${version}/submit`,
      {
        comment: comment || "",
      }
    );
    return response.data.data;
  };

  const mutation: UseMutationResult<PromptVersion, any, SubmitForReviewPayload> = mutate(
    ["useSubmitForReview"],
    submitForReviewFn,
    {
      ...options,
      onSettled: (_data, _error, variables: any) => {
        queryClient.invalidateQueries({ queryKey: ["useGetPromptVersions", variables.promptId] });
        queryClient.invalidateQueries({ queryKey: ["useGetPrompts"] });
      },
    }
  );

  return mutation;
};
