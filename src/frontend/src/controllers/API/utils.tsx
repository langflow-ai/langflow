import axios from "axios";
import { BASE_URL_API } from "../../constants/constants";

/**
 * Fetches the configuration data from the API.
 * @returns {Promise<any>} A promise that resolves to the configuration data.
 * @throws {Error} If there was an error fetching the configuration data.
 */
export async function fetchConfig() {
  try {
    const response = await axios.get(`${BASE_URL_API}config`);
    return response.data;
  } catch (error) {
    console.error("Failed to fetch configuration:", error);
    throw error;
  }
}

/**
 * Sets up default configurations for Axios.
 * Fetches the timeout configuration and sets it as the default timeout for Axios requests.
 */
export async function setupAxiosDefaults() {
  const config = await fetchConfig();
  // Create Axios instance with the fetched timeout configuration

  const timeoutInMilliseconds = config.frontend_timeout
    ? config.frontend_timeout * 1000
    : 30000;
  axios.defaults.baseURL = "";
  axios.defaults.timeout = timeoutInMilliseconds;
}
