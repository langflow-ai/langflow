import type { UseMutationResult } from "@tanstack/react-query";
import type {
  ResponseErrorDetailAPI,
  useMutationFunctionType,
} from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export type FlowAssistantMessageRole = "system" | "user" | "assistant" | "tool";

export type FlowAssistantHistoryItem = {
  role: FlowAssistantMessageRole;
  content: string;
};

export type FlowAssistantChatRequest = {
  flow_id: string;
  message: string;
  history?: FlowAssistantHistoryItem[];
  model?: string | null;
};

export type ToolCallDetail = {
  name: string;
  arguments: Record<string, unknown>;
  result?: string | null;
  error?: string | null;
};

export type FlowAssistantChatResponse = {
  message: string;
  tool_calls: ToolCallDetail[];
};

export const usePostFlowAssistantChat: useMutationFunctionType<
  undefined,
  FlowAssistantChatRequest,
  FlowAssistantChatResponse,
  ResponseErrorDetailAPI
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const fn = async (
    payload: FlowAssistantChatRequest,
  ): Promise<FlowAssistantChatResponse> => {
    const response = await api.post<FlowAssistantChatResponse>(
      getURL("FLOW_ASSISTANT"),
      {
        flow_id: payload.flow_id,
        message: payload.message,
        history: payload.history ?? [],
        model: payload.model ?? null,
      },
    );
    return response.data;
  };

  const mutation: UseMutationResult<
    FlowAssistantChatResponse,
    ResponseErrorDetailAPI,
    FlowAssistantChatRequest
  > = mutate(["usePostFlowAssistantChat"], fn, options);

  return mutation;
};
