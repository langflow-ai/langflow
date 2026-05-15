import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteProviderAccountParams {
  provider_id: string;
}

export const useDeleteProviderAccount: useMutationFunctionType<
  undefined,
  DeleteProviderAccountParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const fn = async ({ provider_id }: DeleteProviderAccountParams) => {
    await api.delete(
      `${getURL("DEPLOYMENT_PROVIDER_ACCOUNTS")}/${provider_id}`,
    );
  };

  return mutate(["useDeleteProviderAccount"], fn, {
    ...options,
    onSuccess: (...args) => {
      queryClient.refetchQueries({ queryKey: ["useGetProviderAccounts"] });
      options?.onSuccess?.(...args);
    },
  });
};
