import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import React from "react";

const mockApiGet = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: {
    get: mockApiGet,
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v2/mcp/servers"),
}));

import { mergeMCPServerCounts, useGetMCPServers } from "../use-get-mcp-servers";

describe("mergeMCPServerCounts", () => {
  it("clears a cached error when refreshed counts omit an error", () => {
    const merged = mergeMCPServerCounts(
      [
        {
          name: "server",
          mode: null,
          toolsCount: null,
          error: "Connection refused",
        },
      ],
      [
        {
          name: "server",
          mode: "streamable_http",
          toolsCount: 2,
        },
      ],
    );

    expect(merged).toEqual([
      {
        name: "server",
        mode: "streamable_http",
        toolsCount: 2,
        error: undefined,
      },
    ]);
  });
});

describe("useGetMCPServers", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    jest.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
  });

  afterEach(() => {
    queryClient.clear();
  });

  it("fetches counts once without retriggering from its own cache update", async () => {
    let toolsCount = 2;
    let servers = [{ name: "server", mode: null, toolsCount: null }];
    mockApiGet.mockImplementation((url: string) =>
      Promise.resolve({
        data: url.endsWith("action_count=true")
          ? servers.map((server) => ({
              ...server,
              mode: "stdio",
              toolsCount,
            }))
          : servers,
      }),
    );

    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(
        QueryClientProvider,
        { client: queryClient },
        children,
      );
    const { result } = renderHook(
      () => useGetMCPServers({ withCounts: true }),
      { wrapper },
    );

    await waitFor(() => {
      expect(result.current.data?.[0]).toMatchObject({
        name: "server",
        mode: "stdio",
        toolsCount: 2,
      });
    });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(
      mockApiGet.mock.calls.filter(([url]) =>
        String(url).endsWith("action_count=true"),
      ),
    ).toHaveLength(1);

    toolsCount = 3;
    await act(async () => {
      await result.current.refetch();
    });

    await waitFor(() => {
      expect(result.current.data?.[0]?.toolsCount).toBe(3);
    });
    expect(
      mockApiGet.mock.calls.filter(([url]) =>
        String(url).endsWith("action_count=true"),
      ),
    ).toHaveLength(2);

    servers = [
      { name: "server", mode: null, toolsCount: null },
      { name: "new-server", mode: null, toolsCount: null },
    ];
    await act(async () => {
      await queryClient.invalidateQueries({
        queryKey: ["useGetMCPServers"],
      });
    });

    await waitFor(() => {
      expect(result.current.data).toHaveLength(2);
      expect(result.current.data?.[1]).toMatchObject({
        name: "new-server",
        mode: "stdio",
        toolsCount: 3,
      });
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(
      mockApiGet.mock.calls.filter(([url]) =>
        String(url).endsWith("action_count=true"),
      ),
    ).toHaveLength(3);
  });
});
