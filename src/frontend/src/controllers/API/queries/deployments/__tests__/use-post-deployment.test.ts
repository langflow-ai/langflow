const mockApiPost = jest.fn();
const mockQueryClient = {
  refetchQueries: jest.fn(),
  invalidateQueries: jest.fn(),
};

jest.mock("@/controllers/API/api", () => ({
  api: { post: mockApiPost },
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
        options?.onSuccess?.(result);
        options?.onSettled?.(result);
        return result;
      },
    })),
    queryClient: mockQueryClient,
  })),
}));

import type { DeploymentCreateRequest } from "../use-post-deployment";
import { usePostDeployment } from "../use-post-deployment";

describe("usePostDeployment", () => {
  beforeEach(() => jest.clearAllMocks());

  const validPayload: DeploymentCreateRequest = {
    provider_id: "prov-1",
    spec: { name: "My Agent", description: "A test agent", type: "agent" },
    provider_data: {
      llm: "ibm/granite-3-8b-instruct",
      operations: [
        {
          op: "bind",
          flow_version_id: "fv-1",
          app_ids: ["app-1"],
          tool_name: "my_tool",
        },
      ],
      connections: {
        raw_payloads: [
          {
            app_id: "app-1",
            environment_variables: {
              API_KEY: { value: "secret", source: "raw" },
            },
          },
        ],
      },
    },
  };

  it("posts to deployments endpoint with full payload", async () => {
    mockApiPost.mockResolvedValue({ data: { id: "dep-1", name: "My Agent" } });

    const mutation = usePostDeployment();
    await mutation.mutate(validPayload);

    expect(mockApiPost).toHaveBeenCalledWith(
      "/api/v1/deployments",
      validPayload,
    );
  });

  it("refetches useGetDeployments on success", async () => {
    mockApiPost.mockResolvedValue({ data: { id: "dep-1" } });

    const mutation = usePostDeployment();
    await mutation.mutate(validPayload);

    expect(mockQueryClient.refetchQueries).toHaveBeenCalledWith({
      queryKey: ["useGetDeployments"],
    });
  });

  it("sends operations without tool_name when not provided", async () => {
    const payloadNoToolName: DeploymentCreateRequest = {
      ...validPayload,
      provider_data: {
        ...validPayload.provider_data,
        operations: [
          { op: "bind", flow_version_id: "fv-1", app_ids: ["app-1"] },
        ],
      },
    };
    mockApiPost.mockResolvedValue({ data: { id: "dep-1" } });

    const mutation = usePostDeployment();
    await mutation.mutate(payloadNoToolName);

    const sentPayload = mockApiPost.mock.calls[0][1];
    expect(sentPayload.provider_data.operations[0].tool_name).toBeUndefined();
  });
});
