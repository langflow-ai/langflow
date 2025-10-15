import { Cookies } from "react-cookie";
import { IS_AUTO_LOGIN, AI_STUDIO_REFRESH_TOKEN } from "@/constants/constants";
import useAuthStore from "@/stores/authStore";
import type { useMutationFunctionType } from "@/types/api";
import { setAuthCookie, getAuthCookie } from "@/utils/utils";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IRefreshAccessToken {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export const useRefreshAccessToken: useMutationFunctionType<
  undefined,
  undefined | void,
  IRefreshAccessToken
> = (options?) => {
  const { mutate } = UseRequestProcessor();
  const autoLogin = useAuthStore((state) => state.autoLogin);

  async function refreshAccess(): Promise<IRefreshAccessToken> {
    const cookies = new Cookies();

    // Get the current refresh token from cookies - this is critical for backend authentication
    const currentRefreshToken = getAuthCookie(cookies, AI_STUDIO_REFRESH_TOKEN);

    if (!currentRefreshToken) {
      throw new Error("No refresh token available");
    }

    // Send refresh token in request body like genesis-frontend does
    const res = await api.post<IRefreshAccessToken>(`${getURL("REFRESH")}`, {
      refresh_token: currentRefreshToken,
    });

    // Store the new refresh token
    setAuthCookie(cookies, AI_STUDIO_REFRESH_TOKEN, res.data.refresh_token);

    return res.data;
  }

  const mutation = mutate(["useRefreshAccessToken"], refreshAccess, {
    ...options,
    retry: IS_AUTO_LOGIN || autoLogin ? 0 : 2,
  });

  return mutation;
};
