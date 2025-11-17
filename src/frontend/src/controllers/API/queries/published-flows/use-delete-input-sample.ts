import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

type DeleteInputSamplePayload = {
  sample_id: string;
};

export const useDeleteInputSample = (publishedFlowId?: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ sample_id }: DeleteInputSamplePayload) => {
      const res = await api.delete(`${getURL("PUBLISHED_FLOWS")}/input-samples/${sample_id}`);
      return res.data;
    },
    onSuccess: () => {
      if (publishedFlowId) {
        queryClient.invalidateQueries({ queryKey: ["published-flow", publishedFlowId] });
      }
    },
  });
};