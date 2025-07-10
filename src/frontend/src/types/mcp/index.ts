export type MCPSettingsType = {
  id: string;
  mcp_enabled: boolean;
  action_name?: string;
  action_description?: string;
  name?: string;
  description?: string;
  input_schema?: Record<string, any>;
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
