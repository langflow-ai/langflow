import axios, { AxiosError, AxiosInstance } from "axios";
import { useContext, useEffect } from "react";
import { Cookies } from "react-cookie";
import { useNavigate } from "react-router-dom";
import { renewAccessToken } from ".";
import { alertContext } from "../../contexts/alertContext";
import { AuthContext } from "../../contexts/authContext";

// Create a new Axios instance
const api: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_AXIOS_BASE_URL ?? "",
});

function ApiInterceptor() {
  const { setErrorData } = useContext(alertContext);
  let { accessToken, login, logout, authenticationErrorCount } =
    useContext(AuthContext);
  const navigate = useNavigate();
  const cookies = new Cookies();

  useEffect(() => {
    const interceptor = api.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        if (error.response?.status === 401) {
          const refreshToken = cookies.get("refresh_tkn_lflw");
          if (refreshToken && refreshToken !== "auto") {
            authenticationErrorCount = authenticationErrorCount + 1;
            if (authenticationErrorCount > 3) {
              authenticationErrorCount = 0;
              logout();
              navigate("/login");
            }
            try {
              const res = await renewAccessToken(refreshToken);
              if (res?.data?.access_token && res?.data?.refresh_token) {
                login(res?.data?.access_token, res?.data?.refresh_token);
              }
              if (error?.config?.headers) {
                delete error.config.headers["Authorization"];
                error.config.headers["Authorization"] = `Bearer ${cookies.get(
                  "access_tkn_lflw"
                )}`;
                const response = await axios.request(error.config);
                return response;
              }
            } catch (error) {
              if (axios.isAxiosError(error) && error.response?.status === 401) {
                logout();
                navigate("/login");
              } else {
                console.error(error);
                logout();
                navigate("/login");
              }
            }
          }

          if (!refreshToken && error?.config?.url?.includes("login")) {
            return Promise.reject(error);
          } else {
            logout();
            navigate("/login");
          }
        } else {
          // if (URL_EXCLUDED_FROM_ERROR_RETRIES.includes(error.config?.url)) {
          return Promise.reject(error);
          // }
        }
      }
    );

    const isAuthorizedURL = (url) => {
      const authorizedDomains = [
        "https://raw.githubusercontent.com/logspace-ai/langflow_examples/main/examples",
        "https://api.github.com/repos/logspace-ai/langflow_examples/contents/examples",
        "https://api.github.com/repos/logspace-ai/langflow",
        "auto_login",
      ];

      const authorizedEndpoints = ["auto_login"];

      try {
        const parsedURL = new URL(url);

        const isDomainAllowed = authorizedDomains.some(
          (domain) => parsedURL.origin === new URL(domain).origin
        );
        const isEndpointAllowed = authorizedEndpoints.some((endpoint) =>
          parsedURL.pathname.includes(endpoint)
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
        if (accessToken && !isAuthorizedURL(config?.url)) {
          config.headers["Authorization"] = `Bearer ${accessToken}`;
        }

        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    return () => {
      // Clean up the interceptors when the component unmounts
      api.interceptors.response.eject(interceptor);
      api.interceptors.request.eject(requestInterceptor);
    };
  }, [accessToken, setErrorData]);

  return null;
}

export { ApiInterceptor, api };
