import { useMutation } from "@tanstack/react-query";
import { getURL } from "../../helpers/constants";
import { api } from "../../api";

export const usePostFlowHistory = () => {
  return useMutation({
    mutationFn: async ({ flowId, data }: { flowId: string; data: any }) => {
      const response = await api.post(
        `${getURL("FLOWS")}/${flowId}/history`,
        data,
      );
      return response.data;
    },
  });
};
