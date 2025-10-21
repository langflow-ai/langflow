import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export interface GetAllPublishedFlowsParams {
  page?: number;
  limit?: number;
  search?: string;
  category?: string;
  tags?: string;
  sort_by?: string;
  order?: string;
}

export const useGetAllPublishedFlows = (params: GetAllPublishedFlowsParams) => {
  return useQuery({
    queryKey: ["all-published-flows", params],
    queryFn: async () => {
      const response = await api.get("/api/v1/published-flows/all", { params });
      return response.data;
    },
  });
};
