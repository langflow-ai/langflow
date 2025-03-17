import useFlowStore from "@/stores/flowStore";
import { useMutationFunctionType } from "@/types/api";
import { Message } from "@/types/messages";
import { UseMutationResult } from "@tanstack/react-query";
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

  const updateSessionApi = async (data: UpdateSessionParams) => {
    const isPlayground = useFlowStore.getState().playgroundPage;
    const flowId = useFlowStore.getState().currentFlow?.id;
    // if we are in playground we will edit the local storage instead of the API
    if (isPlayground && flowId) {
      const messages = JSON.parse(sessionStorage.getItem(flowId) || "");
      const messagesWithNewSessionId = messages.map((message: Message) => {
        if (message.session_id === data.old_session_id) {
          message.session_id = data.new_session_id;
        }
        return message;
      });
      sessionStorage.setItem(flowId, JSON.stringify(messagesWithNewSessionId));
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
      onSettled: (data, variables, context) => {
        // Invalidate and refetch relevant queries
        queryClient.refetchQueries({
          queryKey: ["useGetMessagesQuery"],
        });
      },
    });

  return mutation;
};
