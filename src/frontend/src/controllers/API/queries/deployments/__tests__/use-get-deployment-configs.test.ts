const mockApiGet = jest.fn();
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

import { useGetDeploymentConfigs } from "../use-get-deployment-configs";

const flushPromises = () =>
  new Promise((r) => jest.requireActual("timers").setImmediate(r));

describe("useGetDeploymentConfigs", () => {
  beforeEach(() => jest.clearAllMocks());

  it("calls API with provider_id and size=10000", async () => {
    mockApiGet.mockResolvedValue({
      data: { configs: [], page: 1, size: 10000, total: 0 },
    });

    useGetDeploymentConfigs({ providerId: "prov-1" });
    await flushPromises();

    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/deployments/configs", {
      params: { provider_id: "prov-1", size: 10000 },
    });
  });

  it("uses correct query key", () => {
    mockApiGet.mockResolvedValue({ data: { configs: [] } });

    useGetDeploymentConfigs({ providerId: "prov-1" });

    expect(mockQuery).toHaveBeenCalledWith(
      ["useGetDeploymentConfigs", { providerId: "prov-1" }],
      expect.any(Function),
      undefined,
    );
  });

  it("returns config list with provider_data", async () => {
    const apiResponse = {
      provider_data: {
        connections: [
          { connection_id: "cfg-1", app_id: "app-1", type: "key_value" },
          { connection_id: "cfg-2", app_id: "app-2" },
        ],
        page: 1,
        size: 10000,
        total: 2,
      },
    };
    mockApiGet.mockResolvedValue({ data: apiResponse });

    const result = useGetDeploymentConfigs({ providerId: "prov-1" });
    await flushPromises();

    expect(result.data).toBeDefined();
    if (!result.data) return;
    expect(result.data.configs).toHaveLength(2);
    expect(result.data.configs[0].connection_id).toBe("cfg-1");
    expect(result.data.configs[1].connection_id).toBe("cfg-2");
    expect(result.data.page).toBe(1);
    expect(result.data.total).toBe(2);
  });
});
