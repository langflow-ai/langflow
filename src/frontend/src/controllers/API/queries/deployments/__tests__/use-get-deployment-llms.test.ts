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

import { useGetDeploymentLlms } from "../use-get-deployment-llms";

const flushPromises = () =>
  new Promise((r) => jest.requireActual("timers").setImmediate(r));

describe("useGetDeploymentLlms", () => {
  beforeEach(() => jest.clearAllMocks());

  it("calls API with provider_id", async () => {
    mockApiGet.mockResolvedValue({
      data: { provider_data: { models: [] } },
    });

    useGetDeploymentLlms({ providerId: "prov-1" });
    await flushPromises();

    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/deployments/llms", {
      params: { provider_id: "prov-1" },
    });
  });

  it("uses correct query key", () => {
    mockApiGet.mockResolvedValue({ data: { provider_data: null } });

    useGetDeploymentLlms({ providerId: "prov-1" });

    expect(mockQuery).toHaveBeenCalledWith(
      ["useGetDeploymentLlms", { providerId: "prov-1" }],
      expect.any(Function),
      undefined,
    );
  });

  it("returns LLM model list from provider_data", async () => {
    const responseData = {
      provider_data: {
        models: [
          { model_name: "ibm/granite-3-8b-instruct" },
          { model_name: "meta-llama/llama-3-70b-instruct" },
        ],
      },
    };
    mockApiGet.mockResolvedValue({ data: responseData });

    const result = useGetDeploymentLlms({ providerId: "prov-1" });
    await flushPromises();

    expect(result.data).toBeDefined();
    if (!result.data) return;
    expect(result.data).toEqual(responseData);
    expect(result.data.provider_data).toBeDefined();
    if (!result.data.provider_data) return;
    expect(result.data.provider_data.models).toHaveLength(2);
    expect(result.data.provider_data.models[0].model_name).toBe(
      "ibm/granite-3-8b-instruct",
    );
  });

  it("handles null provider_data", async () => {
    mockApiGet.mockResolvedValue({ data: { provider_data: null } });

    const result = useGetDeploymentLlms({ providerId: "prov-1" });
    await flushPromises();

    expect(result.data).toBeDefined();
    if (!result.data) return;
    expect(result.data).toEqual({ provider_data: null });
    expect(result.data.provider_data).toBeNull();
  });
});
