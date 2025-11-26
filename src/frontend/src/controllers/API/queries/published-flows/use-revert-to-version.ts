import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import useAlertStore from "@/stores/alertStore";

export interface RevertToVersionParams {
  flowId: string;
  versionId: number | string;  // number for old published_flow_version, string (UUID) for flow_version
}

export interface RevertToVersionResponse {
  message: string;
  version: string;
  flow_id: string;
  cloned_flow_id: string;
}

export const useRevertToVersion = () => {
  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  return useMutation({
    mutationFn: async ({ flowId, versionId }: RevertToVersionParams) => {
      const response = await api.post<RevertToVersionResponse>(
        `${getURL("PUBLISHED_FLOWS")}/revert/${flowId}/${versionId}`
      );
      return response.data;
    },
    onSuccess: (data, variables) => {
      setSuccessData({
        title: `Moved to version ${data.version} successfully`,
        list: [data.message],
      });

      // Invalidate queries to refresh data
      queryClient.invalidateQueries({ queryKey: ["flow-versions", variables.flowId] });
      queryClient.invalidateQueries({ queryKey: ["flow", variables.flowId] });
      queryClient.invalidateQueries({ queryKey: ["published-flow-check", variables.flowId] });
    },
    onError: (error: any) => {
      setErrorData({
        title: "Revert Failed",
        list: [error.response?.data?.detail || "Failed to revert to version"],
      });
    },
  });
};
