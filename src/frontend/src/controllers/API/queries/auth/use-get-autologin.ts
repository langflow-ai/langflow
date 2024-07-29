import { UseMutationResult } from "@tanstack/react-query";
import { useMutationFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface AutoLoginParams {
  abortSignal: AbortSignal;
}

export const useAutoLogin: useMutationFunctionType<undefined, any> = (
  options?,
) => {
  const { mutate } = UseRequestProcessor();

  const autoLoginFn = async ({
    abortSignal,
  }: AutoLoginParams): Promise<any> => {
    const res = await api.get(`${getURL("AUTOLOGIN")}`, {
      signal: abortSignal,
    });
    return res.data;
  };

  const mutation: UseMutationResult = mutate(
    ["useAutoLogin"],
    autoLoginFn,
    options,
  );

  return mutation;
};
