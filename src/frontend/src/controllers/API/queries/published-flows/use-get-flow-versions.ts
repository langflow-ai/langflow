import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export interface PublishedFlowVersion {
  id: number | string;  // number for old published_flow_version, string (UUID) for flow_version
  version: string;
  flow_id_cloned_to: string | null;
  flow_id_cloned_from: string;
  published_flow_id: string | null;
  flow_name: string;
  flow_icon: string | null;
  description: string | null;
  tags: string[] | null;
  active: boolean;
  drafted: boolean;
  published_by: string;
  published_at: string;
  created_at: string;
  status_name?: string | null;  // Status from flow_status table (Published, Approved, etc.)
}

export const useGetFlowVersions = (flowId: string | undefined) => {
  return useQuery({
    queryKey: ["flow-versions", flowId],
    queryFn: async () => {
      if (!flowId) throw new Error("Flow ID is required");

      const response = await api.get<PublishedFlowVersion[]>(
        `${getURL("PUBLISHED_FLOWS")}/${flowId}/versions`
      );
      return response.data;
    },
    enabled: !!flowId,
    staleTime: 1000 * 60 * 2, // Cache for 2 minutes
    retry: false, // Don't retry if flow is not published
  });
};
