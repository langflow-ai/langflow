import { renderHook } from "@testing-library/react";
import { useGetDeploymentAttachments } from "@/controllers/API/queries/deployments/use-get-deployment-attachments";

const mockGet = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: {
    get: (...args: unknown[]) => mockGet(...args),
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => {
    if (key === "DEPLOYMENTS") return "/api/v1/deployments";
    return `/${key}`;
  },
}));

const mockQueryFn = jest.fn();
jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: () => ({
    query: (
      queryKey: string[],
      fn: () => Promise<unknown>,
      options?: Record<string, unknown>,
    ) => {
      mockQueryFn(queryKey, fn, options);
      return { data: null, isLoading: false };
    },
    queryClient: { refetchQueries: jest.fn() },
  }),
}));

describe("useGetDeploymentAttachments", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("registers a query with the correct key", () => {
    renderHook(() => useGetDeploymentAttachments({ deploymentId: "deploy-1" }));

    expect(mockQueryFn).toHaveBeenCalledWith(
      ["useGetDeploymentAttachments", { deploymentId: "deploy-1" }],
      expect.any(Function),
      undefined,
    );
  });

  it("calls the correct URL when the query fn executes", async () => {
    mockGet.mockResolvedValue({
      data: {
        attachments: [
          {
            flow_version_id: "fv-1",
            flow_id: "flow-1",
            flow_name: "My Flow",
            version_tag: "v3",
            provider_snapshot_id: "tool-abc",
            connection_ids: ["conn-1", "conn-2"],
            created_at: "2025-01-01T00:00:00Z",
          },
        ],
      },
    });

    renderHook(() => useGetDeploymentAttachments({ deploymentId: "deploy-1" }));

    // Execute the query function that was registered
    const queryFn = mockQueryFn.mock.calls[0][1];
    const result = await queryFn();

    expect(mockGet).toHaveBeenCalledWith(
      "/api/v1/deployments/deploy-1/attachments",
    );
    expect(result.attachments).toHaveLength(1);
    expect(result.attachments[0].connection_ids).toEqual(["conn-1", "conn-2"]);
    expect(result.attachments[0].flow_name).toBe("My Flow");
  });
});
