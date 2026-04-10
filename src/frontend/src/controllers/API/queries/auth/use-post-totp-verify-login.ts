import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface TOTPVerifyLoginParams {
  partial_token: string;
  code: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export const usePostTotpVerifyLogin: useMutationFunctionType<
  undefined,
  TOTPVerifyLoginParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function verifyTotpLogin(
    params: TOTPVerifyLoginParams,
  ): Promise<TokenResponse> {
    const res = await api.post<TokenResponse>(
      `${getURL("TOTP_VERIFY_LOGIN")}`,
      params,
    );
    return res.data;
  }

  const mutation: UseMutationResult<
    TokenResponse,
    Error,
    TOTPVerifyLoginParams
  > = mutate(["usePostTotpVerifyLogin"], verifyTotpLogin, {
    retry: false,
    ...options,
    onSuccess: () => {
      queryClient.clear();
    },
  });

  return mutation;
};
