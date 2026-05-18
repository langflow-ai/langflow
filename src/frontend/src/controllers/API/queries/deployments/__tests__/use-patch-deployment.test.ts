const mockApiPatch = jest.fn();
const mockQueryClient = {
  refetchQueries: jest.fn(),
  removeQueries: jest.fn(),
  invalidateQueries: jest.fn(),
};

jest.mock("@/controllers/API/api", () => ({
  api: { patch: mockApiPatch },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/deployments"),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    // biome-ignore lint/suspicious/noExplicitAny: test mock
    mutate: jest.fn((_key: any, fn: any, options: any) => ({
      // biome-ignore lint/suspicious/noExplicitAny: test mock
      mutate: async (payload: any) => {
        const result = await fn(payload);
        options?.onSuccess?.(result, payload, undefined);
        options?.onSettled?.(result);
        return result;
      },
    })),
    queryClient: mockQueryClient,
  })),
}));

import type { DeploymentUpdateRequest } from "../use-patch-deployment";
import { usePatchDeployment } from "../use-patch-deployment";

describe("usePatchDeployment", () => {
  beforeEach(() => jest.clearAllMocks());

  // ---------------------------------------------------------------------------
  // URL construction
  // ---------------------------------------------------------------------------

  it("patches the correct URL with deployment_id", async () => {
    mockApiPatch.mockResolvedValue({ data: {} });

    const mutation = usePatchDeployment();
    await mutation.mutate({
      deployment_id: "dep-42",
      name: "Updated Agent",
    });

    expect(mockApiPatch).toHaveBeenCalledWith(
      "/api/v1/deployments/dep-42",
      expect.any(Object),
    );
  });

  // ---------------------------------------------------------------------------
  // Body construction — deployment_id must be excluded
  // ---------------------------------------------------------------------------

  it("excludes deployment_id from the request body", async () => {
    mockApiPatch.mockResolvedValue({ data: {} });

    const mutation = usePatchDeployment();
    await mutation.mutate({
      deployment_id: "dep-1",
      name: "Renamed",
      description: "New description",
    });

    const sentBody = mockApiPatch.mock.calls[0][1];
    expect(sentBody).not.toHaveProperty("deployment_id");
    expect(sentBody).toEqual({
      name: "Renamed",
      description: "New description",
    });
  });

  it("sends only name when only name is provided", async () => {
    mockApiPatch.mockResolvedValue({ data: {} });

    const mutation = usePatchDeployment();
    await mutation.mutate({ deployment_id: "dep-1", name: "Solo Name" });

    const sentBody = mockApiPatch.mock.calls[0][1];
    expect(sentBody).toEqual({ name: "Solo Name" });
  });

  it("sends only description when only description is provided", async () => {
    mockApiPatch.mockResolvedValue({ data: {} });

    const mutation = usePatchDeployment();
    await mutation.mutate({
      deployment_id: "dep-1",
      description: "Solo desc",
    });

    const sentBody = mockApiPatch.mock.calls[0][1];
    expect(sentBody).toEqual({ description: "Solo desc" });
  });

  // ---------------------------------------------------------------------------
  // provider_data pass-through
  // ---------------------------------------------------------------------------

  it("forwards provider_data with upsert_flows", async () => {
    mockApiPatch.mockResolvedValue({ data: {} });

    const payload: DeploymentUpdateRequest = {
      deployment_id: "dep-1",
      provider_data: {
        llm: "gpt-4",
        upsert_flows: [
          {
            flow_version_id: "fv-1",
            add_app_ids: ["app-1"],
            remove_app_ids: [],
            tool_name: "my_tool",
          },
        ],
      },
    };

    const mutation = usePatchDeployment();
    await mutation.mutate(payload);

    const sentBody = mockApiPatch.mock.calls[0][1];
    expect(sentBody.provider_data.llm).toBe("gpt-4");
    expect(sentBody.provider_data.upsert_flows).toHaveLength(1);
    expect(sentBody.provider_data.upsert_flows[0]).toEqual({
      flow_version_id: "fv-1",
      add_app_ids: ["app-1"],
      remove_app_ids: [],
      tool_name: "my_tool",
    });
  });

  it("forwards provider_data with remove_flows", async () => {
    mockApiPatch.mockResolvedValue({ data: {} });

    const mutation = usePatchDeployment();
    await mutation.mutate({
      deployment_id: "dep-1",
      provider_data: {
        remove_flows: ["fv-old-1", "fv-old-2"],
      },
    });

    const sentBody = mockApiPatch.mock.calls[0][1];
    expect(sentBody.provider_data.remove_flows).toEqual([
      "fv-old-1",
      "fv-old-2",
    ]);
  });

  it("forwards provider_data with connections", async () => {
    mockApiPatch.mockResolvedValue({ data: {} });

    const mutation = usePatchDeployment();
    await mutation.mutate({
      deployment_id: "dep-1",
      provider_data: {
        connections: [
          {
            app_id: "conn-1",
            credentials: [
              { key: "API_KEY", value: "secret", source: "raw" as const },
            ],
          },
        ],
      },
    });

    const sentBody = mockApiPatch.mock.calls[0][1];
    expect(sentBody.provider_data.connections).toHaveLength(1);
    expect(sentBody.provider_data.connections[0].app_id).toBe("conn-1");
    expect(sentBody.provider_data.connections[0].credentials[0]).toEqual({
      key: "API_KEY",
      value: "secret",
      source: "raw",
    });
  });

  it("forwards provider_data with upsert_tools and remove_tools", async () => {
    mockApiPatch.mockResolvedValue({ data: {} });

    const mutation = usePatchDeployment();
    await mutation.mutate({
      deployment_id: "dep-1",
      provider_data: {
        upsert_tools: [
          { tool_id: "tool-1", add_app_ids: ["app-1"], remove_app_ids: [] },
        ],
        remove_tools: ["tool-old"],
      },
    });

    const sentBody = mockApiPatch.mock.calls[0][1];
    expect(sentBody.provider_data.upsert_tools).toEqual([
      { tool_id: "tool-1", add_app_ids: ["app-1"], remove_app_ids: [] },
    ]);
    expect(sentBody.provider_data.remove_tools).toEqual(["tool-old"]);
  });

  it("sends empty body (minus deployment_id) when no optional fields provided", async () => {
    mockApiPatch.mockResolvedValue({ data: {} });

    const mutation = usePatchDeployment();
    await mutation.mutate({ deployment_id: "dep-1" });

    const sentBody = mockApiPatch.mock.calls[0][1];
    expect(sentBody).toEqual({});
    expect(sentBody).not.toHaveProperty("deployment_id");
  });

  // ---------------------------------------------------------------------------
  // Cache invalidation on success
  // ---------------------------------------------------------------------------

  it("refetches useGetDeployments on success", async () => {
    mockApiPatch.mockResolvedValue({ data: { id: "dep-1" } });

    const mutation = usePatchDeployment();
    await mutation.mutate({ deployment_id: "dep-1", name: "X" });

    expect(mockQueryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["useGetDeployments"],
    });
  });

  it("removes useGetDeploymentAttachments cache on success", async () => {
    mockApiPatch.mockResolvedValue({ data: { id: "dep-1" } });

    const mutation = usePatchDeployment();
    await mutation.mutate({ deployment_id: "dep-1", name: "X" });

    expect(mockQueryClient.removeQueries).toHaveBeenCalledWith({
      queryKey: ["useGetDeploymentAttachments"],
    });
  });

  it("removes useGetDeployment cache on success", async () => {
    mockApiPatch.mockResolvedValue({ data: { id: "dep-1" } });

    const mutation = usePatchDeployment();
    await mutation.mutate({ deployment_id: "dep-1", name: "X" });

    expect(mockQueryClient.removeQueries).toHaveBeenCalledWith({
      queryKey: ["useGetDeployment"],
    });
  });

  it("invalidates all three query keys on a single successful mutation", async () => {
    mockApiPatch.mockResolvedValue({ data: { id: "dep-1" } });

    const mutation = usePatchDeployment();
    await mutation.mutate({ deployment_id: "dep-1", name: "Y" });

    expect(mockQueryClient.refetchQueries).toHaveBeenCalledTimes(1);
    expect(mockQueryClient.removeQueries).toHaveBeenCalledTimes(2);
  });

  // ---------------------------------------------------------------------------
  // Return value
  // ---------------------------------------------------------------------------

  it("returns the response data from the API", async () => {
    const responseData = {
      id: "dep-1",
      name: "Updated",
      description: "Fresh",
      provider_data: { agent_id: "agent-xyz" },
    };
    mockApiPatch.mockResolvedValue({ data: responseData });

    const mutation = usePatchDeployment();
    const result = await mutation.mutate({
      deployment_id: "dep-1",
      name: "Updated",
    });

    expect(result).toEqual(responseData);
  });

  // ---------------------------------------------------------------------------
  // Error propagation
  // ---------------------------------------------------------------------------

  it("propagates API errors without cache invalidation", async () => {
    const error = new Error("422 Validation Error");
    mockApiPatch.mockRejectedValue(error);

    const mutation = usePatchDeployment();
    await expect(
      mutation.mutate({ deployment_id: "dep-1", name: "Bad" }),
    ).rejects.toThrow("422 Validation Error");

    expect(mockQueryClient.refetchQueries).not.toHaveBeenCalled();
    expect(mockQueryClient.removeQueries).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------------------
  // Combined update (name + description + provider_data)
  // ---------------------------------------------------------------------------

  it("sends a full update with name, description, and provider_data together", async () => {
    mockApiPatch.mockResolvedValue({ data: {} });

    const payload: DeploymentUpdateRequest = {
      deployment_id: "dep-full",
      name: "Full Update Agent",
      description: "Complete update test",
      provider_data: {
        llm: "meta-llama/llama-3-3-70b-instruct",
        connections: [
          {
            app_id: "conn-new",
            credentials: [
              { key: "TOKEN", value: "var_token", source: "variable" as const },
            ],
          },
        ],
        upsert_flows: [
          {
            flow_version_id: "fv-new",
            add_app_ids: ["conn-new"],
            remove_app_ids: ["conn-old"],
            tool_name: "updated_tool",
          },
        ],
        remove_flows: ["fv-removed"],
      },
    };

    const mutation = usePatchDeployment();
    await mutation.mutate(payload);

    const sentBody = mockApiPatch.mock.calls[0][1];
    expect(sentBody).not.toHaveProperty("deployment_id");
    expect(sentBody.name).toBe("Full Update Agent");
    expect(sentBody.description).toBe("Complete update test");
    expect(sentBody.provider_data.llm).toBe(
      "meta-llama/llama-3-3-70b-instruct",
    );
    expect(sentBody.provider_data.connections).toHaveLength(1);
    expect(sentBody.provider_data.upsert_flows).toHaveLength(1);
    expect(sentBody.provider_data.remove_flows).toEqual(["fv-removed"]);
    expect(sentBody.provider_data.connections[0].credentials[0].source).toBe(
      "variable",
    );
  });
});
