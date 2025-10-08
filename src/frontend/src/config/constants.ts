// AI Studio Runtime Environment Configuration
// This file replaces hardcoded values with runtime environment variables

import { envConfig } from "./env";

/**
 * Get backend URL from runtime environment
 * Fallback to relative URLs for development proxy
 */
export const getBackendUrl = (): string => {
  if (import.meta.env?.DEV && !envConfig.backendUrl) {
    // Development mode - use proxy
    return "";
  }
  return envConfig.backendUrl || "http://localhost:7860";
};

/**
 * Get API prefix from runtime environment
 */
export const getApiPrefix = (): string => {
  return envConfig.apiPrefix || "/api/v1";
};

/**
 * Runtime-aware base API URLs
 */
export const BASE_URL_API = `${getBackendUrl()}${getApiPrefix()}/`;
export const BASE_URL_API_V2 = `${getBackendUrl()}/api/v2/`;

/**
 * WebSocket URL (if configured)
 */
export const getWebSocketUrl = (): string | undefined => {
  if (envConfig.websocketUrl) {
    return envConfig.websocketUrl;
  }

  // Derive WebSocket URL from backend URL if not explicitly set
  const backendUrl = getBackendUrl();
  if (backendUrl) {
    return backendUrl.replace(/^http/, "ws");
  }

  return undefined;
};

/**
 * Application configuration from environment
 */
export const APP_CONFIG = {
  title: envConfig.appTitle || "AI Studio",
  buildVersion: envConfig.buildVersion || "development",
  debugMode: envConfig.debugMode || false,
  logLevel: envConfig.logLevel || "info",
} as const;

/**
 * Feature flags from environment
 */
export const FEATURE_FLAGS = {
  enableChat: envConfig.enableChat ?? true,
  enableAgentBuilder: envConfig.enableAgentBuilder ?? true,
  enableHealthcareComponents: envConfig.enableHealthcareComponents ?? true,
} as const;

/**
 * Advanced configuration
 */
export const ADVANCED_CONFIG = {
  maxFileSize: envConfig.maxFileSize,
  timeout: envConfig.timeout ? parseInt(envConfig.timeout, 10) : undefined,
} as const;