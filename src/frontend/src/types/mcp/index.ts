export type MCPSettingsType = {
  id: string;
  mcp_enabled: boolean;
  action_name?: string;
  action_description?: string;
  name?: string;
  description?: string;
  input_schema?: Record<string, any>;
};
