import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export const useCheckFlowPublished = (flowId: string | undefined) => {
  return useQuery({
    queryKey: ["published-flow-check", flowId],
    queryFn: async () => {
      const response = await api.get(`/api/v1/published-flows/check/${flowId}`);
      return response.data;
    },
    enabled: !!flowId,
  });
};
