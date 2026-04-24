import { api } from "@/controllers/API/api";
import type { MCPTransport } from "@/controllers/API/queries/mcp/use-patch-install-mcp";
import { useUtilityStore } from "@/stores/utilityStore";

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

  const configBaseUrl = useUtilityStore.getState().mcpBaseUrl;
  const apiHost = (
    configBaseUrl ||
    api.defaults.baseURL ||
    window.location.origin
  ).replace(/\/+$/, "");
  const baseUrl = `${apiHost}/api/v1/mcp/project/${projectId}`;
  return transport === "streamablehttp"
    ? `${baseUrl}/streamable`
    : `${baseUrl}/sse`;
};
