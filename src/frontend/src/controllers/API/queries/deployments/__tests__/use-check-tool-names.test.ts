const mockApiGet = jest.fn();

// biome-ignore lint/suspicious/noExplicitAny: test mock — captures the query fn so we can invoke and assert its return value
let capturedQueryFn: (() => Promise<any>) | null = null;

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
      capturedQueryFn = fn;
      return { data: undefined, isLoading: true };
    }),
  })),
}));

import { useCheckToolNames } from "../use-check-tool-names";

describe("useCheckToolNames", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    capturedQueryFn = null;
  });

  // ---------------------------------------------------------------------------
  // URL & params
  // ---------------------------------------------------------------------------

  it("calls snapshots endpoint with provider_id, names, and size", () => {
    mockApiGet.mockResolvedValue({
      data: { provider_data: { tools: [], total: 0 } },
    });

    useCheckToolNames(
      { providerId: "prov-1", names: ["my_tool", "other_tool"] },
      {},
    );

    // Invoke the captured query function so it hits the mock API
    expect(capturedQueryFn).not.toBeNull();
    capturedQueryFn!();

    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/deployments/snapshots", {
      params: {
        provider_id: "prov-1",
        names: ["my_tool", "other_tool"],
        size: 50,
      },
      paramsSerializer: { indexes: null },
    });
  });

  it("does not hit the old check-names endpoint", () => {
    mockApiGet.mockResolvedValue({
      data: { provider_data: { tools: [] } },
    });

    useCheckToolNames({ providerId: "prov-1", names: ["test"] }, {});
    capturedQueryFn!();

    const calledUrl = mockApiGet.mock.calls[0][0];
    expect(calledUrl).not.toContain("check-names");
    expect(calledUrl).toBe("/api/v1/deployments/snapshots");
  });

  // ---------------------------------------------------------------------------
  // Data transformation — the actual logic under test
  // ---------------------------------------------------------------------------

  it("extracts tool names from snapshot response into existing_names", async () => {
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

    useCheckToolNames(
      { providerId: "prov-1", names: ["my_tool", "another_tool"] },
      {},
    );

    const result = await capturedQueryFn!();
    expect(result).toEqual({
      existing_names: ["my_tool", "another_tool"],
    });
  });

  it("returns empty existing_names when provider_data has no tools key", async () => {
    mockApiGet.mockResolvedValue({
      data: { provider_data: {} },
    });

    useCheckToolNames({ providerId: "prov-1", names: ["nonexistent"] }, {});

    const result = await capturedQueryFn!();
    expect(result).toEqual({ existing_names: [] });
  });

  it("returns empty existing_names when tools array is empty", async () => {
    mockApiGet.mockResolvedValue({
      data: { provider_data: { tools: [], total: 0 } },
    });

    useCheckToolNames({ providerId: "prov-1", names: ["anything"] }, {});

    const result = await capturedQueryFn!();
    expect(result).toEqual({ existing_names: [] });
  });

  it("filters out tools with falsy name values", async () => {
    mockApiGet.mockResolvedValue({
      data: {
        provider_data: {
          tools: [
            { id: "t-1", name: "valid_tool" },
            { id: "t-2", name: "" },
            { id: "t-3", name: "another_valid" },
          ],
          total: 3,
        },
      },
    });

    useCheckToolNames(
      { providerId: "prov-1", names: ["valid_tool", "another_valid"] },
      {},
    );

    const result = await capturedQueryFn!();
    expect(result).toEqual({
      existing_names: ["valid_tool", "another_valid"],
    });
  });

  it("returns empty existing_names when provider_data is undefined", async () => {
    mockApiGet.mockResolvedValue({
      data: {},
    });

    useCheckToolNames({ providerId: "prov-1", names: ["test"] }, {});

    const result = await capturedQueryFn!();
    expect(result).toEqual({ existing_names: [] });
  });
});
