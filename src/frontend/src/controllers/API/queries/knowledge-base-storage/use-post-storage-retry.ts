import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const usePostStorageRetry: useMutationFunctionType<
  undefined,
  { migrationId: string }
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["usePostStorageRetry"],
    async ({
      migrationId,
    }: {
      migrationId: string;
    }): Promise<{ status: string }> => {
      const response = await api.post<{ status: string }>(
        `${getURL("KNOWLEDGE_BASE_STORAGE")}/migrations/${migrationId}/retry`,
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
