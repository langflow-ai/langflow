import { LANGFLOW_ACCESS_TOKEN } from "@/constants/constants";
import { cookieManager } from "@/utils/cookie-manager";

/**
 * Get access token from cookies.
 *
 * Note: When LANGFLOW_ACCESS_HTTPONLY is enabled, this will return null
 * because HttpOnly cookies cannot be accessed by JavaScript. This is by design
 * for security. The browser automatically sends HttpOnly cookies with requests,
 * so manual token handling is not needed.
 *
 * This function is kept for backward compatibility with non-HttpOnly mode.
 */
export const customGetAccessToken = () => {
  // Try to read the cookie (will be null if HttpOnly is enabled)
  return cookieManager.get(LANGFLOW_ACCESS_TOKEN) ?? null;
};
