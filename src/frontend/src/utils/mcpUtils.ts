import { MCPServerType } from "@/types/mcp";

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
