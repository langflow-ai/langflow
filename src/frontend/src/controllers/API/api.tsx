import React, { useEffect, useContext } from 'react';
import axios, { AxiosError, AxiosInstance, AxiosResponse } from 'axios';
import { alertContext } from '../../contexts/alertContext';

// Create a new Axios instance
const api: AxiosInstance = axios.create({
  baseURL: '', // Replace with your actual API URL
});

// Create a map to store the retry counts per endpoint
const retryCounts: Map<string, number> = new Map();

function ApiInterceptor() {
  const { setErrorData } = useContext(alertContext);

  useEffect(() => {
    const interceptor = api.interceptors.response.use(
      response => response,
      async (error: AxiosError) => {
        const { url } = error.config;

        if (!retryCounts.has(url)) {
          retryCounts.set(url, 0);
        }

        const retryCount = retryCounts.get(url)!;

        if (retryCount < 3) {
          retryCounts.set(url, retryCount + 1);

          try {
            const response = await axios.request(error.config);
            return response;
          } catch (error) {
            return Promise.reject(error);
          }
        } else {
          setErrorData({
            title: 'There was an error on web connection, please: ',
            list: ['Refresh the page', 'Use a new flow tab', 'Check if the backend is up'],
          });
        }
      }
    );

    return () => {
      // Clean up the interceptor when the component unmounts
      api.interceptors.response.eject(interceptor);
    };
  }, [setErrorData]);

  return null;
}

export { api, ApiInterceptor };
