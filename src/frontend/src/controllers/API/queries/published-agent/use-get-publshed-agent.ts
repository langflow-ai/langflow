import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
// import { api } from "@/controllers/API";

// Type definitions
export interface PublishedAgentHeader {
  id: string;
  flow_id: string;
  category_id: string | null;
  is_published: boolean;
  created_at: string;
  deleted_at: string | null;
  user_id: string;
  display_name: string | null;
  description: string | null;
}

export interface PublishedAgentsResponse {
  items: PublishedAgentHeader[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface GetPublishedAgentsParams {
  page?: number;
  size?: number;
  flow_id?: string;
  category_id?: string;
  is_published?: boolean;
  include_deleted?: boolean;
}

// API function
const getPublishedAgents = async (
  params: GetPublishedAgentsParams = {}
): Promise<PublishedAgentsResponse> => {
  const searchParams = new URLSearchParams();
  
  if (params.page !== undefined) searchParams.append("page", params.page.toString());
  if (params.size !== undefined) searchParams.append("size", params.size.toString());
  if (params.flow_id) searchParams.append("flow_id", params.flow_id);
  if (params.category_id) searchParams.append("category_id", params.category_id);
  if (params.is_published !== undefined) searchParams.append("is_published", params.is_published.toString());
  if (params.include_deleted !== undefined) searchParams.append("include_deleted", params.include_deleted.toString());

  const response = await api.get(`/api/v1/published-agents/`);
  return response.data;
};

// React Query hook
export const useGetPublishedAgentsQuery = (
  params: GetPublishedAgentsParams = {},
  options?: {
    enabled?: boolean;
    refetchOnWindowFocus?: boolean;
    staleTime?: number;
  }
) => {
  return useQuery({
    queryKey: ["published-agents", params],
    queryFn: () => getPublishedAgents(params),
    enabled: options?.enabled ?? true,
    refetchOnWindowFocus: options?.refetchOnWindowFocus ?? false,
    staleTime: options?.staleTime ?? 5 * 60 * 1000, // 5 minutes
  });
};

export default useGetPublishedAgentsQuery;