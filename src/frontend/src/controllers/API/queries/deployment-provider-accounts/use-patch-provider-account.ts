import type { ProviderAccount } from "@/pages/MainPage/pages/deploymentsPage/types";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ProviderAccountUpdateRequest {
  provider_id: string;
  name?: string;
  provider_data?: {
    api_key: string;
  };
}

export const usePatchProviderAccount: useMutationFunctionType<
  undefined,
  ProviderAccountUpdateRequest,
  ProviderAccount
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async ({
    provider_id,
    ...payload
  }: ProviderAccountUpdateRequest): Promise<ProviderAccount> => {
    const res = await api.patch<ProviderAccount>(
      `${getURL("DEPLOYMENT_PROVIDER_ACCOUNTS")}/${provider_id}`,
      payload,
    );
    return res.data;
  };

  return mutate(["usePatchProviderAccount"], fn, {
    ...options,
    retry: 0,
    onSuccess: (...args) => {
      queryClient.refetchQueries({
        queryKey: ["useGetProviderAccounts"],
      });
      options?.onSuccess?.(...args);
    },
  });
};
