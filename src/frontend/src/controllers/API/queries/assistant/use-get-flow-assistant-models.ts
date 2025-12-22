import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type FlowAssistantModelInfo = {
  slug: string;
  name: string;
  context_length?: number;
  vendor?: string;
  model_type?: string;
};

export type FlowAssistantModelsResponse = {
  models: FlowAssistantModelInfo[];
};

export const useGetFlowAssistantModels: useQueryFunctionType<
  { enabled: boolean },
  FlowAssistantModelsResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async () => {
    const { data } = await api.get<FlowAssistantModelsResponse>(
      getURL("FLOW_ASSISTANT_MODELS"),
    );
    return data;
  };

  return query(["useGetFlowAssistantModels"], responseFn, {
    enabled: !!params.enabled,
    ...options,
  });
};
