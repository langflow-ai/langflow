import axios, { AxiosError, AxiosInstance } from "axios";
import { useContext, useEffect, useRef } from "react";
import { URL_EXCLUDED_FROM_ERROR_RETRIES } from "../../constants/constants";
import { alertContext } from "../../contexts/alertContext";

// Create a new Axios instance
const api: AxiosInstance = axios.create({
  baseURL: "",
});

function ApiInterceptor() {
  const retryCounts = useRef([]);
  const { setErrorData } = useContext(alertContext);

  useEffect(() => {
    const interceptor = api.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        if (URL_EXCLUDED_FROM_ERROR_RETRIES.includes(error.config?.url)) {
          return Promise.reject(error);
        }
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
    );

    return () => {
      // Clean up the interceptor when the component unmounts
      api.interceptors.response.eject(interceptor);
    };
  }, [retryCounts]);

  return null;
}

// Function to sleep for a given duration in milliseconds
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export { ApiInterceptor, api };
