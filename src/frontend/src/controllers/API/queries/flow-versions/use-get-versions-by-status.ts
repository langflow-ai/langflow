import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { FlowVersionPaginatedResponse } from "./use-get-pending-reviews";

export type FlowStatusName = "Draft" | "Submitted" | "Approved" | "Rejected" | "Published" | "Unpublished" | "Deleted";

export const useGetVersionsByStatus = (
  statusName: FlowStatusName,
  page: number = 1,
  limit: number = 12,
  enabled = true
) => {
  return useQuery<FlowVersionPaginatedResponse>({
    queryKey: ["flow-versions-by-status", statusName, page, limit],
    queryFn: async () => {
      const response = await api.get<FlowVersionPaginatedResponse>(
        `${getURL("FLOW_VERSIONS")}/by-status/${statusName}`,
        {
          params: { page, limit },
        }
      );
      return response.data;
    },
    enabled,
    staleTime: 0, // Always fetch fresh data
    refetchOnMount: "always", // Refetch when component mounts
    refetchOnWindowFocus: true,
  });
};
