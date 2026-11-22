import type { useQueryFunctionType } from "@/types/api";
import type { ApiKeyPermissionOptions } from "@/types/api-key-permissions";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetApiKeyPermissionOptions: useQueryFunctionType<
  undefined,
  ApiKeyPermissionOptions
> = (options) => {
  const { query } = UseRequestProcessor();
  return query(
    ["useGetApiKeyPermissionOptions"],
    async (): Promise<ApiKeyPermissionOptions> => {
      try {
        const { data } = await api.get<ApiKeyPermissionOptions>(
          `${getURL("API_KEY")}/permission-options`,
        );
        return data;
      } catch (error) {
        const status = (error as { response?: { status?: number } }).response
          ?.status;
        if (status === 404 || status === 501) {
          return {
            supported: false,
            roles: [],
            resource_actions: {},
            scope_types: {},
          };
        }
        throw error;
      }
    },
    { retry: false, refetchOnWindowFocus: true, ...options },
  );
};
