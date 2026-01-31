import { useQuery } from "@tanstack/react-query";
import { getURL } from "../../helpers/constants";
import { api } from "../../api";

interface FlowHistoryItem {
  id: string;
  created_at: string;
}

interface FlowHistoryResponse {
  flow_id: string;
  flow_history: FlowHistoryItem[];
}

export const useGetFlowHistory = ({ flowId }: { flowId: string }) => {
  return useQuery({
    queryKey: ["flowHistory", flowId],
    queryFn: async () => {
      const response = await api.get<FlowHistoryResponse>(
        `${getURL("FLOWS")}/${flowId}/history`,
      );
      return response.data;
    },
    enabled: !!flowId,
  });
};
