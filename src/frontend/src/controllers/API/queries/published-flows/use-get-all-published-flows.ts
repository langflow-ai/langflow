import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export interface GetAllPublishedFlowsParams {
  page?: number;
  limit?: number;
  search?: string;
  category?: string;
  tags?: string;
  status?: "published" | "unpublished" | "all";
  sort_by?: string;
  order?: string;
}

export const useGetAllPublishedFlows = (params: GetAllPublishedFlowsParams) => {
  return useQuery({
    queryKey: ["all-published-flows", params],
    queryFn: async () => {
      const response = await api.get(`${getURL("PUBLISHED_FLOWS")}/all`, { params });
      return response.data;
    },
  });
};
