import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { FlowVersionPaginatedResponse } from "./use-get-pending-reviews";

export const useGetAllFlowVersions = (
  page: number = 1,
  limit: number = 12,
  status?: string
) => {
  return useQuery<FlowVersionPaginatedResponse>({
    queryKey: ["all-flow-versions", page, limit, status],
    queryFn: async () => {
      const response = await api.get<FlowVersionPaginatedResponse>(
        `${getURL("FLOW_VERSIONS")}/all`,
        {
          params: {
            page,
            limit,
            ...(status && status !== "all" ? { status } : {}),
          },
        }
      );
      return response.data;
    },
    staleTime: 0, // Always fetch fresh data
    refetchOnMount: "always", // Refetch when component mounts
    refetchOnWindowFocus: true,
  });
};
