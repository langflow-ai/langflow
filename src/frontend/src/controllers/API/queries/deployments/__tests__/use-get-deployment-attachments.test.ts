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

import { useGetDeploymentAttachments } from "../use-get-deployment-attachments";

const flushPromises = () =>
  new Promise((r) => jest.requireActual("timers").setImmediate(r));

describe("useGetDeploymentAttachments", () => {
  beforeEach(() => jest.clearAllMocks());

  it("calls API with deployment ID and size=50", async () => {
    mockApiGet.mockResolvedValue({
      data: { flow_versions: [], page: 1, size: 50, total: 0 },
    });

    useGetDeploymentAttachments({ deploymentId: "dep-1" });
    await flushPromises();

    expect(mockApiGet).toHaveBeenCalledWith("/api/v1/deployments/dep-1/flows", {
      params: { size: 50 },
      paramsSerializer: { indexes: null },
    });
  });

  it("uses correct query key", () => {
    mockApiGet.mockResolvedValue({ data: { flow_versions: [] } });

    useGetDeploymentAttachments({ deploymentId: "dep-1" });

    expect(mockQuery).toHaveBeenCalledWith(
      ["useGetDeploymentAttachments", { deploymentId: "dep-1" }],
      expect.any(Function),
      undefined,
    );
  });

  it("returns flow versions with provider_snapshot_id and tool_name", async () => {
    const responseData = {
      flow_versions: [
        {
          id: "fv-1",
          flow_id: "f-1",
          flow_name: "My Flow",
          version_number: 1,
          attached_at: "2026-01-01T00:00:00Z",
          provider_snapshot_id: "tool-abc",
          tool_name: "my_flow_tool",
          provider_data: { app_ids: ["app-1"] },
        },
        {
          id: "fv-2",
          flow_id: "f-2",
          flow_name: "Other Flow",
          version_number: 3,
          attached_at: "2026-01-02T00:00:00Z",
          provider_snapshot_id: "tool-xyz",
          tool_name: null,
          provider_data: null,
        },
      ],
      page: 1,
      size: 50,
      total: 2,
    };
    mockApiGet.mockResolvedValue({ data: responseData });

    const result = useGetDeploymentAttachments({ deploymentId: "dep-1" });
    await flushPromises();

    expect(result.data).toBeDefined();
    if (!result.data) return;
    expect(result.data).toEqual(responseData);
    expect(result.data.flow_versions).toHaveLength(2);
    expect(result.data.flow_versions[0].provider_snapshot_id).toBe("tool-abc");
    expect(result.data.flow_versions[0].tool_name).toBe("my_flow_tool");
    expect(result.data.flow_versions[1].tool_name).toBeNull();
  });
});
