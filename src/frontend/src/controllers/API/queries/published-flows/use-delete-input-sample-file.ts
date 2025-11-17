import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

type DeleteInputSampleFilePayload = {
  sample_id: string;
  name: string; // exact stored file path or name
};

export const useDeleteInputSampleFile = (publishedFlowId?: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ sample_id, name }: DeleteInputSampleFilePayload) => {
      const res = await api.delete(
        `${getURL("PUBLISHED_FLOWS")}/input-samples/${sample_id}/file`,
        { params: { name } }
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