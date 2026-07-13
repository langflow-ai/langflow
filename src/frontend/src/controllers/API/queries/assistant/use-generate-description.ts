import type { useMutationFunctionType } from "@/types/api";
import i18n from "@/i18n";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type GenerateDescriptionPayload = {
  componentId?: string;
  flowId: string;
  currentDescription?: string;
};

const extractGeneratedText = (response: any): string => {
  const output = response?.outputs?.[0]?.outputs?.[0];
  const text =
    output?.results?.message?.text ??
    output?.results?.text?.data?.text ??
    output?.artifacts?.message ??
    response?.message?.text ??
    response?.result ??
    response?.text;
  if (typeof text !== "string" || !text.trim()) {
    throw new Error("The language model did not return a description.");
  }
  return text.trim();
};

export const useGenerateDescription: useMutationFunctionType<
  undefined,
  GenerateDescriptionPayload
> = (options?) => {
  const { mutate } = UseRequestProcessor();
  return mutate(
    ["useGenerateDescription"],
    async ({ componentId, flowId, currentDescription }) => {
      const response = await api.post(
        getURL("AGENTIC_GENERATE_DESCRIPTION"),
        {
          flow_id: flowId,
          component_id: componentId,
          current_description: currentDescription,
          language: i18n.resolvedLanguage ?? i18n.language ?? "en",
        },
      );
      return extractGeneratedText(response.data);
    },
    { retry: false, ...options },
  );
};
