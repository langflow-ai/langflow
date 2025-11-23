import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export interface SubmitFlowPayload {
  title: string;
  version: string;
  description?: string;
  tags?: string[];
  agent_logo?: string;
  // Sample input fields
  storage_account?: string;
  container_name?: string;
  file_names?: string[];
  sample_text?: string[];
  sample_output?: Record<string, any>;
}

export interface FlowVersionResponse {
  id: string;
  original_flow_id: string;
  version_flow_id: string;
  status_id: number;
  version: string;
  title: string;
  description?: string;
  tags?: string[];
  agent_logo?: string;
  submitted_by: string;
  submitted_at: string;
  status?: {
    id: number;
    name: string;
    description?: string;
  };
}

export const useSubmitFlowForApproval = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { flowId: string; payload: SubmitFlowPayload }) => {
      const response = await api.post<FlowVersionResponse>(
        `${getURL("FLOW_VERSIONS")}/submit/${data.flowId}`,
        data.payload
      );
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate relevant queries to refresh UI
      queryClient.invalidateQueries({ queryKey: ["flow-latest-status", variables.flowId] });
      queryClient.invalidateQueries({ queryKey: ["flow-versions", variables.flowId] });
      queryClient.invalidateQueries({ queryKey: ["my-submissions"] });
      queryClient.invalidateQueries({ queryKey: ["pending-reviews"] });
      // Invalidate flows query to update title/description in flow header
      queryClient.invalidateQueries({ queryKey: ["flows"] });
    },
  });
};
