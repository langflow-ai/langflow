import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export const useGetPublishedFlowSpec = (publishedFlowId: string | undefined) => {
  return useQuery({
    queryKey: ["published-flow-spec", publishedFlowId],
    queryFn: async () => {
      const response = await api.get(
        `${getURL("SPEC_BUILDER")}/published-agent-yaml/${publishedFlowId}`
      );
      return response.data;
    },
    enabled: !!publishedFlowId,
  });
};
