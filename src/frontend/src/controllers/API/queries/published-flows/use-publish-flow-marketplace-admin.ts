import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { PublishFlowPayload } from "./use-publish-flow";

/**
 * Hook for Marketplace Admin to publish flows directly to marketplace.
 * Uses the new /publish-flow/{flow_id} endpoint with intelligent status handling.
 */
export const usePublishFlowMarketplaceAdmin = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { flowId: string; payload: PublishFlowPayload }) => {
      const response = await api.post(
        `${getURL("PUBLISHED_FLOWS")}/publish-flow/${data.flowId}`,
        data.payload
      );
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["published-flows"] });
      queryClient.invalidateQueries({ queryKey: ["all-published-flows"] });
      queryClient.invalidateQueries({ queryKey: ["published-flow-check"] });
      queryClient.invalidateQueries({ queryKey: ["flow-versions", variables.flowId] });
      queryClient.invalidateQueries({ queryKey: ["published-flow"] });
      // Invalidate flow-latest-status to update status badge on flow page
      queryClient.invalidateQueries({ queryKey: ["flow-latest-status"] });
    },
  });
};
