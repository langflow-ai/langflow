import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";

export interface PublishFlowPayload {
  version?: string;
  category?: string;
}

export const usePublishFlow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { flowId: string; payload: PublishFlowPayload }) => {
      const response = await api.post(
        `/api/v1/published-flows/publish/${data.flowId}`,
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
