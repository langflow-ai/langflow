import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";

export const useClearInstallationStatus = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const response = await api.delete("/api/v1/packages/install/status");
      return response.data;
    },
    onSuccess: () => {
      // Invalidate the installation status query to refetch
      queryClient.invalidateQueries({ queryKey: ["installation-status"] });
    },
  });
};
