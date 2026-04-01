import type { ProviderAccount } from "@/pages/MainPage/pages/deploymentsPage/types";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ProviderAccountCreateRequest {
  name: string;
  provider_key: string;
  provider_url: string;
  provider_data: {
    api_key: string;
  };
}

export const usePostProviderAccount: useMutationFunctionType<
  undefined,
  ProviderAccountCreateRequest,
  ProviderAccount
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async (
    payload: ProviderAccountCreateRequest,
  ): Promise<ProviderAccount> => {
    const res = await api.post<ProviderAccount>(
      `${getURL("DEPLOYMENT_PROVIDER_ACCOUNTS")}`,
      payload,
    );
    return res.data;
  };

  return mutate(["usePostProviderAccount"], fn, {
    ...options,
    onSuccess: () => {
      return queryClient.refetchQueries({
        queryKey: ["useGetProviderAccounts"],
      });
    },
  });
};
