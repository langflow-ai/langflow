import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type {
  CustomProviderCreate,
  CustomProviderRead,
} from "@/types/custom-providers";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const usePostCustomProvider: useMutationFunctionType<
  undefined,
  CustomProviderCreate
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const postCustomProviderFn = async (
    payload: CustomProviderCreate,
  ): Promise<CustomProviderRead> => {
    const res = await api.post<CustomProviderRead>(
      `${getURL("CUSTOM_PROVIDERS")}/`,
      payload,
    );
    return res.data;
  };

  const mutation: UseMutationResult<
    CustomProviderRead,
    any,
    CustomProviderCreate
  > = mutate(["usePostCustomProvider"], postCustomProviderFn, {
    ...options,
    onSettled: () => {
      queryClient.refetchQueries({ queryKey: ["useGetCustomProviders"] });
    },
  });

  return mutation;
};
