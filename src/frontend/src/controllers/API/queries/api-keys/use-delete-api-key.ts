import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteApiKey {
  keyId: string;
}

// add types for error handling and success
export const useDeleteApiKey: useMutationFunctionType<
  undefined,
  IDeleteApiKey
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const deleteApiKeyFn = async (payload: IDeleteApiKey): Promise<any> => {
    const res = await api.delete(`${getURL("API_KEY")}/${payload.keyId}`);
    return res.data;
  };

  const mutation = mutate(["useDeleteApiKey"], deleteApiKeyFn, options);

  return mutation;
};
