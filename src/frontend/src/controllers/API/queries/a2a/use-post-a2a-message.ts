import {
  type A2AEnvelope,
  buildSendMessageBody,
} from "@/modals/a2aModal/utils";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostA2AMessage {
  flowId: string;
  message: string;
}

// Sends one A2A message/send to the flow's public JSON-RPC endpoint and returns the
// raw JSON-RPC envelope (result or error). Used by the A2A modal's test panel to
// exercise the published agent end to end.
export const usePostA2AMessage: useMutationFunctionType<
  undefined,
  IPostA2AMessage
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const postA2AMessageFn = async ({
    flowId,
    message,
  }: IPostA2AMessage): Promise<A2AEnvelope> => {
    const body = buildSendMessageBody(message, crypto.randomUUID());
    const response = await api.post(`${getURL("A2A")}/${flowId}/jsonrpc`, body);
    return response.data;
  };

  return mutate(["usePostA2AMessage"], postA2AMessageFn, options);
};
