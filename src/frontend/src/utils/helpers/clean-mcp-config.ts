/**
 * Configuration object for MCP server that may contain sensitive data
 */
export type MCPServerConfig = {
  command?: string;
  url?: string;
  args?: string[];
  env?: Record<string, string>;
  headers?: Record<string, string>;
  api_key?: string;
  apiKey?: string;
  token?: string;
  access_token?: string;
  authorization?: string;
  [key: string]: unknown;
};

/**
 * MCP server value object containing name and config
 */
export type MCPServerValue = {
  name: string;
  config?: MCPServerConfig;
  [key: string]: unknown;
};

/**
 * Cleans sensitive data from MCP (Model Context Protocol) server configuration.
 *
 * This function removes sensitive authentication data that should not be exported,
 * including:
 * - Headers (may contain API keys, authorization tokens)
 * - Environment variables (may contain secrets)
 * - Command arguments (may contain sensitive parameters)
 * - API keys, tokens, and authorization fields
 *
 * @param mcpValue - The MCP server configuration object
 * @returns The cleaned configuration with sensitive data removed
 */
export function cleanMcpConfig(mcpValue: MCPServerValue): MCPServerValue {
  // If no config object exists, return as-is
  if (!mcpValue?.config || typeof mcpValue.config !== "object") {
    return mcpValue;
  }

  const config = mcpValue.config;

  // Remove headers that may contain API keys or auth tokens
  if (config.headers) {
    config.headers = {};
  }

  // Remove environment variables that may contain secrets
  if (config.env) {
    config.env = {};
  }

  // Clear command arguments that may contain sensitive data
  // Keep the command structure but clear args array
  if (config.args && Array.isArray(config.args)) {
    config.args = [];
  }

  // Clear any API key fields
  if (config.api_key || config.apiKey) {
    delete config.api_key;
    delete config.apiKey;
  }

  // Clear authorization fields
  if (config.authorization) {
    delete config.authorization;
  }

  // Clear token fields
  if (config.token || config.access_token) {
    delete config.token;
    delete config.access_token;
  }

  return mcpValue;
}
