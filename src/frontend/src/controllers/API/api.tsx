import { LANGFLOW_ACCESS_TOKEN } from "@/constants/constants";
import useAuthStore from "@/stores/authStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from "axios";
import { useContext, useEffect } from "react";
import { Cookies } from "react-cookie";
import { BuildStatus } from "../../constants/enums";
import { AuthContext } from "../../contexts/authContext";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import { checkDuplicateRequestAndStoreRequest } from "./helpers/check-duplicate-requests";
import { useLogout, useRefreshAccessToken } from "./queries/auth";

// Create a new Axios instance
const api: AxiosInstance = axios.create({
  baseURL: "",
});

function ApiInterceptor() {
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  let { accessToken, authenticationErrorCount } = useContext(AuthContext);
  const cookies = new Cookies();
  const setSaveLoading = useFlowsManagerStore((state) => state.setSaveLoading);
  const { mutate: mutationLogout } = useLogout();
  const { mutate: mutationRenewAccessToken } = useRefreshAccessToken();
  const logout = useAuthStore((state) => state.logout);
  const isLoginPage = location.pathname.includes("login");

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

            await tryToRenewAccessToken(error);

            const accessToken = cookies.get(LANGFLOW_ACCESS_TOKEN);
            if (!accessToken && error?.config?.url?.includes("login")) {
              return Promise.reject(error);
            }
          }
        }
        await clearBuildVerticesState(error);
        if (
          error?.response?.status !== 401 &&
          error?.response?.status !== 403
        ) {
          return Promise.reject(error);
        }
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

        const accessToken = cookies.get(LANGFLOW_ACCESS_TOKEN);
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
    if (isLoginPage) return;

    authenticationErrorCount = authenticationErrorCount + 1;

    if (authenticationErrorCount > 3) {
      authenticationErrorCount = 0;
      mutationLogout(undefined, {
        onSuccess: () => {
          logout();
        },
        onError: (error) => {
          console.error(error);
        },
      });
      return false;
    }

    return true;
  }

  async function tryToRenewAccessToken(error: AxiosError) {
    if (isLoginPage) return;
    mutationRenewAccessToken(
      {},
      {
        onSuccess: async (data) => {
          authenticationErrorCount = 0;
          await remakeRequest(error);
          setSaveLoading(false);
          authenticationErrorCount = 0;
        },
        onError: (error) => {
          console.error(error);
          mutationLogout(undefined, {
            onSuccess: () => {
              logout();
            },
            onError: (error) => {
              console.error(error);
            },
          });
          return Promise.reject("Authentication error");
        },
      },
    );
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
      const accessToken = cookies.get(LANGFLOW_ACCESS_TOKEN);
      if (!accessToken) {
        throw new Error("Access token not found in cookies");
      }

      // Modify headers in originalRequest
      originalRequest.headers = {
        ...(originalRequest.headers as Record<string, string>), // Cast to suppress TypeScript error
        Authorization: `Bearer ${accessToken}`,
      };

      const response = await axios.request(originalRequest);
      return response.data; // Or handle the response as needed
    } catch (err) {
      throw err; // Throw the error if request fails again
    }
  }

  return null;
}

export { ApiInterceptor, api };
