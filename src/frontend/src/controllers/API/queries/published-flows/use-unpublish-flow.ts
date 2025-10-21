import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export const useUnpublishFlow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (flowId: string) => {
      const response = await api.post(
        `${getURL("PUBLISHED_FLOWS")}/unpublish/${flowId}`
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
