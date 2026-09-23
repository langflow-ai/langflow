import type { QueryClient } from "@tanstack/react-query";
import axios from "axios";

export class McpServerNotFoundError extends Error {
  constructor(readonly serverName: string) {
    super(`MCP server "${serverName}" not found`);
    this.name = "McpServerNotFoundError";
    // Error subclasses lose their prototype when compiled to ES5, breaking instanceof.
    Object.setPrototypeOf(this, McpServerNotFoundError.prototype);
  }
}

export function isNotFoundResponse(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 404;
}

export function refreshMcpServerList(queryClient: QueryClient): void {
  queryClient.invalidateQueries({ queryKey: ["useGetMCPServers"] });
  queryClient.invalidateQueries({ queryKey: ["useGetMCPServerCounts"] });
}
