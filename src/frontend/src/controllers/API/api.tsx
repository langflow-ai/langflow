import { LANGFLOW_ACCESS_TOKEN } from "@/constants/constants";
import { useCustomApiHeaders } from "@/customization/hooks/use-custom-api-headers";
import useAuthStore from "@/stores/authStore";
import { useUtilityStore } from "@/stores/utilityStore";
import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from "axios";
import * as fetchIntercept from "fetch-intercept";
import { useEffect, useRef } from "react";
import { Cookies } from "react-cookie";
import { BuildStatus } from "../../constants/enums";
import useAlertStore from "../../stores/alertStore";
import useFlowStore from "../../stores/flowStore";
import { checkDuplicateRequestAndStoreRequest } from "./helpers/check-duplicate-requests";
import { useLogout, useRefreshAccessToken } from "./queries/auth";

// Define request timeout
const REQUEST_TIMEOUT = 30000; // 30 seconds 

// Special handling error codes
const AUTH_ERROR_CODES = [401, 403];
const SERVER_ERROR_CODES = [500, 502, 503, 504];

// Create a new Axios instance with default config
const api: AxiosInstance = axios.create({
  baseURL: "",
  timeout: REQUEST_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  }
});

const cookies = new Cookies();

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

  const setHealthCheckTimeout = useUtilityStore(
    (state) => state.setHealthCheckTimeout,
  );
  
  // Use ref to prevent multiple concurrent token refresh requests
  const isRefreshing = useRef(false);
  // Queue requests waiting for token refresh
  const requestQueue = useRef<(() => void)[]>([]);

  // List of URLs that don't require authentication
  const nonAuthUrls = [
    "https://raw.githubusercontent.com/langflow-ai/langflow_examples/main/examples",
    "https://api.github.com/repos/langflow-ai/langflow_examples/contents/examples",
    "https://api.github.com/repos/langflow-ai/langflow",
    "auto_login",
  ];

  // Check if URL doesn't require authentication
  const isNonAuthUrl = (url: string | undefined): boolean => {
    if (!url) return false;
    return nonAuthUrls.some(authUrl => url.includes(authUrl));
  };

  // Handle token refresh and queued requests
  const handleTokenRefresh = async (originalError: AxiosError) => {
    // Return a new promise that will be resolved when token refresh is complete
    return new Promise((resolve, reject) => {
      // Function to retry the original request with new token
      const retryOriginalRequest = async () => {
        try {
          const newToken = cookies.get(LANGFLOW_ACCESS_TOKEN);
          if (!newToken) {
            return reject(originalError);
          }
          
          // Clone the original request config and update the authorization header
          const newConfig = { 
            ...originalError.config, 
            headers: { 
              ...(originalError.config?.headers || {}), 
              Authorization: `Bearer ${newToken}` 
            } 
          } as AxiosRequestConfig;
          
          // Execute the request again with the new token
          const response = await axios(newConfig);
          resolve(response);
        } catch (error) {
          reject(error);
        }
      };

      // If token refresh is already in progress, queue this request
      if (isRefreshing.current) {
        requestQueue.current.push(retryOriginalRequest);
        return;
      }

      // Start token refresh process
      isRefreshing.current = true;

      // Execute token refresh request
      mutationRenewAccessToken(undefined, {
        onSuccess: () => {
          // Reset error counter
          setAuthenticationErrorCount(0);
          
          // Process original request
          retryOriginalRequest();
          
          // Process all queued requests
          requestQueue.current.forEach(request => request());
          requestQueue.current = [];
        },
        onError: () => {
          // Token refresh failed, logout user
          mutationLogout();
          reject(originalError);
        },
        onSettled: () => {
          isRefreshing.current = false;
        }
      });
    });
  };

  // Clear build state on API errors
  const clearBuildVerticesState = () => {
    const vertices = useFlowStore.getState().verticesBuild;
    useFlowStore
      .getState()
      .updateBuildStatus(vertices?.verticesIds ?? [], BuildStatus.BUILT);
    useFlowStore.getState().setIsBuilding(false);
  };

  useEffect(() => {
    // Handle requests before they are sent
    const requestInterceptor = api.interceptors.request.use(
      (config) => {
        // Create abort controller for request
        const controller = new AbortController();
        
        try {
          // Check and prevent duplicate requests
          checkDuplicateRequestAndStoreRequest(config);
        } catch (e) {
          const error = e as Error;
          controller.abort(error.message);
          console.error(error.message);
        }

        // Add token to header if available and request isn't in non-auth list
        const accessToken = cookies.get(LANGFLOW_ACCESS_TOKEN);
        if (accessToken && !isNonAuthUrl(config?.url)) {
          config.headers.Authorization = `Bearer ${accessToken}`;
        }

        // Add custom headers for requests to the same domain
        const currentOrigin = window.location.origin;
        if (config.url) {
          const requestUrl = new URL(config.url, currentOrigin);
          const urlIsFromCurrentOrigin = requestUrl.origin === currentOrigin;
          
          if (urlIsFromCurrentOrigin) {
            Object.entries(customHeaders).forEach(([key, value]) => {
              config.headers[key] = value;
            });
          }
        }

        return {
          ...config,
          signal: controller.signal,
        };
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Handle response processing
    const responseInterceptor = api.interceptors.response.use(
      (response) => {
        // Reset health check timeout on successful response
        setHealthCheckTimeout(null);
        return response;
      },
      async (error: AxiosError) => {
        const statusCode = error?.response?.status;
        
        // Handle authentication errors (401, 403)
        if (statusCode && AUTH_ERROR_CODES.includes(statusCode)) {
          if (autoLogin === false || isLoginPage) {
            // If auto login is disabled or on login page, don't handle
            return Promise.reject(error);
          }
          
          // Check authentication error count
          if (authenticationErrorCount >= 3) {
            setAuthenticationErrorCount(0);
            mutationLogout();
            return Promise.reject(error);
          }
          
          // Increment authentication error count
          setAuthenticationErrorCount(authenticationErrorCount + 1);
          
          // Handle token refresh
          return handleTokenRefresh(error);
        }
        
        // Handle server errors (500, 502, 503, 504)
        if (statusCode && SERVER_ERROR_CODES.includes(statusCode)) {
          // Reset building states if server error occurs
          clearBuildVerticesState();
          
          // Show server error message
          setErrorData({
            title: "Server Error",
            list: ["A server error occurred. Please try again later."],
          });
        }
        
        return Promise.reject(error);
      }
    );
    
    // Handle fetch API interceptor
    const unregisterFetchInterceptor = fetchIntercept.register({
      request: function (url, config) {
        const accessToken = cookies.get(LANGFLOW_ACCESS_TOKEN);
        if (accessToken && !isNonAuthUrl(config?.url)) {
          config.headers["Authorization"] = `Bearer ${accessToken}`;
        }

        Object.entries(customHeaders).forEach(([key, value]) => {
          config.headers[key] = value;
        });
        
        return [url, config];
      },
    });

    // Clean up when component unmounts
    return () => {
      api.interceptors.request.eject(requestInterceptor);
      api.interceptors.response.eject(responseInterceptor);
      unregisterFetchInterceptor();
    };
  }, [
    accessToken, 
    setErrorData, 
    customHeaders, 
    autoLogin, 
    authenticationErrorCount,
    setAuthenticationErrorCount
  ]);

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
    // This flag is fundamental to ensure server stops tasks when client disconnects
    Connection: "close",
  };

  // Add authorization header with access token if available
  const accessToken = cookies.get(LANGFLOW_ACCESS_TOKEN);
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

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
        throw new Error(`Error in streaming request: ${response.status} ${response.statusText}`);
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
    
    // Process any remaining data
    if (current.length > 0) {
      const allString = current.join("");
      if (allString) {
        try {
          const data = JSON.parse(allString);
          await onData(data);
        } catch (e) {
          console.error("Error parsing final chunk:", e);
        }
      }
    }
  } catch (e: any) {
    // Handle network errors or aborted requests
    if (e.name === 'AbortError') {
      console.log('Streaming request was aborted');
      return;
    }
    
    if (onNetworkError) {
      onNetworkError(e);
    } else {
      throw e;
    }
  }
}

export { api, ApiInterceptor, performStreamingRequest };