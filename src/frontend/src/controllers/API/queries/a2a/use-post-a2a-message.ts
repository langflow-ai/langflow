import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { type A2AEnvelope, buildSendMessageBody } from "./utils";

interface IPostA2AMessage {
  flowId: string;
  message: string;
  // Echo the server's contextId to continue a conversation; send a paused task's
  // id to resume it (HITL). apiKey is required only for apikey-folder agents.
  contextId?: string;
  taskId?: string;
  apiKey?: string;
}

// Sends one A2A message/send to the flow's public JSON-RPC endpoint and returns the
// raw JSON-RPC envelope (result or error). Drives the Agent tab's test conversation:
// contextId/taskId thread multi-turn and input-required resume; apiKey satisfies the
// x-api-key gate on apikey-folder agents.
export const usePostA2AMessage: useMutationFunctionType<
  undefined,
  IPostA2AMessage
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const postA2AMessageFn = async ({
    flowId,
    message,
    contextId,
    taskId,
    apiKey,
  }: IPostA2AMessage): Promise<A2AEnvelope> => {
    const body = buildSendMessageBody(message, crypto.randomUUID(), {
      contextId,
      taskId,
    });
    const response = await api.post(
      `${getURL("A2A")}/${flowId}/jsonrpc`,
      body,
      apiKey ? { headers: { "x-api-key": apiKey } } : undefined,
    );
    return response.data;
  };

  // message/send runs the flow and is not idempotent (no server-side messageId
  // dedupe), so a retry on a 5xx/network error re-executes the whole flow and can
  // spawn duplicate HITL tasks. Default retry off; a caller can still opt back in.
  return mutate(["usePostA2AMessage"], postA2AMessageFn, {
    retry: false,
    ...options,
  });
};
