import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useDeleteCustomProvider: useMutationFunctionType<
  undefined,
  string
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteCustomProviderFn = async (id: string): Promise<void> => {
    await api.delete(`${getURL("CUSTOM_PROVIDERS")}/${id}`);
  };

  const mutation: UseMutationResult<void, any, string> = mutate(
    ["useDeleteCustomProvider"],
    deleteCustomProviderFn,
    {
      ...options,
      onSettled: () => {
        queryClient.refetchQueries({ queryKey: ["useGetCustomProviders"] });
      },
    },
  );

  return mutation;
};
