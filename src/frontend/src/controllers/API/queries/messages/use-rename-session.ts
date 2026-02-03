import type { UseMutationResult } from "@tanstack/react-query";
import { useGetFlowId } from "@/modals/IOModal/hooks/useGetFlowId";
import useFlowStore from "@/stores/flowStore";
import { useMessagesStore } from "@/stores/messagesStore";
import type { useMutationFunctionType } from "@/types/api";
import type { Message } from "@/types/messages";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface UpdateSessionParams {
  old_session_id: string;
  new_session_id: string;
}

export const useUpdateSessionName: useMutationFunctionType<
  undefined,
  UpdateSessionParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const flowId = useGetFlowId();

  const updateSessionApi = async (data: UpdateSessionParams) => {
    const isPlayground = useFlowStore.getState().playgroundPage;
    // if we are in playground we will edit the local storage instead of the API
    if (isPlayground && flowId) {
      const messages = JSON.parse(sessionStorage.getItem(flowId) || "[]");
      const messagesWithNewSessionId = messages.map((message: Message) => {
        if (message.session_id === data.old_session_id) {
          message.session_id = data.new_session_id;
        }
        return message;
      });
      sessionStorage.setItem(flowId, JSON.stringify(messagesWithNewSessionId));
      
      // Update the messages store to reflect the new session_id
      useMessagesStore.getState().renameSession(data.old_session_id, data.new_session_id);
      
      // Update React Query cache - move messages from old session key to new session key
      const oldCacheKey = [
        "useGetMessagesQuery",
        { id: flowId, session_id: data.old_session_id },
      ];
      const newCacheKey = [
        "useGetMessagesQuery",
        { id: flowId, session_id: data.new_session_id },
      ];
      
      const oldMessages = queryClient.getQueryData<Message[]>(oldCacheKey);
      if (oldMessages) {
        // Update session_id in cached messages and move to new cache key
        const updatedMessages = oldMessages.map((msg) => ({
          ...msg,
          session_id: data.new_session_id,
        }));
        queryClient.setQueryData(newCacheKey, updatedMessages);
        // Remove old cache entry
        queryClient.removeQueries({ queryKey: oldCacheKey });
      }
      
      return {
        data: messagesWithNewSessionId,
      };
    } else {
      const result = await api.patch(
        `${getURL("MESSAGES")}/session/${data.old_session_id}`,
        null,
        {
          params: { new_session_id: data.new_session_id },
        },
      );
      return result.data;
    }
  };

  const mutation: UseMutationResult<Message[], any, UpdateSessionParams> =
    mutate(["useUpdateSessionName"], updateSessionApi, {
      ...options,
      onSettled: () => {
        queryClient.invalidateQueries({
          queryKey: ["useGetSessionsFromFlowQuery"],
        });
      },
    });

  return mutation;
};
