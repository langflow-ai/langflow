import { OAuthProvidersResponse, useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetOAuthProviders: useQueryFunctionType<
  undefined,
  OAuthProvidersResponse
> = (options?) => {
  const { query } = UseRequestProcessor();

  async function getOAuthProvidersFn(): Promise<OAuthProvidersResponse> {
    const response = await api.get<OAuthProvidersResponse>(
      getURL("OAUTH_PROVIDERS"),
    );
    return response.data;
  }

  return query(["useGetOAuthProviders"], getOAuthProvidersFn, {
    refetchOnWindowFocus: false,
    ...options,
  });
};
