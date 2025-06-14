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
  id: string;
  name: string;
  description: string;
  toolsCount: number;
  protocolVersion?: string;
  transportType?: string;
  capabilities?: Record<string, any>;
  serverInfo?: {
    name?: string;
    version?: string;
  };
  lastChecked?: string;
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
