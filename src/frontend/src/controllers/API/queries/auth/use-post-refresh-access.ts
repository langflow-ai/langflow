import type { useMutationFunctionType } from "@/types/api";
import {
  type RefreshAccessTokenResponse,
  refreshAccessToken,
} from "../../services/auth-session";
import { UseRequestProcessor } from "../../services/request-processor";

export const useRefreshAccessToken: useMutationFunctionType<
  undefined,
  undefined | void,
  RefreshAccessTokenResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  return mutate(["useRefreshAccessToken"], refreshAccessToken, {
    ...options,
    // A failed response can follow a committed one-use token exchange.
    retry: false,
  });
};
