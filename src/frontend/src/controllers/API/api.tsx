import axios, { AxiosError, AxiosInstance } from "axios";
import { useContext, useEffect } from "react";
import { Cookies } from "react-cookie";
import { renewAccessToken } from ".";
import { BuildStatus } from "../../constants/enums";
import { AuthContext } from "../../contexts/authContext";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import { checkDuplicateRequestAndStoreRequest } from "./helpers/check-duplicate-requests";

// Create a new Axios instance
const api: AxiosInstance = axios.create({
  baseURL: "",
});

function ApiInterceptor() {
  const setErrorData = useAlertStore((state) => state.setErrorData);
  let { accessToken, login, logout, authenticationErrorCount, autoLogin } =
    useContext(AuthContext);
  const cookies = new Cookies();

  useEffect(() => {
    const interceptor = api.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        if (
          error?.response?.status === 403 ||
          error?.response?.status === 401
        ) {
          if (!autoLogin) {
            if (error?.config?.url?.includes("github")) {
              return Promise.reject(error);
            }
            const stillRefresh = checkErrorCount();
            if (!stillRefresh) {
              return Promise.reject(error);
            }
            const acceptedRequest = await tryToRenewAccessToken(error);

            const accessToken = cookies.get("access_token_lf");

            if (!accessToken && error?.config?.url?.includes("login")) {
              return Promise.reject(error);
            }

            return acceptedRequest;
          }
        }
        await clearBuildVerticesState(error);
        return Promise.reject(error);
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

        const isDomainAllowed = authorizedDomains.some(
          (domain) => parsedURL.origin === new URL(domain).origin,
        );
        const isEndpointAllowed = authorizedEndpoints.some((endpoint) =>
          parsedURL.pathname.includes(endpoint),
        );

        return isDomainAllowed || isEndpointAllowed;
      } catch (e) {
        // Invalid URL
        return false;
      }
    };

    // Request interceptor to add access token to every request
    const requestInterceptor = api.interceptors.request.use(
      (config) => {
        const checkRequest = checkDuplicateRequestAndStoreRequest(config);

        const controller = new AbortController();

        if (!checkRequest) {
          controller.abort("Duplicate Request");
          console.error("Duplicate Request");
        }

        const accessToken = cookies.get("access_token_lf");
        if (accessToken && !isAuthorizedURL(config?.url)) {
          config.headers["Authorization"] = `Bearer ${accessToken}`;
        }

        return {
          ...config,
          signal: controller.signal,
        };
      },
      (error) => {
        return Promise.reject(error);
      },
    );

    return () => {
      // Clean up the interceptors when the component unmounts
      api.interceptors.response.eject(interceptor);
      api.interceptors.request.eject(requestInterceptor);
    };
  }, [accessToken, setErrorData]);

  function checkErrorCount() {
    authenticationErrorCount = authenticationErrorCount + 1;

    if (authenticationErrorCount > 3) {
      authenticationErrorCount = 0;
      logout();
      return false;
    }

    return true;
  }

  async function tryToRenewAccessToken(error: AxiosError) {
    try {
      if (window.location.pathname.includes("/login")) return;
      const res = await renewAccessToken();
      if (res?.data?.access_token && res?.data?.refresh_token) {
        login(res?.data?.access_token);
      }
    } catch (error) {
      clearBuildVerticesState(error);
      logout();
      return Promise.reject("Authentication error");
    }
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

  return null;
}

export { ApiInterceptor, api };
