import type { useQueryFunctionType } from "@/types/api";
import type { CustomProviderRead } from "@/types/custom-providers";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetCustomProviders: useQueryFunctionType<
  undefined,
  CustomProviderRead[]
> = (options?) => {
  const { query } = UseRequestProcessor();

  const getCustomProvidersFn = async (): Promise<CustomProviderRead[]> => {
    const res = await api.get<CustomProviderRead[]>(
      `${getURL("CUSTOM_PROVIDERS")}/`,
    );
    return res.data;
  };

  const queryResult = query(
    ["useGetCustomProviders"],
    getCustomProvidersFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
