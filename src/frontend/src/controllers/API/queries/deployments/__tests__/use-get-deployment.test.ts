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

import { useGetDeployment } from "../use-get-deployment";

const flushPromises = () =>
  new Promise((r) => jest.requireActual("timers").setImmediate(r));

describe("useGetDeployment", () => {
  beforeEach(() => jest.clearAllMocks());

  it("calls API with deployment ID in URL path", async () => {
    mockApiGet.mockResolvedValue({ data: { id: "dep-1", name: "Agent" } });

    useGetDeployment({ deploymentId: "dep-1" });
    await flushPromises();

    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/deployments/dep-1");
  });

  it("uses correct query key", () => {
    mockApiGet.mockResolvedValue({ data: {} });

    useGetDeployment({ deploymentId: "dep-42" });

    expect(mockQuery).toHaveBeenCalledWith(
      ["useGetDeployment", { deploymentId: "dep-42" }],
      expect.any(Function),
      undefined,
    );
  });

  it("returns deployment data from response", async () => {
    const deployment = {
      id: "dep-1",
      name: "Agent",
      type: "agent",
      resource_key: "rk-1",
      attached_count: 2,
    };
    mockApiGet.mockResolvedValue({ data: deployment });

    const result = useGetDeployment({ deploymentId: "dep-1" });
    await flushPromises();

    expect(result.data).toBeDefined();
    if (!result.data) return;
    expect(result.data).toEqual(deployment);
    expect(result.data.type).toBe("agent");
    expect(result.data.attached_count).toBe(2);
  });
});
