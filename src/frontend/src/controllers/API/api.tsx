import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from 'axios';
import React from 'react';

import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

// Create a new Axios instance
const api: AxiosInstance = axios.create({
  baseURL: '', // Replace with your actual API URL
});

// Create a map to store the retry counts per endpoint
const retryCounts: Map<string, number> = new Map();

// Define the interceptor to handle errors and retries
api.interceptors.response.use(
  response => response,
  async (error: AxiosError) => {
    const { url }: AxiosRequestConfig = error.config;

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
      toast.error('Request failed after 3 retries');
      return Promise.reject(error);
    }
  }
);


export default api;
