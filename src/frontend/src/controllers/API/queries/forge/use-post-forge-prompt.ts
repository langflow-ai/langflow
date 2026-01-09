import { useMutation } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { ForgePromptResponse } from "@/components/core/componentForge/types";

type ForgePromptRequest = {
  flowId: string;
  inputValue: string;
  componentId?: string;
  fieldName?: string;
};

async function postForgePrompt({
  flowId,
  inputValue,
  componentId,
  fieldName,
}: ForgePromptRequest): Promise<ForgePromptResponse> {
  const response = await api.post<ForgePromptResponse>(
    getURL("FORGE_PROMPT"),
    {
      flow_id: flowId,
      input_value: inputValue,
      component_id: componentId,
      field_name: fieldName,
    },
  );
  return response.data;
}

export function usePostForgePrompt() {
  return useMutation({
    mutationFn: postForgePrompt,
    mutationKey: ["usePostForgePrompt"],
  });
}
