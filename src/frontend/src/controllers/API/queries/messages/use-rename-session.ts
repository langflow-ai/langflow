import type { useMutationFunctionType } from "@/types/api";
import type { Message } from "@/types/messages";
import type { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface UpdateSessionParams {
  oldSessionId: string;
  newSessionId: string;
}

interface useUpdateSessionNameParams {
  flowId?: string;
  useLocalStorage?: boolean;
}

export const useUpdateSessionName: useMutationFunctionType<
  useUpdateSessionNameParams,
  UpdateSessionParams
> = ({ flowId, useLocalStorage }, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateSessionApi = async (data: UpdateSessionParams) => {
    if (!flowId) {
      throw new Error("Flow ID is required");
    }

    if (useLocalStorage) {
      const messages = JSON.parse(sessionStorage.getItem(flowId) || "");
      const messagesWithNewSessionId = messages.map((message: Message) => {
        if (message.session_id === data.oldSessionId) {
          message.session_id = data.newSessionId;
        }
        return message;
      });
      sessionStorage.setItem(flowId, JSON.stringify(messagesWithNewSessionId));
      return {
        data: messagesWithNewSessionId,
      };
    } else {
      const result = await api.patch(
        `${getURL("MESSAGES")}/session/${data.oldSessionId}`,
        null,
        {
          params: { new_session_id: data.newSessionId },
        }
      );
      return result.data;
    }
  };

  const mutation: UseMutationResult<Message[], any, UpdateSessionParams> =
    mutate(["useUpdateSessionName"], updateSessionApi, {
      ...options,
      onSettled: () => {
        queryClient.invalidateQueries({
          queryKey: ["useGetSessionsFromFlowQuery", { flowId }],
        });
      },
    });

  return mutation;
};
