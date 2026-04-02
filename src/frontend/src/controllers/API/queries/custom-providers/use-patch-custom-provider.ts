import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type {
  CustomProviderRead,
  CustomProviderUpdate,
} from "@/types/custom-providers";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchCustomProviderParams {
  id: string;
  body: CustomProviderUpdate;
}

export const usePatchCustomProvider: useMutationFunctionType<
  undefined,
  PatchCustomProviderParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const patchCustomProviderFn = async (
    payload: PatchCustomProviderParams,
  ): Promise<CustomProviderRead> => {
    const res = await api.patch<CustomProviderRead>(
      `${getURL("CUSTOM_PROVIDERS")}/${payload.id}`,
      payload.body,
    );
    return res.data;
  };

  const mutation: UseMutationResult<
    CustomProviderRead,
    any,
    PatchCustomProviderParams
  > = mutate(["usePatchCustomProvider"], patchCustomProviderFn, {
    ...options,
    onSettled: () => {
      queryClient.refetchQueries({ queryKey: ["useGetCustomProviders"] });
    },
  });

  return mutation;
};
