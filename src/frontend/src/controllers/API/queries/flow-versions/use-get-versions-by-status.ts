import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type { FlowVersionRead } from "./use-get-pending-reviews";

export type FlowStatusName = "Draft" | "Submitted" | "Approved" | "Rejected" | "Published" | "Unpublished" | "Deleted";

export const useGetVersionsByStatus = (statusName: FlowStatusName, enabled = true) => {
  return useQuery<FlowVersionRead[]>({
    queryKey: ["flow-versions-by-status", statusName],
    queryFn: async () => {
      const response = await api.get<FlowVersionRead[]>(
        `${getURL("FLOW_VERSIONS")}/by-status/${statusName}`
      );
      return response.data;
    },
    enabled,
    staleTime: 30000,
    refetchOnWindowFocus: true,
  });
};
