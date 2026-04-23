import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { IApiKeysDataArray } from "./use-get-api-keys";

export interface IPatchApiKey {
  keyId: string;
  allowed_ips: string | null;
}

export const usePatchApiKey: useMutationFunctionType<
  undefined,
  IPatchApiKey,
  IApiKeysDataArray
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const patchApiKeyFn = async (
    payload: IPatchApiKey,
  ): Promise<IApiKeysDataArray> => {
    const res = await api.patch(`${getURL("API_KEY")}/${payload.keyId}`, {
      allowed_ips: payload.allowed_ips || null,
    });
    return res.data;
  };

  const mutation = mutate(["usePatchApiKey"], patchApiKeyFn, options);

  return mutation;
};
