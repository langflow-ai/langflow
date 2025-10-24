import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export const useGetPublishedFlow = (publishedFlowId: string | undefined) => {
  return useQuery({
    queryKey: ["published-flow", publishedFlowId],
    queryFn: async () => {
      const response = await api.get(`${getURL("PUBLISHED_FLOWS")}/${publishedFlowId}`);
      return response.data;
    },
    enabled: !!publishedFlowId,
  });
};
