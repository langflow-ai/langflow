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
    const responseData = {
      configs: [
        {
          id: "cfg-1",
          name: "my_connection",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: null,
          provider_data: { scheme: "key_value" },
        },
        {
          id: "cfg-2",
          name: "other_conn",
          created_at: "2026-01-02T00:00:00Z",
          updated_at: "2026-01-03T00:00:00Z",
          provider_data: null,
        },
      ],
      page: 1,
      size: 10000,
      total: 2,
    };
    mockApiGet.mockResolvedValue({ data: responseData });

    const result = useGetDeploymentConfigs({ providerId: "prov-1" });
    await flushPromises();

    expect(result.data).toBeDefined();
    if (!result.data) return;
    expect(result.data).toEqual(responseData);
    expect(result.data.configs).toHaveLength(2);
    expect(result.data.configs[0].name).toBe("my_connection");
    expect(result.data.configs[1].provider_data).toBeNull();
  });
});
