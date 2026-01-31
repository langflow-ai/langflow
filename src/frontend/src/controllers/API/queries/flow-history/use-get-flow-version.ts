import { useMutation } from "@tanstack/react-query";
import { getURL } from "../../helpers/constants";
import { api } from "../../api";

interface FlowVersionResponse {
  id: string;
  flow_id: string;
  user_id: string;
  created_at: string;
  flow_data: {
    nodes: any[];
    edges: any[];
    viewport?: { x: number; y: number; zoom: number };
  };
}

export const useGetFlowVersion = () => {
  return useMutation({
    mutationFn: async ({
      flowId,
      versionId,
    }: {
      flowId: string;
      versionId: string;
    }) => {
      const response = await api.get<FlowVersionResponse>(
        `${getURL("FLOWS")}/${flowId}/history/${versionId}`,
      );
      return response.data;
    },
  });
};
