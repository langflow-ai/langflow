import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";

export const useDeletePublishedFlow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (publishedFlowId: string) => {
      const response = await api.delete(
        `/api/v1/published-flows/${publishedFlowId}`
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
