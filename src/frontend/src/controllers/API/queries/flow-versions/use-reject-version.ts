import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { FlowVersionRead } from "./use-get-pending-reviews";

export interface RejectVersionPayload {
  rejection_reason?: string;
}

export const useRejectVersion = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { versionId: string; payload?: RejectVersionPayload }) => {
      const response = await api.post<FlowVersionRead>(
        `${getURL("FLOW_VERSIONS")}/reject/${data.versionId}`,
        data.payload || {}
      );
      return response.data;
    },
    onSuccess: () => {
      // Invalidate all relevant queries
      // Use refetchType: "all" to ensure immediate refetch of all matching queries
      queryClient.invalidateQueries({
        queryKey: ["pending-reviews"],
        refetchType: "all"
      });
      queryClient.invalidateQueries({
        queryKey: ["flow-versions-by-status", "Submitted"],
        refetchType: "all"
      });
      queryClient.invalidateQueries({
        queryKey: ["flow-versions-by-status", "Rejected"],
        refetchType: "all"
      });
      queryClient.invalidateQueries({
        queryKey: ["my-submissions"],
        refetchType: "all"
      });
      // Invalidate flow-latest-status to update Submit for Review button state
      queryClient.invalidateQueries({
        queryKey: ["flow-latest-status"],
        refetchType: "all"
      });
      // Invalidate flows to update the locked state (flow is unlocked on rejection)
      queryClient.invalidateQueries({
        queryKey: ["useGetRefreshFlowsQuery"],
        refetchType: "all"
      });
    },
  });
};
