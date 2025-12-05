import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL, URLs } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";


export interface IApplicationConfig {
  id: string;
  key: string;
  value: string;
  type: string;
  description?: string;
  created_at: string;
  updated_at?: string;
  updated_by?: string;
}

export const useGetAppConfig: useQueryFunctionType<
  { key: string },
  IApplicationConfig
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getAppConfigFn = async () => {
    return await api.get<IApplicationConfig>(
      getURL("APPLICATION_CONFIG", { key: params.key })
    );
  };

  const responseFn = async () => {
    const { data } = await getAppConfigFn();
    return data;
  };

  const queryResult = query(
    ["useGetAppConfig", params.key],
    responseFn,
    {
      refetchOnMount: "always",  // Always fetch fresh data when component mounts (page load/reload)
      ...options,
      enabled: !!params.key && (options?.enabled ?? true),
    }
  );

  return queryResult;
};
