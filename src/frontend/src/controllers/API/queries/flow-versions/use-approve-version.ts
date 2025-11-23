import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { FlowVersionRead } from "./use-get-pending-reviews";

export const useApproveVersion = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (versionId: string) => {
      const response = await api.post<FlowVersionRead>(
        `${getURL("FLOW_VERSIONS")}/approve/${versionId}`
      );
      return response.data;
    },
    onSuccess: () => {
      // Invalidate all relevant queries
      queryClient.invalidateQueries({ queryKey: ["pending-reviews"] });
      queryClient.invalidateQueries({ queryKey: ["flow-versions-by-status", "Submitted"] });
      queryClient.invalidateQueries({ queryKey: ["flow-versions-by-status", "Approved"] });
      queryClient.invalidateQueries({ queryKey: ["my-submissions"] });
      // Invalidate flow-latest-status to update button states on flow page
      queryClient.invalidateQueries({ queryKey: ["flow-latest-status"] });
    },
  });
};
