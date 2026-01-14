import { useMutation } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { GenerateComponentPromptResponse } from "@/components/core/generateComponent/types";

type GenerateComponentPromptRequest = {
  flowId: string;
  inputValue: string;
  componentId?: string;
  fieldName?: string;
  maxRetries?: number;
};

async function postGenerateComponentPrompt({
  flowId,
  inputValue,
  componentId,
  fieldName,
  maxRetries,
}: GenerateComponentPromptRequest): Promise<GenerateComponentPromptResponse> {
  const response = await api.post<GenerateComponentPromptResponse>(
    getURL("GENERATE_COMPONENT_PROMPT"),
    {
      flow_id: flowId,
      input_value: inputValue,
      component_id: componentId,
      field_name: fieldName,
      max_retries: maxRetries,
    },
  );
  return response.data;
}

export function usePostGenerateComponentPrompt() {
  return useMutation({
    mutationFn: postGenerateComponentPrompt,
    mutationKey: ["usePostGenerateComponentPrompt"],
  });
}
