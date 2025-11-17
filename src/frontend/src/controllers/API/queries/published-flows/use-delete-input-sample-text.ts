import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

type DeleteInputSampleTextPayload = {
  sample_id: string;
  index?: number;
  value?: string;
};

export const useDeleteInputSampleText = (publishedFlowId?: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ sample_id, index, value }: DeleteInputSampleTextPayload) => {
      const res = await api.delete(
        `${getURL("PUBLISHED_FLOWS")}/input-samples/${sample_id}/text`,
        { params: { index, value } }
      );
      return res.data;
    },
    onSuccess: () => {
      if (publishedFlowId) {
        queryClient.invalidateQueries({ queryKey: ["published-flow", publishedFlowId] });
      }
    },
  });
};