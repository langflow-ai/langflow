import { useQuery } from "@tanstack/react-query";
import type { FlowType } from "@/types/flow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export const useGetPublishedFlowForViewing = (publishedFlowId: string | undefined) => {
  return useQuery({
    queryKey: ["published-flow-for-viewing", publishedFlowId],
    queryFn: async (): Promise<FlowType> => {
      console.log("[useGetPublishedFlowForViewing] FETCHING from API for publishedFlowId:", publishedFlowId);

      const response = await api.get(
        `${getURL("PUBLISHED_FLOWS")}/${publishedFlowId}`
      );
      const publishedFlow = response.data;

      console.log("[useGetPublishedFlowForViewing] API Response - flow_data has", publishedFlow.flow_data?.nodes?.length, "nodes");

      // Transform published flow data into FlowType format
      // The flow_data field contains the snapshot with nodes, edges, viewport
      const transformed = {
        id: publishedFlow.flow_id,
        name: publishedFlow.flow_name,
        description: publishedFlow.description || "",
        data: publishedFlow.flow_data, // This is the published snapshot!
        is_component: false,
        updated_at: publishedFlow.updated_at,
        folder_id: null,
        endpoint_name: null,
      } as FlowType;

      console.log("[useGetPublishedFlowForViewing] Transformed data has", transformed.data?.nodes?.length, "nodes");

      return transformed;
    },
    enabled: !!publishedFlowId,
    staleTime: 0, // CHANGED: Don't cache - always fetch fresh data
  });
};
