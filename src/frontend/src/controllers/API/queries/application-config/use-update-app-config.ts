import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { IApplicationConfig } from "./use-get-app-config";
import { getBackendUrl } from "@/config/constants";

interface IUpdateAppConfigPayload {
  key: string;
  value: string;
  description?: string;
}

export const useUpdateAppConfig: useMutationFunctionType<
  undefined,
  IUpdateAppConfigPayload,
  IApplicationConfig
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const updateAppConfigFn = async (
    payload: IUpdateAppConfigPayload
  ): Promise<IApplicationConfig> => {
    const { key, value, description } = payload;
    const res = await api.put<IApplicationConfig>(
      `${getBackendUrl()}/api/v1/application-config/${key}`,
      {
        value,
        description,
      }
    );
    return res.data;
  };

  const mutation = mutate(["useUpdateAppConfig"], updateAppConfigFn, options);

  return mutation;
};
