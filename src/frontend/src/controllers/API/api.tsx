import axios, { AxiosError, AxiosInstance } from "axios";
import { useContext, useEffect } from "react";
import { Cookies } from "react-cookie";
import { useNavigate } from "react-router-dom";
import { renewAccessToken } from ".";
import { alertContext } from "../../contexts/alertContext";
import { AuthContext } from "../../contexts/authContext";

// Create a new Axios instance
const api: AxiosInstance = axios.create({
  baseURL: "",
});

function ApiInterceptor() {
  const { setErrorData } = useContext(alertContext);
  let { accessToken, login, logout, authenticationErrorCount } =
    useContext(AuthContext);
  const navigate = useNavigate();
  const cookies = new Cookies();

  console.log(accessToken);

  useEffect(() => {
    const interceptor = api.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        if (error.response?.status === 401) {
          const refreshToken = cookies.get("refresh_token");

          if (refreshToken) {
            authenticationErrorCount = authenticationErrorCount + 1;
            if (authenticationErrorCount > 3) {
              authenticationErrorCount = 0;
              logout();
              navigate("/login");
            }

            const res = await renewAccessToken(refreshToken);
            login(res.data.access_token, res.data.refresh_token);
            try {
              const accessToken = cookies.get("access_token");
              delete error.config.headers["Authorization"];
              error.config.headers["Authorization"] = `Bearer ${accessToken}`;
              const response = await axios.request(error.config);
              return response;
            } catch (error) {
              if (error.response?.status === 401) {
                logout();
                navigate("/login");
              }
            }
          } else {
            logout();
            navigate("/login");
          }
        } else {
          // if (URL_EXCLUDED_FROM_ERROR_RETRIES.includes(error.config?.url)) {
          return Promise.reject(error);
          // }
        }
        // else {
        //   let retryCount = 0;
        //   while (retryCount < 4) {
        //     await sleep(5000); // Sleep for 5 seconds
        //     retryCount++;
        //     try {
        //       const response = await axios.request(error.config);
        //       return response;
        //     } catch (error) {
        //       if (retryCount === 3) {
        //         setErrorData({
        //           title: "There was an error on web connection, please: ",
        //           list: [
        //             "Refresh the page",
        //             "Use a new flow tab",
        //             "Check if the backend is up",
        //             "Endpoint: " + error.config?.url,
        //           ],
        //         });
        //         return Promise.reject(error);
        //       }
        //     }
        //   }
        // }
      }
    );

    // Request interceptor to add access token to every request
    const requestInterceptor = api.interceptors.request.use(
      (config) => {
        if (accessToken) {
          config.headers["Authorization"] = `Bearer ${accessToken}`;
        }

        if (
          config?.url?.includes(
            "https://raw.githubusercontent.com/logspace-ai/langflow_examples/main/examples"
          ) ||
          config?.url?.includes(
            "https://api.github.com/repos/logspace-ai/langflow_examples/contents/examples"
          ) ||
          config?.url?.includes(
            "https://api.github.com/repos/logspace-ai/langflow"
          )
        ) {
          delete config.headers["Authorization"];
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

// Function to sleep for a given duration in milliseconds
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export { ApiInterceptor, api };
