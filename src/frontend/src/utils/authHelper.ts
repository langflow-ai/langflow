import { envConfig } from "@/config/env";
import KeycloakService from "@/services/keycloak";
import { customGetAccessToken } from "@/customization/utils/custom-get-access-token";

/**
 * Centralized token access function following Genesis frontend pattern
 * Prioritizes Keycloak tokens when enabled, falls back to traditional auth
 */
export const getAccessToken = (): string | undefined => {
  if (envConfig.keycloakEnabled) {
    const keycloakService = KeycloakService.getInstance();
    return keycloakService.getToken();
  }
  return customGetAccessToken();
};

/**
 * Genesis-style header management for API requests
 * Adds proper Bearer token authentication headers
 */
export const withAuthHeaders = (headers: Record<string, string> = {}): Record<string, string> => {
  const token = getAccessToken();

  if (token) {
    headers["authorization"] = `Bearer ${token}`;
    if (envConfig.keycloakEnabled) {
      headers["x-user-token"] = "true";
    }
  }

  return headers;
};

/**
 * Legacy authHeaders function for backward compatibility
 */
export const authHeaders = (headers: Record<string, string>, token: string): Record<string, string> => {
  headers["authorization"] = `Bearer ${token}`;
  if (envConfig.keycloakEnabled) {
    headers["x-user-token"] = "true";
  }
  return headers;
};

/**
 * Check if user is authenticated using appropriate method
 */
export const isAuthenticated = (): boolean => {
  if (envConfig.keycloakEnabled) {
    const keycloakService = KeycloakService.getInstance();
    return keycloakService.isAuthenticated();
  }

  const token = customGetAccessToken();
  return !!token;
};

/**
 * Handle token refresh using appropriate mechanism
 */
export const handleTokenRefresh = async (): Promise<string | null> => {
  if (envConfig.keycloakEnabled) {
    const keycloakService = KeycloakService.getInstance();
    try {
      const refreshed = await keycloakService.updateToken(30); // 30 seconds min validity
      if (refreshed) {
        return keycloakService.getToken() || null;
      }
      return keycloakService.getToken() || null;
    } catch (error) {
      console.error("Keycloak token refresh failed:", error);
      await keycloakService.logout();
      throw error;
    }
  }

  // Traditional refresh logic would go here
  // For now, return the existing token
  return customGetAccessToken() || null;
};

/**
 * Check if token is expired
 */
export const isTokenExpired = (): boolean => {
  if (envConfig.keycloakEnabled) {
    const keycloakService = KeycloakService.getInstance();
    return keycloakService.isTokenExpired();
  }

  // For traditional auth, we don't have a direct way to check expiration
  // The API will return 401 if expired
  return false;
};

/**
 * Handle user logout using appropriate mechanism
 */
export const handleLogout = async (): Promise<void> => {
  if (envConfig.keycloakEnabled) {
    const keycloakService = KeycloakService.getInstance();
    await keycloakService.logout();
    return;
  }

  // Traditional logout logic would be handled by existing logout mutation
  // This is just a placeholder for the interface
};