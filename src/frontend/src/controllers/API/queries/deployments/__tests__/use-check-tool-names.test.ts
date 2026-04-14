const mockApiGet = jest.fn();
const mockQueryClient = {
  refetchQueries: jest.fn(),
  invalidateQueries: jest.fn(),
};

jest.mock("@/controllers/API/api", () => ({
  api: { get: mockApiGet },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/deployments"),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    // biome-ignore lint/suspicious/noExplicitAny: test mock
    query: jest.fn((_key: any, fn: any, _options: any) => {
      // Immediately invoke the query function for testing
      fn();
      return { data: undefined, isLoading: true };
    }),
    queryClient: mockQueryClient,
  })),
}));

import { useCheckToolNames } from "../use-check-tool-names";

describe("useCheckToolNames", () => {
  beforeEach(() => jest.clearAllMocks());

  it("calls snapshots endpoint with names param", () => {
    mockApiGet.mockResolvedValue({
      data: {
        provider_data: {
          tools: [{ id: "tool-1", name: "my_tool" }],
          total: 1,
        },
      },
    });

    useCheckToolNames(
      { providerId: "prov-1", names: ["my_tool", "other_tool"] },
      {},
    );

    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/deployments/snapshots", {
      params: {
        provider_id: "prov-1",
        names: ["my_tool", "other_tool"],
        size: 50,
      },
      paramsSerializer: { indexes: null },
    });
  });

  it("extracts tool names from snapshot list response", async () => {
    mockApiGet.mockResolvedValue({
      data: {
        provider_data: {
          tools: [
            { id: "tool-1", name: "my_tool" },
            { id: "tool-2", name: "another_tool" },
          ],
          total: 2,
        },
      },
    });

    // Call the hook to trigger the query function
    useCheckToolNames(
      { providerId: "prov-1", names: ["my_tool", "another_tool"] },
      {},
    );

    // Wait for the async fn to resolve
    await new Promise(process.nextTick);

    // Verify the API was called with correct endpoint
    expect(mockApiGet).toHaveBeenCalledWith(
      "/api/v1/deployments/snapshots",
      expect.objectContaining({
        params: expect.objectContaining({
          names: ["my_tool", "another_tool"],
        }),
      }),
    );
  });

  it("returns empty existing_names when provider_data has no tools", async () => {
    mockApiGet.mockResolvedValue({
      data: { provider_data: {} },
    });

    useCheckToolNames({ providerId: "prov-1", names: ["nonexistent"] }, {});

    await new Promise(process.nextTick);

    expect(mockApiGet).toHaveBeenCalledWith(
      "/api/v1/deployments/snapshots",
      expect.objectContaining({
        params: expect.objectContaining({
          names: ["nonexistent"],
        }),
      }),
    );
  });

  it("does not call old check-names endpoint", () => {
    mockApiGet.mockResolvedValue({
      data: { provider_data: { tools: [] } },
    });

    useCheckToolNames({ providerId: "prov-1", names: ["test"] }, {});

    const calledUrl = mockApiGet.mock.calls[0][0];
    expect(calledUrl).not.toContain("check-names");
    expect(calledUrl).toBe("/api/v1/deployments/snapshots");
  });
});
