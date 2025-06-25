import { IS_AUTO_LOGIN } from "@/constants/constants";
import { baseURL } from "@/customization/constants";
import { useCustomApiHeaders } from "@/customization/hooks/use-custom-api-headers";
import { customGetAccessToken } from "@/customization/utils/custom-get-access-token";
import useAuthStore from "@/stores/authStore";
import { useUtilityStore } from "@/stores/utilityStore";
import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from "axios";
import * as fetchIntercept from "fetch-intercept";
import { useEffect } from "react";
import { Cookies } from "react-cookie";
import { BuildStatus, EventDeliveryType } from "../../constants/enums";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import { useClerkAccessToken } from "./clerk-access-token";
import { checkDuplicateRequestAndStoreRequest } from "./helpers/check-duplicate-requests";
import { useLogout, useRefreshAccessToken } from "./queries/auth";

// Create a new Axios instance
const api: AxiosInstance = axios.create({
  baseURL: baseURL,
});

const cookies = new Cookies();
const CLERK_AUTH_ENABLED = import.meta.env.VITE_CLERK_AUTH_ENABLED === "true";

function ApiInterceptor() {
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const accessToken = useAuthStore((state) => state.accessToken);
  const authenticationErrorCount = useAuthStore(
    (state) => state.authenticationErrorCount,
  );
  const setAuthenticationErrorCount = useAuthStore(
    (state) => state.setAuthenticationErrorCount,
  );
  const { mutate: mutationLogout } = useLogout();
  const { mutate: mutationRenewAccessToken } = useRefreshAccessToken();
  const isLoginPage = location.pathname.includes("login");
  const customHeaders = useCustomApiHeaders();
  const getClerkAccessToken = useClerkAccessToken();
  const setHealthCheckTimeout = useUtilityStore(
    (state) => state.setHealthCheckTimeout,
  );

  useEffect(() => {
    const unregister = fetchIntercept.register({
      request: function (url, config) {
        const accessToken = customGetAccessToken();
        if (accessToken && !isAuthorizedURL(config?.url)) {
          config.headers["Authorization"] = `Bearer ${accessToken}`;
        }

        if (!isExternalURL(url)) {
          for (const [key, value] of Object.entries(customHeaders)) {
            config.headers[key] = value;
          }
        }

        return [url, config];
      },
    });

    const interceptor = api.interceptors.response.use(
      (response) => {
        setHealthCheckTimeout(null);
        return response;
      },
      async (error: AxiosError) => {
        const isAuthenticationError = [401, 403].includes(
          error?.response?.status || 0,
        );
        const shouldRetryRefresh =
          (isAuthenticationError && !autoLogin) ||
          (isAuthenticationError && autoLogin === undefined);

        if (shouldRetryRefresh) {
          if (
            error?.config?.url?.includes("github") ||
            error?.config?.url?.includes("public")
          ) {
            return Promise.reject(error);
          }

          const stillRefresh = checkErrorCount();
          if (!stillRefresh) return Promise.reject(error);

          await tryToRenewAccessToken(error);

          const accessToken = customGetAccessToken();
          if (!accessToken && error?.config?.url?.includes("login")) {
            return Promise.reject(error);
          }
        }

        await clearBuildVerticesState(error);
        if (!isAuthenticationError) return Promise.reject(error);
      },
    );

    const isAuthorizedURL = (url) => {
      const authorizedDomains = [
        "https://raw.githubusercontent.com/langflow-ai/langflow_examples/main/examples",
        "https://api.github.com/repos/langflow-ai/langflow_examples/contents/examples",
        "https://api.github.com/repos/langflow-ai/langflow",
        "auto_login",
      ];
      const authorizedEndpoints = ["auto_login"];

      try {
        const parsedURL = new URL(url);
        return (
          authorizedDomains.some(
            (domain) => parsedURL.origin === new URL(domain).origin,
          ) ||
          authorizedEndpoints.some((endpoint) =>
            parsedURL.pathname.includes(endpoint),
          )
        );
      } catch {
        return false;
      }
    };

    const isExternalURL = (url: string): boolean => {
      const EXTERNAL_DOMAINS = [
        "https://raw.githubusercontent.com",
        "https://api.github.com",
        "https://api.segment.io",
        "https://cdn.sprig.com",
      ];
      try {
        const parsedURL = new URL(url);
        return EXTERNAL_DOMAINS.some((domain) => parsedURL.origin === domain);
      } catch {
        return false;
      }
    };

    const requestInterceptor = api.interceptors.request.use(
      async (config) => {
        let accessToken = customGetAccessToken();
        if (CLERK_AUTH_ENABLED) {
          accessToken = await getClerkAccessToken();
          console.debug("[CLERK][API] Clerk token:", accessToken?.slice(0, 30));
        } else {
          console.debug("[CLERK][API] Legacy token:", accessToken);
        }

        if (accessToken && !isAuthorizedURL(config?.url)) {
          config.headers["Authorization"] = `Bearer ${accessToken}`;
        }

        const controller = new AbortController();
        try {
          checkDuplicateRequestAndStoreRequest(config);
        } catch (e) {
          controller.abort((e as Error).message);
          console.error(e);
        }

        const currentOrigin = window.location.origin;
        const requestUrl = new URL(config?.url as string, currentOrigin);
        if (requestUrl.origin === currentOrigin) {
          for (const [key, value] of Object.entries(customHeaders)) {
            config.headers[key] = value;
          }
        }

        return { ...config, signal: controller.signal };
      },
      (error) => Promise.reject(error),
    );

    return () => {
      api.interceptors.response.eject(interceptor);
      api.interceptors.request.eject(requestInterceptor);
      unregister();
    };
  }, [accessToken, setErrorData, customHeaders, autoLogin]);

  function checkErrorCount() {
    if (isLoginPage) return;
    setAuthenticationErrorCount(authenticationErrorCount + 1);
    if (authenticationErrorCount > 3) {
      setAuthenticationErrorCount(0);
      mutationLogout();
      return false;
    }
    return true;
  }

  async function tryToRenewAccessToken(error: AxiosError) {
    if (isLoginPage) return;

    if (error.config?.headers) {
      for (const [key, value] of Object.entries(customHeaders)) {
        error.config.headers[key] = value;
      }
    }

    mutationRenewAccessToken(undefined, {
      onSuccess: async () => {
        setAuthenticationErrorCount(0);
        await remakeRequest(error);
      },
      onError: (error) => {
        console.error(error);
        mutationLogout();
        return Promise.reject("Authentication error");
      },
    });
  }

  async function clearBuildVerticesState(error) {
    if (error?.response?.status === 500) {
      const vertices = useFlowStore.getState().verticesBuild;
      useFlowStore
        .getState()
        .updateBuildStatus(vertices?.verticesIds ?? [], BuildStatus.BUILT);
      useFlowStore.getState().setIsBuilding(false);
    }
  }

  async function remakeRequest(error: AxiosError) {
    const originalRequest = error.config as AxiosRequestConfig;
    try {
      let accessToken = customGetAccessToken();
      if (CLERK_AUTH_ENABLED) {
        accessToken = await getClerkAccessToken();
      }
      if (!accessToken) throw new Error("Access token not found");
      originalRequest.headers = {
        ...(originalRequest.headers as Record<string, string>),
        Authorization: `Bearer ${accessToken}`,
      };
      const response = await axios.request(originalRequest);
      return response.data;
    } catch (err) {
      throw err;
    }
  }

  return null;
}

export type StreamingRequestParams = {
  method: string;
  url: string;
  onData: (event: object) => Promise<boolean>;
  body?: object;
  onError?: (statusCode: number) => void;
  onNetworkError?: (error: Error) => void;
  buildController: AbortController;
  eventDeliveryConfig?: EventDeliveryType;
};

async function performStreamingRequest({
  method,
  url,
  onData,
  body,
  onError,
  onNetworkError,
  buildController,
}: StreamingRequestParams) {
  let headers = {
    "Content-Type": "application/json",
    // this flag is fundamental to ensure server stops tasks when client disconnects
    Connection: "close",
  };

  const params = {
    method: method,
    headers: headers,
    signal: buildController.signal,
  };
  if (body) {
    params["body"] = JSON.stringify(body);
  }
  let current: string[] = [];
  let textDecoder = new TextDecoder();

  try {
    const response = await fetch(url, params);
    if (!response.ok) {
      if (onError) {
        onError(response.status);
      } else {
        throw new Error("Error in streaming request.");
      }
    }
    if (response.body === null) {
      return;
    }
    const reader = response.body.getReader();
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      const decodedChunk = textDecoder.decode(value);
      let all = decodedChunk.split("\n\n");
      for (const string of all) {
        if (string.endsWith("}")) {
          const allString = current.join("") + string;
          let data: object;
          try {
            data = JSON.parse(allString);
            current = [];
          } catch (e) {
            current.push(string);
            continue;
          }
          const shouldContinue = await onData(data);
          if (!shouldContinue) {
            buildController.abort();
            return;
          }
        } else {
          current.push(string);
        }
      }
    }
    if (current.length > 0) {
      const allString = current.join("");
      if (allString) {
        const data = JSON.parse(current.join(""));
        await onData(data);
      }
    }
  } catch (e: any) {
    if (onNetworkError) {
      onNetworkError(e);
    } else {
      throw e;
    }
  }
}

export { api, ApiInterceptor, performStreamingRequest };
