import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

type PatchInputSamplePayload = {
  sample_id: string;
  data: {
    sample_text?: string[] | null;
    sample_output?: Record<string, any> | null;
  };
};

export const usePatchInputSample = (publishedFlowId?: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ sample_id, data }: PatchInputSamplePayload) => {
      const res = await api.patch(`${getURL("PUBLISHED_FLOWS")}/input-samples/${sample_id}`, data);
      return res.data;
    },
    onSuccess: () => {
      if (publishedFlowId) {
        queryClient.invalidateQueries({ queryKey: ["published-flow", publishedFlowId] });
      }
    },
  });
};