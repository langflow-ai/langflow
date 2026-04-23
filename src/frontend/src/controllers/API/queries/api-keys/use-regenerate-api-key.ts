import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { IApiKeysDataArray } from "./use-get-api-keys";

export interface IRegenerateApiKey {
  keyId: string;
}

export const useRegenerateApiKey: useMutationFunctionType<
  undefined,
  IRegenerateApiKey,
  IApiKeysDataArray
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const regenerateApiKeyFn = async (
    payload: IRegenerateApiKey,
  ): Promise<IApiKeysDataArray> => {
    const res = await api.post<IApiKeysDataArray>(
      `${getURL("API_KEY")}/${payload.keyId}/regenerate`,
    );
    return res.data;
  };

  const mutation = mutate(["useRegenerateApiKey"], regenerateApiKeyFn, options);

  return mutation;
};
