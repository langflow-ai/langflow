import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export interface FlowLatestStatusResponse {
  has_submissions: boolean;
  latest_status: string | null;
  latest_version: string | null;
  latest_version_id?: string | null;
  submitted_at?: string | null;
  reviewed_at?: string | null;
  // Data for pre-populating re-submissions
  sample_text?: string[] | null;
  file_names?: string[] | null;
  agent_logo?: string | null;
  tags?: string[] | null;
}

export const useGetFlowLatestStatus = (flowId: string | undefined) => {
  return useQuery<FlowLatestStatusResponse>({
    queryKey: ["flow-latest-status", flowId],
    queryFn: async () => {
      const response = await api.get(
        `${getURL("FLOW_VERSIONS")}/flow/${flowId}/latest-status`
      );
      return response.data;
    },
    enabled: !!flowId,
    staleTime: 0, // Always consider data stale to ensure fresh data
    refetchOnMount: "always", // Refetch when component mounts
    refetchOnWindowFocus: false,
  });
};
