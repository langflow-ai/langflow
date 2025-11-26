import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { FlowVersionRead } from "./use-get-pending-reviews";

export const useCancelSubmission = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (versionId: string) => {
      const response = await api.post<FlowVersionRead>(
        `${getURL("FLOW_VERSIONS")}/cancel/${versionId}`
      );
      return response.data;
    },
    onSuccess: async () => {
      // Invalidate all relevant queries
      // Use refetchType: "all" to ensure immediate refetch of all matching queries
      await queryClient.invalidateQueries({
        queryKey: ["pending-reviews"],
        refetchType: "all"
      });
      await queryClient.invalidateQueries({
        queryKey: ["flow-versions-by-status", "Submitted"],
        refetchType: "all"
      });
      await queryClient.invalidateQueries({
        queryKey: ["flow-versions-by-status", "Draft"],
        refetchType: "all"
      });
      await queryClient.invalidateQueries({
        queryKey: ["my-submissions"],
        refetchType: "all"
      });
      // Invalidate flow-latest-status to update toolbar button state
      await queryClient.invalidateQueries({
        queryKey: ["flow-latest-status"],
        refetchType: "all"
      });
      // Invalidate flows to update the locked state (flow is unlocked on cancellation)
      // Force refetch to ensure the flow locked state is updated immediately
      await queryClient.refetchQueries({
        queryKey: ["useGetRefreshFlowsQuery"],
        type: "all"
      });
    },
  });
};
