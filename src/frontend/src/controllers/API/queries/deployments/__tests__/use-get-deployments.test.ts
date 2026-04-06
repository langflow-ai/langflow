const mockApiGet = jest.fn();

// Mock query that properly resolves data via async execution
const mockQuery = jest.fn(
  (_key: unknown, fn: () => Promise<unknown>, _options?: unknown) => {
    // biome-ignore lint/suspicious/noExplicitAny: test mock
    const result: { data: any; isLoading: boolean; error: unknown } = {
      data: null,
      isLoading: false,
      error: null,
    };
    void fn().then((data) => {
      result.data = data;
    });
    return result;
  },
);

jest.mock("@/controllers/API/api", () => ({
  api: { get: mockApiGet },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/deployments"),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({ query: mockQuery })),
}));

import { useGetDeployments } from "../use-get-deployments";

const flushPromises = () =>
  new Promise((r) => jest.requireActual("timers").setImmediate(r));

describe("useGetDeployments", () => {
  beforeEach(() => jest.clearAllMocks());

  it("calls API with provider_id and default pagination", async () => {
    mockApiGet.mockResolvedValue({
      data: { deployments: [], page: 1, size: 20, total: 0 },
    });

    useGetDeployments({ provider_id: "prov-1" });
    await flushPromises();

    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/deployments", {
      params: {
        provider_id: "prov-1",
        flow_ids: undefined,
        page: 1,
        size: 20,
      },
    });
  });

  it("forwards flow_ids and custom pagination", async () => {
    mockApiGet.mockResolvedValue({
      data: { deployments: [], page: 2, size: 10, total: 50 },
    });

    useGetDeployments({
      provider_id: "prov-1",
      flow_ids: "f1,f2",
      page: 2,
      size: 10,
    });
    await flushPromises();

    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/deployments", {
      params: { provider_id: "prov-1", flow_ids: "f1,f2", page: 2, size: 10 },
    });
  });

  it("uses correct query key with all params", () => {
    mockApiGet.mockResolvedValue({ data: { deployments: [] } });

    useGetDeployments({
      provider_id: "prov-1",
      flow_ids: "f1",
      page: 3,
      size: 5,
    });

    expect(mockQuery).toHaveBeenCalledWith(
      [
        "useGetDeployments",
        { provider_id: "prov-1", flow_ids: "f1", page: 3, size: 5 },
      ],
      expect.any(Function),
      undefined,
    );
  });

  it("returns deployment data from API response", async () => {
    const responseData = {
      deployments: [{ id: "d1", name: "Agent 1" }],
      page: 1,
      size: 20,
      total: 1,
    };
    mockApiGet.mockResolvedValue({ data: responseData });

    const result = useGetDeployments({ provider_id: "prov-1" });
    await flushPromises();

    expect(result.data).toBeDefined();
    if (!result.data) return;
    expect(result.data).toEqual(responseData);
    expect(result.data.deployments).toHaveLength(1);
    expect(result.data.deployments[0].id).toBe("d1");
  });
});
