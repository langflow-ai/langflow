import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";

export const useUnpublishFlow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (flowId: string) => {
      const response = await api.post(
        `/api/v1/published-flows/unpublish/${flowId}`
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
