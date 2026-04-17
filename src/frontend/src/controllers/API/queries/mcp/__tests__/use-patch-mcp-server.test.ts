const mockApiPatch = jest.fn();
const mockQueryClient = {
  setQueryData: jest.fn(),
  invalidateQueries: jest.fn(),
};

type MutationOptions<TData, TVariables> = {
  onSuccess?: (data: TData, variables: TVariables, context: undefined) => void;
  onSettled?: (data: TData) => void;
};

type MutationFn<TVariables, TData> = (payload: TVariables) => Promise<TData>;

jest.mock("@/controllers/API/api", () => ({
  api: { patch: mockApiPatch },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v2/mcp/servers"),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    mutate: jest.fn(
      <TVariables, TData>(
        _key: unknown,
        fn: MutationFn<TVariables, TData>,
        options: MutationOptions<TData, TVariables>,
      ) => ({
        mutate: async (payload: TVariables) => {
          const result = await fn(payload);
          options?.onSuccess?.(result, payload, undefined);
          options?.onSettled?.(result);
          return result;
        },
      }),
    ),
    queryClient: mockQueryClient,
  })),
}));

import { usePatchMCPServer } from "../use-patch-mcp-server";

describe("usePatchMCPServer", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("preserves explicit empty collections in patch payload", async () => {
    mockApiPatch.mockResolvedValue({ data: {} });

    const mutation = usePatchMCPServer();
    await mutation.mutate({
      name: "my-server",
      url: "http://host/sse",
      headers: {},
      env: {},
      args: [],
    });

    expect(mockApiPatch).toHaveBeenCalledWith("/api/v2/mcp/servers/my-server", {
      url: "http://host/sse",
      headers: {},
      env: {},
      args: [],
    });
  });

  it("updates cached server list and invalidates MCP queries on success", async () => {
    mockApiPatch.mockResolvedValue({ data: {} });

    const mutation = usePatchMCPServer();
    await mutation.mutate({
      name: "my-server",
      url: "http://host/sse",
    });

    expect(mockQueryClient.setQueryData).toHaveBeenCalledWith(
      ["useGetMCPServers"],
      expect.any(Function),
    );
    expect(mockQueryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetMCPServers"],
    });
    expect(mockQueryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetMCPServer", undefined],
    });
  });
});
