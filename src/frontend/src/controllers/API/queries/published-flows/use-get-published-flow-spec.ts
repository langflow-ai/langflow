import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export const useGetPublishedFlowSpec = (publishedFlowId: string | undefined) => {
  return useQuery({
    queryKey: ["published-flow-spec", publishedFlowId],
    queryFn: async () => {
      const response = await api.get(
        `/api/v1/published-flows/${publishedFlowId}/spec`
      );
      return response.data;
    },
    enabled: !!publishedFlowId,
  });
};
