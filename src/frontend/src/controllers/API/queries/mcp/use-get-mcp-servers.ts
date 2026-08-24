import { useCallback, useEffect } from "react";
import type { useQueryFunctionType } from "@/types/api";
import type { MCPServerInfoType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

// This type is now updated to allow nulls for mode/toolsCount
// type getMCPServersResponse = Array<MCPServerInfoType>;

export type getMCPServersResponse = Array<MCPServerInfoType>;

export const mergeMCPServerCounts = (
  oldData: getMCPServersResponse = [],
  countsData: getMCPServersResponse,
): getMCPServersResponse =>
  oldData.map((server) => {
    const updated = countsData.find((s) => s.name === server.name);
    if (!updated) return server;

    return {
      ...server,
      ...updated,
      error: updated.error ?? undefined,
    };
  });

export const useGetMCPServers: useQueryFunctionType<
  undefined,
  getMCPServersResponse,
  { withCounts?: boolean }
> = (options) => {
  const { query, queryClient } = UseRequestProcessor();
  const { withCounts, ...queryOptions } = options ?? {};

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
    ...queryOptions,
  });

  const serverNames = JSON.stringify(
    (queryResult.data ?? []).map((server) => server.name).sort(),
  );
  const countsQuery = query(
    ["useGetMCPServerCounts", serverNames],
    fetchWithCounts,
    {
      enabled: Boolean(withCounts && queryResult.data?.length),
    },
  );

  useEffect(() => {
    const countsData = countsQuery.data as getMCPServersResponse | undefined;
    if (!withCounts || !countsData?.length) return;

    queryClient.setQueryData(
      ["useGetMCPServers"],
      (oldData: getMCPServersResponse = []) =>
        mergeMCPServerCounts(oldData, countsData),
    );
  }, [withCounts, countsQuery.data, queryClient]);

  const refetch = useCallback(
    async (...args: Parameters<typeof queryResult.refetch>) => {
      const result = await queryResult.refetch(...args);
      const refreshedServerNames = JSON.stringify(
        (result.data ?? []).map((server) => server.name).sort(),
      );
      if (
        withCounts &&
        result.data?.length &&
        refreshedServerNames === serverNames
      ) {
        await countsQuery.refetch();
      }
      return result;
    },
    [countsQuery.refetch, queryResult.refetch, serverNames, withCounts],
  );

  return { ...queryResult, refetch };
};
