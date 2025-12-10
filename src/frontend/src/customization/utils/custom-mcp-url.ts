import type { MCPTransport } from "@/controllers/API/queries/mcp/use-patch-install-mcp";
import { api } from "@/controllers/API/api";

type ComposerConnectionOptions = {
  useComposer?: boolean;
  streamableHttpUrl?: string;
  legacySseUrl?: string;
};

export const customGetMCPUrl = (
  projectId: string,
  options: ComposerConnectionOptions = {},
  transport: MCPTransport = "streamablehttp",
) => {
  const { useComposer, streamableHttpUrl, legacySseUrl } = options;

  if (useComposer) {
    if (transport === "streamablehttp" && streamableHttpUrl) {
      return streamableHttpUrl;
    }
    if (legacySseUrl) {
      return legacySseUrl;
    }
    if (streamableHttpUrl) {
      return streamableHttpUrl;
    }
  }

  const apiHost = api.defaults.baseURL || window.location.origin;
  const baseUrl = `${apiHost}/api/v1/mcp/project/${projectId}`;
  return transport === "streamablehttp"
    ? `${baseUrl}/streamable`
    : `${baseUrl}/sse`;
};
