import { MCPServerType } from "@/types/mcp";

export enum AuthMethodId {
  NONE = "none",
  API_KEY = "apikey",
  BASIC = "basic",
  BEARER = "bearer",
  IAM = "iam",
}

export const AUTH_METHODS = {
  [AuthMethodId.NONE]: { id: AuthMethodId.NONE, label: "None" },
  [AuthMethodId.API_KEY]: { id: AuthMethodId.API_KEY, label: "API Key" },
  [AuthMethodId.BASIC]: {
    id: AuthMethodId.BASIC,
    label: "Basic",
  },
  [AuthMethodId.BEARER]: { id: AuthMethodId.BEARER, label: "Bearer Token" },
  [AuthMethodId.IAM]: { id: AuthMethodId.IAM, label: "IAM" },
} as const;

export const AUTH_METHODS_ARRAY = Object.values(AUTH_METHODS);

/**
 * Extracts all MCP servers from a JSON string or object.
 * Supports:
 * 1. { mcpServers: { ... } }
 * 2. { ... } (object with server keys)
 * 3. a single server object
 * Returns: Array<MCPServerType> or throws an error.
 */
export function extractMcpServersFromJson(
  json: string | object,
): MCPServerType[] {
  let parsed: any = json;
  if (typeof json === "string") {
    try {
      parsed = JSON.parse(json);
    } catch (_e) {
      try {
        parsed = JSON.parse(`{${json}}`);
      } catch (_e) {
        throw new Error("Invalid JSON format.");
      }
    }
  }

  let serverEntries: [string, any][] = [];

  // Case 1: { mcpServers: { ... } }
  if (
    parsed &&
    typeof parsed === "object" &&
    parsed.mcpServers &&
    typeof parsed.mcpServers === "object"
  ) {
    serverEntries = Object.entries(parsed.mcpServers);
  }
  // Case 2: { ... } (object with server keys)
  else if (
    parsed &&
    typeof parsed === "object" &&
    Object.values(parsed).some(
      (v) => v && typeof v === "object" && ("command" in v || "url" in v),
    )
  ) {
    serverEntries = Object.entries(parsed).filter(
      ([, v]) => v && typeof v === "object" && ("command" in v || "url" in v),
    );
  }
  // Case 3: single server object
  else if (
    parsed &&
    typeof parsed === "object" &&
    ("command" in parsed || "url" in parsed)
  ) {
    serverEntries = [["server", parsed]];
  }

  if (serverEntries.length === 0) {
    throw new Error("No valid MCP server found in the input.");
  }
  // Validate and map all servers
  const validServers = serverEntries.filter(
    ([, server]) => server.command || server.url,
  );
  if (validServers.length === 0) {
    throw new Error("No valid MCP server found in the input.");
  }
  return validServers.map(([name, server]) => ({
    name: name.slice(0, 30),
    command: server.command,
    args: server.args || [],
    env: server.env && typeof server.env === "object" ? server.env : {},
    url: server.url,
  }));
}
