import { renewAccessToken } from "@/controllers/API";
import useAuthStore from "@/stores/authStore";
import { AxiosError } from "axios";
import { jwtDecode } from "jwt-decode";
import { useEffect } from "react";
import { ENABLE_DATASTAX_LANGFLOW } from "../feature-flags";

export function useCustomTokenRefresh(onRefreshComplete?: () => void) {
  // Get authentication-related functions from the auth store
  const { accessToken, setAccessToken, logout } = useAuthStore((state) => ({
    accessToken: state.accessToken,
    setAccessToken: state.setAccessToken,
    logout: state.logout,
  }));

  useEffect(() => {
    // Early return if DataStax feature flag is not enabled
    if (!ENABLE_DATASTAX_LANGFLOW) return;

    // Function to check and refresh token if needed
    const checkAndRefreshToken = async () => {
      if (shouldRefreshToken()) {
        const success = await handleTokenRefresh();
        if (!success) {
          // If refresh fails, log the user out
          logout();
          return;
        }
      }
      // Call the optional callback if provided
      onRefreshComplete?.();
    };

    // Initial check when component mounts
    checkAndRefreshToken();

    // Set up periodic check every minute (60,000 milliseconds)
    const interval = setInterval(checkAndRefreshToken, 60 * 1000);

    // Cleanup interval when component unmounts
    return () => clearInterval(interval);
  }, [accessToken]);

  // Attempts to refresh the access token
  async function handleTokenRefresh() {
    try {
      const response = await renewAccessToken();
      if (response.status === 200 && response.data.access_token) {
        // If successful, update the token in the store
        setAccessToken(response.data.access_token);
        return true;
      }
      return false;
    } catch (error) {
      // If unauthorized error occurs, log out the user
      if (error instanceof AxiosError && error.response?.status === 401) {
        await logout();
      }
      return false;
    }
  }

  // Determines if the current token needs to be refreshed
  function shouldRefreshToken() {
    if (!accessToken) return false;

    try {
      // Decode the JWT token to get expiration time
      const decodedToken: { exp: number } = jwtDecode(accessToken);
      // Convert expiration time to milliseconds
      const expirationTime = decodedToken.exp * 1000;
      const currentTime = Date.now();
      const timeUntilExpiry = expirationTime - currentTime;

      // Return true if token expires in less than 5 minutes (300,000 milliseconds)
      return timeUntilExpiry < 5 * 60 * 1000;
    } catch (error) {
      // If token can't be decoded, assume it's invalid
      return false;
    }
  }

  // Expose these functions for external use if needed
  return {
    handleTokenRefresh,
    shouldRefreshToken,
  };
}
