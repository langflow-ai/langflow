import type { UseMutationResult } from "@tanstack/react-query";
import { useGetFlowId } from "@/modals/IOModal/hooks/useGetFlowId";
import useFlowStore from "@/stores/flowStore";
import { useMessagesStore } from "@/stores/messagesStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
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
    const isPlaygroundFromFlow = useFlowStore.getState().playgroundPage;
    const isPlaygroundFromPlayground =
      usePlaygroundStore.getState().isPlayground;
    const isPlayground = isPlaygroundFromFlow || isPlaygroundFromPlayground;
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
      useMessagesStore
        .getState()
        .renameSession(data.old_session_id, data.new_session_id);

      // CRITICAL: Move messages from old cache key to new cache key
      const oldCacheKey = [
        "useGetMessagesQuery",
        { id: flowId, session_id: data.old_session_id },
      ];
      const newCacheKey = [
        "useGetMessagesQuery",
        { id: flowId, session_id: data.new_session_id },
      ];

      const oldCacheData = queryClient.getQueryData<Message[]>(oldCacheKey);
      // Get fresh messages from sessionStorage (source of truth after rename)
      const freshMessages = JSON.parse(sessionStorage.getItem(flowId) || "[]");
      const messagesForNewSession = freshMessages.filter(
        (msg: Message) => msg.session_id === data.new_session_id,
      );

      // Set the new cache with fresh messages from sessionStorage
      queryClient.setQueryData(newCacheKey, messagesForNewSession);

      // Remove the old cache key
      if (oldCacheData && oldCacheData.length > 0) {
        queryClient.removeQueries({ queryKey: oldCacheKey });
      }

      queryClient.invalidateQueries({
        queryKey: ["useGetSessionsFromFlowQuery"],
      });

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

      // Update React Query cache with the renamed messages
      if (result.data && flowId) {
        const newCacheKey = [
          "useGetMessagesQuery",
          { id: flowId, session_id: data.new_session_id },
        ];

        queryClient.setQueryData(newCacheKey, result.data);

        // Remove old cache key
        const oldCacheKey = [
          "useGetMessagesQuery",
          { id: flowId, session_id: data.old_session_id },
        ];
        queryClient.removeQueries({ queryKey: oldCacheKey });
      }

      return result.data;
    }
  };

  const mutation: UseMutationResult<Message[], any, UpdateSessionParams> =
    mutate(["useUpdateSessionName"], updateSessionApi, {
      onMutate: (variables) => {},
      onSuccess: (data, variables, context, ...rest) => {
        // Call the original onSuccess if provided
        options?.onSuccess?.(data, variables, context, ...rest);
      },
      onError: (error, variables, context, ...rest) => {
        options?.onError?.(error, variables, context, ...rest);
      },
      onSettled: (data, error, variables, context, ...rest) => {
        queryClient.invalidateQueries({
          queryKey: ["useGetSessionsFromFlowQuery"],
        });
        // Call the original onSettled if provided
        options?.onSettled?.(data, error, variables, context, ...rest);
      },
    });

  return mutation;
};
