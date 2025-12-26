import { useQuery } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { FlowVersionType } from "@/types/flow";
import { getURL } from "@/controllers/API/helpers/constants";

export const useGetFlowVersionsQuery = ({ flowId }: { flowId?: string }) => {
  return useQuery({
    queryKey: ["useGetFlowVersionsQuery", flowId],
    queryFn: async (): Promise<FlowVersionType[]> => {
      if (!flowId) {
        return [];
      }
      const url = `${getURL("FLOWS")}/${flowId}/versions`;
      const response = await api.get<FlowVersionType[] | null>(url);
      return Array.isArray(response.data) ? response.data : [];
    },
    enabled: !!flowId,
    staleTime: 0,
    refetchOnMount: true,
  });
};
