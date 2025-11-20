import { z } from "zod";
import { validator } from "./validation.env";

/**
 * AI Studio Environment Configuration Schema
 *
 * Adding new environment variables:
 * 1. Add the variable to envSchema with appropriate validation
 * 2. The EnvConfig interface will be automatically inferred
 * 3. Always prefix with 'VITE_' for client-side access
 *
 * Example:
 * VITE_NEW_API_URL: validator.url(),
 * VITE_OPTIONAL_FEATURE: validator.optionalBoolean(),
 */

/**
 * Zod schema for AI Studio environment validation
 */
export const envSchema = z.object({
  // Backend API Configuration
  VITE_BACKEND_URL: validator.url(),
  VITE_API_PREFIX: validator.string().default("/api/v1"),

  // Proxy Configuration (Development)
  VITE_PROXY_TARGET: validator.optionalUrl(),
  VITE_PORT: validator.optionalString(),

  // Application Configuration
  VITE_APP_TITLE: validator.string().default("AI Studio"),
  VITE_BUILD_VERSION: validator.optionalString(),

  // Feature Flags
  VITE_ENABLE_CHAT: validator.boolean().default(true),
  VITE_ENABLE_AGENT_BUILDER: validator.boolean().default(true),
  VITE_ENABLE_HEALTHCARE_COMPONENTS: validator.boolean().default(true),

  // Development/Debug Configuration
  VITE_DEBUG_MODE: validator.optionalBoolean(),
  VITE_LOG_LEVEL: validator.logLevel(),

  // Optional Advanced Configuration
  VITE_WEBSOCKET_URL: validator.optionalUrl(),
  VITE_MAX_FILE_SIZE: validator.optionalString(),
  VITE_TIMEOUT: validator.optionalString(),

  // Keycloak Authentication Configuration
  VITE_KEYCLOAK_URL: validator.optionalUrl(),
  VITE_KEYCLOAK_REALM: validator.optionalString(),
  VITE_KEYCLOAK_CLIENT_ID: validator.optionalString(),
  VITE_KEYCLOAK_ENABLED: validator.boolean().default(false),

  // External urls
  VITE_PROMPTS_URL: validator.optionalUrl(),
});

/**
 * Raw environment variables type inferred from Zod schema
 */
export type RawEnvConfig = z.infer<typeof envSchema>;

/**
 * Processed environment configuration with camelCase properties
 * This interface maps the validated environment variables to camelCase
 */
export interface EnvConfig {
  // Backend API Configuration
  backendUrl: string;
  apiPrefix: string;

  // Proxy Configuration (Development)
  proxyTarget?: string;
  port?: string;

  // Application Configuration
  appTitle: string;
  buildVersion?: string;

  // Feature Flags
  enableChat: boolean;
  enableAgentBuilder: boolean;
  enableHealthcareComponents: boolean;

  // Development/Debug Configuration
  debugMode?: boolean;
  logLevel: "debug" | "info" | "warn" | "error";

  // Optional Advanced Configuration
  websocketUrl?: string;
  maxFileSize?: string;
  timeout?: string;

  // Keycloak Authentication Configuration
  keycloakUrl?: string;
  keycloakRealm?: string;
  keycloakClientId?: string;
  keycloakEnabled: boolean;

  // External urls
  promptsUrl?: string | null;
}