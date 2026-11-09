import type { useMutationFunctionType } from "@/types/api";
import type { ApiKeyPermissionPolicy } from "@/types/api-key-permissions";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { IApiKeysDataArray } from "./use-get-api-keys";

export const usePatchApiKeyPermissions: useMutationFunctionType<
  undefined,
  { id: string; permissions: ApiKeyPermissionPolicy | null }
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["usePatchApiKeyPermissions"],
    async ({ id, permissions }): Promise<IApiKeysDataArray> => {
      const { data } = await api.patch<IApiKeysDataArray>(
        `${getURL("API_KEY")}/${encodeURIComponent(id)}/permissions`,
        { permissions },
      );
      return data;
    },
    {
      retry: false,
      ...options,
      onSettled: (...args) => {
        void queryClient.invalidateQueries({
          queryKey: ["useGetApiKeysQuery"],
        });
        options?.onSettled?.(...args);
      },
    },
  );
};
