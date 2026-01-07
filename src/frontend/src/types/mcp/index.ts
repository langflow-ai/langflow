export type AuthSettingsType = {
  auth_type: string;
  oauth_host?: string;
  oauth_port?: string;
  oauth_server_url?: string;
  oauth_callback_path?: string; // Deprecated: use oauth_callback_url instead
  oauth_callback_url?: string;
  oauth_client_id?: string;
  oauth_client_secret?: string;
  oauth_auth_url?: string;
  oauth_token_url?: string;
  oauth_mcp_scope?: string;
  oauth_provider_scope?: string;
};

export type MCPSettingsType = {
  id: string;
  mcp_enabled: boolean;
  action_name?: string;
  action_description?: string;
  name?: string;
  description?: string;
  input_schema?: Record<string, any>;
};

export type MCPProjectResponseType = {
  tools: MCPSettingsType[];
  auth_settings?: AuthSettingsType;
};

export type MCPServerInfoType = {
  id?: string;
  name: string;
  description?: string;
  mode: string | null;
  toolsCount: number | null;
  error?: string;
};

export type MCPServerType = {
  name: string;
  command?: string;
  url?: string;
  args?: string[];
  env?: Record<string, string>;
  headers?: Record<string, string>;
};

export type ComposerUrlResponseType = {
  project_id: string;
  uses_composer: boolean;
  streamable_http_url?: string;
  legacy_sse_url?: string;
  sse_url?: string;
  error_message?: string;
};
