import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export const useGetPublishedFlow = (publishedFlowId: string | undefined) => {
  return useQuery({
    queryKey: ["published-flow", publishedFlowId],
    queryFn: async () => {
      const response = await api.get(`/api/v1/published-flows/${publishedFlowId}`);
      return response.data;
    },
    enabled: !!publishedFlowId,
  });
};
