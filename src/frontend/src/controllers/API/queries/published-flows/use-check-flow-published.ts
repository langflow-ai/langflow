import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export const useCheckFlowPublished = (flowId: string | undefined) => {
  return useQuery({
    queryKey: ["published-flow-check", flowId],
    queryFn: async () => {
      const response = await api.get(`${getURL("PUBLISHED_FLOWS")}/check/${flowId}`);
      return response.data;
    },
    enabled: !!flowId,
  });
};
