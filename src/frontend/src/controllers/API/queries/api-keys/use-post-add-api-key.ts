import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostAddApiKey {
  key: string;
}

// add types for error handling and success
export const usePostAddApiKey: useMutationFunctionType<IPostAddApiKey> = (
  options,
) => {
  const { mutate } = UseRequestProcessor();

  const postAddApiKeyFn = async (payload: IPostAddApiKey): Promise<any> => {
    return await api.post<any>(`${getURL("API_KEY")}/store`, {
      api_key: payload.key,
    });
  };

  const mutation: UseMutationResult<any, any, IPostAddApiKey> = mutate(
    ["usePostAddApiKey"],
    async (payload: IPostAddApiKey) => {
      const res = await postAddApiKeyFn(payload);
      return res.data;
    },
    options,
  );

  return mutation;
};
