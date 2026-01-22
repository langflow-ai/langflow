import type { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface SSOLoginResponse {
  authorization_url: string;
  state: string;
  provider: string;
}

export const useSSOLogin = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function ssoLoginFn(): Promise<SSOLoginResponse> {
    const res = await api.get<SSOLoginResponse>(`${getURL("SSO_LOGIN")}`);
    return res.data;
  }

  const mutation: UseMutationResult<SSOLoginResponse, any, void> = mutate(
    ["useSSOLogin"],
    ssoLoginFn,
    {
      retry: false,
      ...options,
    }
  );

  return mutation;
};