import type { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface SSOLoginResponse {
  authorization_url: string;
  state: string;
  provider_id: string;
  provider_name: string;
}

export interface SSOLoginParams {
  providerId: string;
}

export const useSSOLogin = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function ssoLoginFn(params: SSOLoginParams): Promise<SSOLoginResponse> {
    const res = await api.get<SSOLoginResponse>(`${getURL("SSO_LOGIN")}`, {
      params: { provider_id: params.providerId },
    });
    return res.data;
  }

  const mutation: UseMutationResult<SSOLoginResponse, any, SSOLoginParams> = mutate(
    ["useSSOLogin"],
    ssoLoginFn,
    {
      retry: false,
      ...options,
    }
  );

  return mutation;
};