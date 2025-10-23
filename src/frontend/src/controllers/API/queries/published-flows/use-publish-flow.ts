import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export interface PublishFlowPayload {
  marketplace_flow_name: string;
  target_folder_id?: string;
  version?: string;
  category?: string;
}

export const usePublishFlow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { flowId: string; payload: PublishFlowPayload }) => {
      const response = await api.post(
        `${getURL("PUBLISHED_FLOWS")}/publish/${data.flowId}`,
        data.payload
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["published-flows"] });
      queryClient.invalidateQueries({ queryKey: ["all-published-flows"] });
      queryClient.invalidateQueries({ queryKey: ["published-flow-check"] });
    },
  });
};
