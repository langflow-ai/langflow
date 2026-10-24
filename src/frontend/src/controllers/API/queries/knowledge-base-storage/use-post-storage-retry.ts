import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const usePostStorageRetry: useMutationFunctionType<
  undefined,
  { migrationId: string } | { inventory: true }
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["usePostStorageRetry"],
    async (
      request: { migrationId: string } | { inventory: true },
    ): Promise<{ status: string }> => {
      const path =
        "migrationId" in request
          ? `migrations/${request.migrationId}/retry`
          : "inventory/retry";
      const response = await api.post<{ status: string }>(
        `${getURL("KNOWLEDGE_BASE_STORAGE")}/${path}`,
      );
      return response.data;
    },
    {
      retry: false,
      onSettled: () => {
        queryClient.invalidateQueries({ queryKey: ["useGetStorageStatus"] });
      },
      ...options,
    },
  );
};
