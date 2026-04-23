import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { IApiKeysDataArray } from "./use-get-api-keys";

export interface IPatchApiKey {
  keyId: string;
  name?: string | null;
  allowed_ips?: string | null;
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
    const { keyId, ...rest } = payload;
    const body: { name?: string | null; allowed_ips?: string | null } = {};
    if ("name" in rest) {
      body.name = rest.name ?? null;
    }
    if ("allowed_ips" in rest) {
      body.allowed_ips = rest.allowed_ips ?? null;
    }
    const res = await api.patch(`${getURL("API_KEY")}/${keyId}`, body);
    return res.data;
  };

  const mutation = mutate(["usePatchApiKey"], patchApiKeyFn, options);

  return mutation;
};
