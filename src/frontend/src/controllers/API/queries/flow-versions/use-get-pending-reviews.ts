import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export interface FlowVersionRead {
  id: string;
  original_flow_id: string;
  version_flow_id: string;
  status_id: number;
  status_name: string;
  version: string;
  title: string;
  description?: string;
  tags?: string[];
  agent_logo?: string;
  // Submission fields
  submitted_by: string;
  submitted_by_name?: string;
  submitted_by_email?: string;
  submitted_at: string;
  // Review fields
  reviewed_by?: string;
  reviewed_by_name?: string;
  reviewed_by_email?: string;
  reviewed_at?: string;
  rejection_reason?: string;
  // Publish fields
  published_by?: string;
  published_by_name?: string;
  published_by_email?: string;
  published_at?: string;
  // Aliases for backward compatibility
  submitter_name?: string;
  submitter_email?: string;
  reviewer_name?: string;
  // Standard fields
  created_at: string;
  updated_at: string;
}

export const useGetPendingReviews = () => {
  return useQuery<FlowVersionRead[]>({
    queryKey: ["pending-reviews"],
    queryFn: async () => {
      const response = await api.get<FlowVersionRead[]>(
        `${getURL("FLOW_VERSIONS")}/pending-reviews`
      );
      return response.data;
    },
    staleTime: 0, // Always fetch fresh data
    refetchOnMount: "always", // Refetch when component mounts
    refetchOnWindowFocus: true,
  });
};
