import type { useQueryFunctionType } from "@/types/api";
import type { MCPServerInfoType } from "@/types/mcp";
import { useEffect } from "react";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

// This type is now updated to allow nulls for mode/toolsCount
// type getMCPServersResponse = Array<MCPServerInfoType>;

type getMCPServersResponse = Array<MCPServerInfoType>;

export const useGetMCPServers: useQueryFunctionType<
  undefined,
  getMCPServersResponse
> = (options) => {
  const { query, queryClient } = UseRequestProcessor();

  // First fetch: action_count=false (fast)
  const responseFn = async () => {
    try {
      const { data } = await api.get<getMCPServersResponse>(
        `${getURL("MCP_SERVERS", undefined, true)}?action_count=false`,
      );
      // Merge with cached data to preserve non-null mode/toolsCount
      const cachedData = queryClient.getQueryData(["useGetMCPServers"]) as
        | getMCPServersResponse
        | undefined;
      if (cachedData && Array.isArray(cachedData)) {
        const merged = data.map((server) => {
          const cached = cachedData.find((s) => s.name === server.name);
          return cached &&
            (cached.toolsCount !== null ||
              cached.mode !== null ||
              cached.error !== null)
            ? {
                ...server,
                toolsCount: cached.toolsCount,
                mode: cached.mode,
                error: cached.error,
              }
            : server;
        });
        return merged;
      }
      return data;
    } catch (error) {
      console.error(error);
      return [];
    }
  };

  // Second fetch: action_count=true (slow, updates mode/toolsCount)
  const fetchWithCounts = async () => {
    try {
      const { data } = await api.get<getMCPServersResponse>(
        `${getURL("MCP_SERVERS", undefined, true)}?action_count=true`,
      );
      return data;
    } catch (error) {
      console.error(error);
      return [];
    }
  };

  const queryResult = query(["useGetMCPServers"], responseFn, {
    ...options,
  });

  useEffect(() => {
    if (queryResult.data && queryResult.data.length > 0) {
      fetchWithCounts().then((countsData) => {
        if (!countsData || countsData.length === 0) return;
        // Merge by name
        queryClient.setQueryData(
          ["useGetMCPServers"],
          (oldData: getMCPServersResponse = []) => {
            return oldData.map((server) => {
              const updated = countsData.find((s) => s.name === server.name);
              return updated ? { ...server, ...updated } : server;
            });
          },
        );
      });
    }
  }, [queryResult.data]);

  return queryResult;
};
