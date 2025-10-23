import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export interface PublishCheckResponse {
  is_published: boolean;
  published_flow_id?: string | null;
  cloned_flow_id?: string | null;
  published_at?: string | null;
  // Additional data for pre-filling re-publish modal
  marketplace_flow_name?: string | null;
  version?: string | null;
  category?: string | null;
}

export const useCheckFlowPublished = (flowId: string | undefined) => {
  return useQuery<PublishCheckResponse>({
    queryKey: ["published-flow-check", flowId],
    queryFn: async () => {
      const response = await api.get(`${getURL("PUBLISHED_FLOWS")}/check/${flowId}`);
      return response.data;
    },
    enabled: !!flowId,
  });
};
