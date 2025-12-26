import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { FlowType } from "@/types/flow";
import useFlowStore from "@/stores/flowStore";
import { getURL } from "@/controllers/API/helpers/constants";

export const usePostRestoreFlowVersion = () => {
  const queryClient = useQueryClient();
  const resetFlow = useFlowStore((state) => state.resetFlow);

  const restoreFlowVersion = async ({
    flowId,
    versionId,
  }: {
    flowId: string;
    versionId: string;
  }) => {
    const url = `${getURL("FLOWS")}/${flowId}/versions/${versionId}`;
    const response = await api.post<FlowType>(url);
    return response.data;
  };

  return useMutation({
    mutationFn: restoreFlowVersion,
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["useGetFlowVersionsQuery", variables.flowId],
      });
      // Invalidate the current flow query as well
      queryClient.invalidateQueries({
        queryKey: ["useGetFlow", variables.flowId],
      });
      
      // Update the flow in the store
      if (data) {
        resetFlow(data);
      }
    },
  });
};
