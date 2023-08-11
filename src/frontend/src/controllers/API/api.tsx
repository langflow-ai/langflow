import axios, { AxiosError, AxiosInstance } from "axios";
import { useContext, useEffect, useRef, useState } from "react";
import { alertContext } from "../../contexts/alertContext";
import { AuthContext } from "../../contexts/authContext";
import { URL_EXCLUDED_FROM_ERROR_RETRIES } from "../../constants/constants";
import { renewAccessToken } from ".";
import { useNavigate } from "react-router-dom";

// Create a new Axios instance
const api: AxiosInstance = axios.create({
  baseURL: "",
});

function ApiInterceptor() {
  const { setErrorData } = useContext(alertContext);
  const { accessToken, login, logout } = useContext(AuthContext);
  const navigate = useNavigate();

  useEffect(() => {
    const interceptor = api.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        if (URL_EXCLUDED_FROM_ERROR_RETRIES.includes(error.config?.url)) {
          return Promise.reject(error);
        }

        if(error.response?.status === 401){
          const refreshToken = localStorage.getItem("refresh_token");
          if (refreshToken) {
              const res = await renewAccessToken(refreshToken);
              login(res.data.access_token, res.data.refresh_token);
              try {
                  const accessToken = localStorage.getItem("access_token");
                  delete error.config.headers["Authorization"];
                  error.config.headers["Authorization"] = `Bearer ${accessToken}`;
                  const response = await axios.request(error.config);
                  return response;
                }
               catch (error) {
                if(error.response?.status === 401){
                  logout();
                  navigate("/login");
                }
              }
            }
          }

          else{
            let retryCount = 0;
            while (retryCount < 4) {
              await sleep(5000); // Sleep for 5 seconds
              retryCount++;
              try {
                const response = await axios.request(error.config);
                return response;
              } catch (error) {
                if (retryCount === 3) {
                  setErrorData({
                    title: "There was an error on web connection, please: ",
                    list: [
                      "Refresh the page",
                      "Use a new flow tab",
                      "Check if the backend is up",
                      "Endpoint: " + error.config?.url,
                    ],
                  });
                  return Promise.reject(error);
                }
              }
            }
          }
      }
    );

    // Request interceptor to add access token to every request
    const requestInterceptor = api.interceptors.request.use(
      (config) => {
        
        if (accessToken) {
          config.headers["Authorization"] = `Bearer ${accessToken}`;
        }
        
        if(
          config?.url?.includes("https://raw.githubusercontent.com/logspace-ai/langflow_examples/main/examples") ||
          config?.url?.includes("https://api.github.com/repos/logspace-ai/langflow_examples/contents/examples"))
          {
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
