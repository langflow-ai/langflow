import { api } from "@/controllers/API/api";

export const customGetMCPUrl = (
  projectId: string,
  useComposer = false,
  composerUrl?: string,
) => {
  if (useComposer && composerUrl) {
    // Use the per-project MCP Composer SSE URL
    return composerUrl;
  }

  // Fallback to direct Langflow SSE endpoint
  const apiHost = api.defaults.baseURL || window.location.origin;
  const apiUrl = `${apiHost}/api/v1/mcp/project/${projectId}/sse`;
  return apiUrl;
};
